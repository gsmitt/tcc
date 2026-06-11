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

Times here are in whole-note fractions (the unit used throughout the pipeline,
see :mod:`src.midi_reader`); ``delta_t`` is in the same unit and is the analogue
of the paper's 1 s window.
"""

from .costs import chord_complexity, fingering_transition_cost


def layer_costs(layers, path, hand):
    """Per-layer ergonomic cost for a solved hand.

    ``path`` is the solver's output: ``[(notes, fingers), ...]`` aligned with
    ``layers``. Each layer's cost is its chord complexity plus the transition
    cost from the previous layer (the same two terms the solvers minimise).
    """
    costs = []
    for i, (notes, fingers) in enumerate(path):
        c = chord_complexity(notes, fingers, hand)
        if i > 0:
            prev_notes, prev_fingers = path[i - 1]
            c += fingering_transition_cost(prev_notes, notes,
                                           prev_fingers, fingers, hand)
        costs.append(float(c))
    return costs


def _window_density(query_times, src_times, src_costs, delta_t):
    """For each query onset, sum ``src_costs`` whose ``src_times`` fall in the
    window of width ``delta_t`` centred on it, divided by ``delta_t``.
    """
    half = delta_t / 2.0
    out = []
    for t in query_times:
        lo, hi = t - half, t + half
        total = sum(c for st, c in zip(src_times, src_costs) if lo <= st <= hi)
        out.append(total / delta_t)
    return out


def note_difficulties(layers, lh_layers, lh_path, rh_layers, rh_path, delta_t):
    """Per-onset difficulty triplet ``(D_L, D_R, D_B)``.

    Returns a list aligned with ``layers`` (the combined condensed score). Each
    hand's difficulty at an onset is the windowed density of that hand's
    per-layer cost; ``D_B = D_L + D_R`` (paper §II.B.1, eq. (7)).
    """
    query_times = [layer["time"] for layer in layers]

    lh_times = [l["time"] for l in lh_layers]
    rh_times = [l["time"] for l in rh_layers]
    lh_costs = layer_costs(lh_layers, lh_path, "L")
    rh_costs = layer_costs(rh_layers, rh_path, "R")

    d_l = _window_density(query_times, lh_times, lh_costs, delta_t)
    d_r = _window_density(query_times, rh_times, rh_costs, delta_t)
    return [(l, r, l + r) for l, r in zip(d_l, d_r)]
