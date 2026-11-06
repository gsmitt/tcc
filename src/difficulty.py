"""Performance-difficulty measure over a solved fingering.

This is the project's deterministic analogue of the difficulty measure used in
the piano-reduction literature:

    Nakamura & Sagayama, "Automatic Piano Reduction from Ensemble Scores Based
    on Merged-Output Hidden Markov Model", ICMC 2015, eq. (4);
    Nakamura & Yoshii, "Statistical Piano Reduction Controlling Performance
    Difficulty", APSIPA Trans. Signal & Information Processing 7 (2018),
    eq. (6)-(7), §II.B.1.

There the difficulty is the time rate of a probabilistic cost,
``D(t) = -ln P(p(t), f(t)) / Δt``. This project does not carry a probabilistic
piano-score model; it scores playing effort with the ergonomic cost in
:mod:`src.costs` instead. So we keep the *same shape* of the measure -- a cost
density over a time window -- but substitute the ergonomic cost for ``-ln P``:

    D_hand(t) = (sum of per-layer ergonomic cost in [t - Δt/2, t + Δt/2]) / Δt

with per-hand difficulties ``D_L``/``D_R`` and the both-hands total
``D_B = D_L + D_R`` (paper §II.B.1). No solver change is needed: the per-layer
cost is recomputed from an already-solved ``path`` with :mod:`src.costs`.

Units: tempo dependence
-----------------------
``delta_t`` is in **seconds**, defaulting to the paper's 1 s (§II.B.2), and the
difficulty is a cost *per second*.  This is the whole point of taking a rate
rather than a sum: the paper defines difficulty as a time rate precisely "to
include the dependence on tempo" (§II.B.1).  Measuring the window in note values
instead would make the same passage score identically at any tempo, which removes
the property the measure exists to have.

Layer times stay in whole-note fractions (:mod:`src.midi_reader`) -- the unit the
rest of the pipeline uses, and tempo-free because fingering is.  Only the window
converts: with ``bpm`` in quarter notes per minute a whole note lasts
``240 / bpm`` seconds, so a window of ``delta_t`` seconds spans
``delta_t * bpm / 240`` whole notes (:func:`window_whole_notes`).  Twice the tempo
puts twice as much material inside the same second, hence roughly twice the
difficulty.

What counts as "tempo" here is the event rate, not the metronome mark alone:
Sébastien et al., "Score Analyzer: Automatically Determining Scores Difficulty
Level for Instrumental e-Learning", ISMIR 2012, §2.1, define playing speed from
the tempo *and* the shortest significant note value (a fast tempo in long values
and a slow one in short values can demand the same agility); Ramoneda et al.,
"Towards Explainable and Interpretable Musical Difficulty Estimation", ISMIR
2024, §3.1, formalise it as the mean inter-onset interval in seconds.  The window
here is a density over exactly that: both the tempo and the note values inside the
second determine how much cost falls in it.
"""

from .costs import chord_complexity, fingering_transition_cost, held_reach_cost

# The paper's window, in seconds (Nakamura & Yoshii 2018, §II.B.2: "we set Δt to
# be 1 s").
DEFAULT_DELTA_T = 1.0


def window_whole_notes(delta_t, bpm):
    """Width, in whole-note fractions, of a ``delta_t``-second window at ``bpm``.

    ``bpm`` is quarter notes per minute, so a whole note lasts ``240 / bpm``
    seconds.  Every consumer of the difficulty window (notably
    :mod:`src.sheet_reducer`, which collects the notes inside it) must use this
    function, so the window the reducer edits cannot drift from the window the
    difficulty is measured over.
    """
    return delta_t * bpm / 240.0


def layer_costs(layers, path, hand):
    """Per-layer ergonomic cost for a solved hand.

    ``path`` is the solver's output: ``[(notes, fingers), ...]`` aligned with
    ``layers``. Each layer's cost is its chord complexity, the reach cost against
    the notes still held from earlier layers, and the transition cost from the
    previous layer (the same terms the solvers minimise).
    """
    costs = []
    pressing = {}                       # finger -> (pitch, release) of its last note
    for i, (notes, fingers) in enumerate(path):
        time = layers[i]["time"]
        still_held = [(p, f) for f, (p, r) in pressing.items() if r > time]
        c = chord_complexity(notes, fingers, hand)
        reach, released = held_reach_cost(still_held, notes, fingers, hand)
        c += reach
        for f in released:              # a note let go early frees its finger
            pressing.pop(f, None)
        if i > 0:
            prev_notes, prev_fingers = path[i - 1]
            c += fingering_transition_cost(prev_notes, notes,
                                           prev_fingers, fingers, hand)
        costs.append(float(c))
        for (pitch, release), f in zip(notes, fingers):
            pressing[f] = (pitch, release)
    return costs


def _window_density(query_times, src_times, src_costs, width, delta_t):
    """For each query onset, sum ``src_costs`` whose ``src_times`` fall in the
    window of ``width`` whole notes centred on it, divided by ``delta_t`` seconds.

    ``width`` is the seconds-long window expressed in the layers' whole-note unit
    (:func:`window_whole_notes`); dividing by ``delta_t`` makes the result a cost
    per second.
    """
    half = width / 2.0
    out = []
    for t in query_times:
        lo, hi = t - half, t + half
        total = sum(c for st, c in zip(src_times, src_costs) if lo <= st <= hi)
        out.append(total / delta_t)
    return out


def note_difficulties(layers, lh_layers, lh_path, rh_layers, rh_path,
                      *, bpm, delta_t=DEFAULT_DELTA_T):
    """Per-onset difficulty triplet ``(D_L, D_R, D_B)`` in cost per second.

    Returns a list aligned with ``layers`` (the combined condensed score). Each
    hand's difficulty at an onset is the windowed density of that hand's
    per-layer cost; ``D_B = D_L + D_R`` (paper §II.B.1, eq. (7)).

    ``bpm`` is the tempo the piece is being measured *at* -- the score's tempo
    times any global tempo factor the reducer applied -- and is required rather
    than defaulted, because a difficulty figure means nothing without the tempo it
    was measured at.  ``delta_t`` is the window in seconds.
    """
    query_times = [layer["time"] for layer in layers]
    width = window_whole_notes(delta_t, bpm)

    lh_times = [l["time"] for l in lh_layers]
    rh_times = [l["time"] for l in rh_layers]
    lh_costs = layer_costs(lh_layers, lh_path, "L")
    rh_costs = layer_costs(rh_layers, rh_path, "R")

    d_l = _window_density(query_times, lh_times, lh_costs, width, delta_t)
    d_r = _window_density(query_times, rh_times, rh_costs, width, delta_t)
    return [(l, r, l + r) for l, r in zip(d_l, d_r)]
