"""Shared piano-fingering cost machinery.

Every solver imports `DISTANCE_COSTS`, `finger_move_cost`, `chord_complexity`,
etc. from here so the cost model is defined exactly once. Hand-aware: pass
`hand="L"` (or `"R"`) to mirror the keyboard for the left hand.

Sources
-------
`DISTANCE_COSTS` reproduces Tables 1-4 of

    M. Hart, R. Bosch and E. Tsai, "Finding optimal piano fingerings",
    The UMAP Journal 21(2):167-177, 2000.

(Tables 1-4 sit on pp. 3-4 of the preprint in `refs/relevantes/piano.pdf`; that
numbering is the preprint's, not the journal's, so don't cite it as such.)

The authors rate every "basic movement" -- one finger on one key followed by
another finger on another key -- from 1 (easiest) to 4 (hardest), indexed by the
ordered finger pair, the interval size in semitones and the white/black colours
of the two keys (hence the four tables). Verified cell by cell: all 672 entries
match the paper.

**The pair is ordered by pitch, not by time.** Hart et al. index rows by
`(finger on the lower note, finger on the upper note)` and name the tables
`Lower-<colour>-upper-<colour>`, so the two keys' colours are read in the same
low->high order. `finger_move_cost` therefore sorts by pitch before the lookup,
which means an ascending 1->3 and a descending 3->1 over the same two keys hit
the *same* cell: the table does not distinguish direction of motion. What the
ordering does distinguish is where the thumb sits -- row (1,3) is the thumb below
the middle finger, row (3,1) the thumb above it, i.e. a thumb crossing, which is
why the (x,1) rows carry the high costs. Inversions not involving the thumb are
not tabulated at all; the source does not allow them.

**Table columns are interval sizes 1..12**, so a span of `s` semitones is
`row[s - 1]`. Span 0 (a repeated note) is not tabulated by Hart et al. and is
extrapolated here as the cheapest cost. Earlier revisions of this module indexed
`row[s]` directly, which shifted every lookup by one semitone; the shift also
moved the paper's "impossible" sentinels off the black-black spans they belong
to, and a `_repair_bb` routine was patching the wrong cells to compensate. Both
are gone: the sentinels now land on spans 1, 6 and 11, which are exactly the
intervals two black keys can never form.

The simultaneous-span thresholds `MAX_COMFORT` / `MAX_ABS` come from a different
source -- Table 1 (p. 346) of

    R. Parncutt, J. A. Sloboda, E. F. Clarke, M. Raekallio and P. Desain,
    "An ergonomic model of keyboard fingering for melodic fragments",
    Music Perception 14(4):341-382, 1997.

Parncutt et al. express difficulty as twelve named rules, not as a table; only
the span limits are taken from them. See `MAX_COMFORT` for which of their
columns each value corresponds to. Using them for *simultaneous* spans is
sanctioned by the source: it defines MaxPrac as the largest stretch a pianist
would use "to span two notes played either simultaneously or consecutively in
finger legato", despite the paper being about melodic fragments.

The weights this project chose (chord-span threshold and coefficient, the
stretch coefficient, the release cost, the untabulated and unison costs, the 1-5
comfortable span) live in :mod:`src.params`; ``otimizar.py`` fits the ones the
fingering depends on, on PIG pieces 031-150 only.

**No crossing inside a chord.** Every caller generates a chord's fingering from
its thumb side with ascending fingers (``itertools.combinations``), so a crossed
chord fingering is never tried; :func:`chord_complexity` rejects one instead of
pricing it, since it can only come from a caller that passed the notes in the
wrong order.

**Held notes.** A layer holds only the notes that *start* there, so a note still
sounding from an earlier layer is outside `chord_complexity`. `held_reach_cost`
closes that gap: every held note is kept, paying the chord pair limits
(`_stretch_cost`) against each new note of the hand, or released early at a fixed
cost, whichever is cheaper; holding C3 with the thumb while the index plays C6 is
no longer free, the C3 is let go.

**Chord width.** The hard limit on a chord's total span is the absolute limit of
the widest pair, `MAX_ABS[(1, 5)]` (``comfort_1_5`` + 2 semitones), so it agrees with the pair
limits instead of cutting at the octave.

The 100 sentinel in the tables marks moves the source marks as non-existent. It
is re-exported as `MAX_MOVE_COST_HARD` so solvers can use it as a hard pruning
threshold.
"""

MAX_MOVE_COST_HARD = 100

# Weights chosen by this project, not by a source (chord span, stretch,
# release, untabulated moves, unison, the 1-5 comfortable span) live in
# :mod:`src.params`, where ``otimizar.py`` fits them; ``P`` is the live dict.
from src.params import VALUES as P

DISTANCE_COSTS = {
    "w-w": {
        "1-2": [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3],
        "1-3": [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3],
        "1-4": [2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
        "1-5": [3, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1],
        "2-1": [2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4],
        "2-3": [1, 1, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3],
        "2-4": [2, 2, 1, 1, 1, 1, 2, 3, 3, 3, 3, 3],
        "2-5": [3, 3, 2, 2, 1, 1, 1, 1, 1, 2, 2, 2],
        "3-1": [2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4],
        "3-4": [1, 1, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3],
        "3-5": [3, 3, 1, 1, 1, 1, 3, 3, 3, 3, 3, 3],
        "4-1": [2, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
        "4-5": [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3],
        "5-1": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    },
    "w-b": {
        "1-2": [1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 100],
        "1-3": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 100],
        "1-4": [2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 100],
        "1-5": [3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 100],
        "2-1": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 100],
        "2-3": [1, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3, 100],
        "2-4": [2, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 100],
        "2-5": [3, 2, 2, 2, 2, 1, 1, 1, 2, 2, 3, 100],
        "3-1": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 100],
        "3-4": [1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 100],
        "3-5": [3, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 100],
        "4-1": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 100],
        "4-5": [2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 100],
        "5-1": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 100],
    },
    "b-w": {
        "1-2": [3, 2, 2, 1, 1, 2, 2, 2, 3, 3, 3, 100],
        "1-3": [3, 2, 2, 1, 1, 1, 2, 2, 2, 2, 3, 100],
        "1-4": [3, 3, 3, 1, 1, 1, 1, 1, 2, 2, 2, 100],
        "1-5": [3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 100],
        "2-1": [2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 100],
        "2-3": [1, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3, 100],
        "2-4": [2, 1, 1, 1, 1, 2, 3, 3, 3, 3, 3, 100],
        "2-5": [3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 2, 100],
        "3-1": [2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 100],
        "3-4": [1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 100],
        "3-5": [2, 1, 1, 1, 1, 1, 2, 2, 3, 3, 3, 100],
        "4-1": [3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 100],
        "4-5": [1, 1, 1, 2, 2, 3, 3, 3, 3, 3, 3, 100],
        "5-1": [3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 100],
    },
    "b-b": {
        "1-2": [100, 2, 2, 2, 2, 100, 3, 3, 3, 3, 100, 3],
        "1-3": [100, 2, 2, 2, 2, 100, 2, 2, 2, 2, 100, 2],
        "1-4": [100, 3, 2, 2, 2, 100, 2, 1, 1, 1, 100, 2],
        "1-5": [100, 3, 3, 3, 3, 100, 2, 1, 1, 1, 100, 1],
        "2-1": [100, 2, 3, 3, 4, 100, 4, 4, 4, 4, 100, 4],
        "2-3": [100, 1, 1, 1, 2, 100, 3, 3, 3, 3, 100, 3],
        "2-4": [100, 2, 1, 1, 1, 100, 2, 3, 3, 3, 100, 3],
        "2-5": [100, 3, 2, 2, 1, 100, 1, 1, 1, 2, 100, 2],
        "3-1": [100, 3, 4, 4, 4, 100, 4, 4, 4, 4, 100, 4],
        "3-4": [100, 1, 1, 1, 2, 100, 3, 3, 3, 3, 100, 3],
        "3-5": [100, 3, 1, 1, 2, 100, 3, 3, 3, 3, 100, 3],
        "4-1": [100, 4, 4, 4, 4, 100, 4, 4, 4, 4, 100, 4],
        "4-5": [100, 2, 2, 2, 3, 100, 3, 3, 3, 3, 100, 3],
        "5-1": [100, 4, 4, 4, 4, 100, 4, 4, 4, 4, 100, 4],
    },
}




def key_color(midi_note: int) -> str:
    if midi_note % 12 in {1, 3, 6, 8, 10}:
        return "b"
    return "w"


# Comfortable / absolute maximum span (in semitones) that a finger pair can
# stretch *simultaneously* (for chords), keyed by the sorted finger pair. The
# distance tables stop at 12 semitones, so anything wider is judged here.
#
# From Parncutt et al. (1997), Table 1, p. 346, with two documented departures:
#   * pairs without the thumb: MAX_COMFORT is their MaxComf and MAX_ABS their
#     MaxPrac, taken literally;
#   * pairs 1-2, 1-3, 1-4: MAX_COMFORT is their *MaxRel* (one level below
#     MaxComf), a deliberately conservative reading of the thumb's reach, with
#     MAX_ABS = MAX_COMFORT + 2, the relation the paper itself defines;
#   * pair 1-5: its comfortable span is a parameter (``comfort_1_5`` in
#     src.params, searched from 10 to the paper's MaxComf of 13) and its
#     absolute span is two semitones above.  The 12/14 below are the
#     hand-picked start, the octave and the major ninth; ``set_span_limits``
#     puts the value in force in their place when the module loads.
MAX_COMFORT = {(1, 2): 5, (1, 3): 7, (1, 4): 9, (1, 5): 12, (2, 3): 3,
               (2, 4): 5, (2, 5): 8, (3, 4): 2, (3, 5): 5, (4, 5): 3}
MAX_ABS = {(1, 2): 7, (1, 3): 9, (1, 4): 11, (1, 5): 14, (2, 3): 5,
           (2, 4): 7, (2, 5): 10, (3, 4): 4, (3, 5): 7, (4, 5): 5}

# The paper's own values for the thumb pairs (MaxComf / MaxPrac of Table 1), used
# only by the sensitivity experiment (``evaluate.py``) to show how much the
# departures above matter; the pairs without the thumb are already literal.
SPAN_LIMITS = {
    "tcc": (dict(MAX_COMFORT), dict(MAX_ABS)),
    "parncutt": ({**MAX_COMFORT, (1, 2): 8, (1, 3): 10, (1, 4): 12, (1, 5): 13},
                 {**MAX_ABS, (1, 2): 10, (1, 3): 12, (1, 4): 14, (1, 5): 15}),
}


_SPAN_LIMITS_NAME = "tcc"


def set_span_limits(name):
    """Switch the pair limits in place (``"tcc"`` default, ``"parncutt"``).

    Under ``"tcc"`` the 1-5 pair takes its comfortable span from
    :mod:`src.params` (``comfort_1_5``) and its absolute span two semitones
    above, the relation the paper fixes between its comfortable and practical
    levels; ``"parncutt"`` keeps the paper's own 13/15.
    """
    global _SPAN_LIMITS_NAME
    comfort, absol = (dict(d) for d in SPAN_LIMITS[name])
    if name == "tcc":
        comfort[(1, 5)] = P["comfort_1_5"]
        absol[(1, 5)] = P["comfort_1_5"] + 2
    MAX_COMFORT.clear(); MAX_COMFORT.update(comfort)
    MAX_ABS.clear(); MAX_ABS.update(absol)
    _SPAN_LIMITS_NAME = name


def current_span_limits():
    return _SPAN_LIMITS_NAME


set_span_limits("tcc")     # apply the 1-5 span in force (src.params)


def _stretch_cost(finger_a, finger_b, span):
    """Stretch cost for two fingers reaching ``span`` semitones at once.

    Returns ``MAX_MOVE_COST_HARD`` if impossible, an escalating cost if merely
    uncomfortable, or ``None`` when the span is within comfortable reach (so the
    caller should use the tabulated ergonomic cost instead).
    """
    pair = tuple(sorted((finger_a, finger_b)))
    comfort, absol = MAX_COMFORT[pair], MAX_ABS[pair]
    if span > absol:
        return MAX_MOVE_COST_HARD
    if span > comfort:
        return (span - comfort) * P["stretch_weight"]
    return None


def _curr_is_thumb_side(note_prev, note_curr, hand):
    # RH: thumb (finger 1) sits on the lowest-pitch key in a hand position.
    # LH: geometry mirrors — thumb sits on the highest-pitch key.
    if hand == "R":
        return note_curr[0] < note_prev[0]
    return note_curr[0] > note_prev[0]


def finger_move_cost(note_prev, note_curr, finger_prev, finger_curr, hand="R"):
    note_span = abs(note_curr[0] - note_prev[0])
    if _curr_is_thumb_side(note_prev, note_curr, hand):
        key = f"{finger_curr}-{finger_prev}"
        transition = f"{key_color(note_curr[0])}-{key_color(note_prev[0])}"
    else:
        key = f"{finger_prev}-{finger_curr}"
        transition = f"{key_color(note_prev[0])}-{key_color(note_curr[0])}"
    finger_combo = DISTANCE_COSTS[transition].get(key, None)

    if finger_combo is None:
        return note_span + P["untabulated_offset"]
    if note_span == 0:
        return P["unison"]             # repeated note; not tabulated by Hart et al.
    if note_span > len(finger_combo):  # wider than the table's 12 semitones
        return note_span + P["untabulated_offset"]
    return finger_combo[note_span - 1]     # column `note_span` of the source table


def fingering_transition_cost(prev_notes, curr_notes, prev_fingers, curr_fingers, hand="R"):
    """Max over voices of the per-note move cost between two consecutive layers.

    Notes are paired by position (each hand's layers are pitch-sorted from the
    thumb side, see :func:`src.hand_assigner.split_layers_by_hands`), so when the two
    layers differ in size the extra notes of the larger one are unpaired and add
    no transition cost -- a known simplification (thesis §4.3.1).
    """
    max_cost = 0
    for (n_prev, f_prev, n_curr, f_curr) in zip(prev_notes, prev_fingers, curr_notes, curr_fingers):
        if n_prev != n_curr:
            c = finger_move_cost(n_prev, n_curr, f_prev, f_curr, hand)
            max_cost = max(max_cost, c)
    return max_cost


def chord_complexity(notes, fingers, hand="R"):
    if len(notes) <= 1:
        return 0

    # RH: sort ascending so finger_a sits on the thumb-side (lowest) note.
    # LH: sort descending so finger_a sits on the thumb-side (highest) note.
    combined = sorted(zip(notes, fingers), key=lambda x: x[0][0], reverse=(hand == "L"))
    total_cost = 0
    max_span = abs(combined[-1][0][0] - combined[0][0][0])

    # 1. No crossing: from the thumb side, the fingers must ascend (module
    #    docstring).  A crossed fingering means the caller ordered the notes
    #    wrongly, so it is an error, not a cost.
    for i in range(len(combined) - 1):
        if combined[i][1] > combined[i + 1][1]:
            raise ValueError(f"crossed chord fingering {fingers} for {notes} ({hand}): "
                             "fingers must ascend from the thumb side")

    # 2. Penalize wide spans (thumb–pinky distance); beyond the widest pair's
    #    absolute limit no fingering reaches the chord.
    if max_span > MAX_ABS[(1, 5)]:
        total_cost += MAX_MOVE_COST_HARD
    else:
        total_cost += max(0, max_span - P["chord_span_threshold"]) * P["chord_span_weight"]

    # 3. Base ergonomic cost: stretch model first (handles octaves+ and rejects
    #    pairs that physically cannot span the interval), then the distance table.
    for i in range(len(combined) - 1):
        note_a, finger_a = combined[i]
        note_b, finger_b = combined[i + 1]

        note_span = abs(note_b[0] - note_a[0])
        stretch = _stretch_cost(finger_a, finger_b, note_span)
        if stretch is not None:
            total_cost += stretch
            continue

        transition = f"{key_color(note_a[0])}-{key_color(note_b[0])}"
        key = f"{finger_a}-{finger_b}"
        finger_combo = DISTANCE_COSTS.get(transition, {}).get(key)
        if finger_combo is not None:
            # within comfortable reach: use the table (columns are interval
            # sizes 1..12), clamped to its widest tabulated value.
            if note_span == 0:
                total_cost += P["unison"]   # unison; not tabulated by Hart et al.
            else:
                total_cost += finger_combo[min(note_span, len(finger_combo)) - 1]
        else:
            total_cost += note_span + P["untabulated_offset"]

    return total_cost



# Cost of letting go of a held note before its written end because the hand
# cannot (or should not) keep it while it plays the new notes: the legato or the
# held sound the score asks for is lost, though the pedal often keeps the sound.
# Its weight is ``P["release"]`` (src.params).


def held_reach_cost(held, notes, fingers, hand="R"):
    """Cost of the notes a hand still holds while it starts new ones.

    ``held`` is a list of ``(pitch, finger)`` for the fingers still pressing a key
    from an earlier layer at this onset; ``notes``/``fingers`` are the new layer's
    notes and the fingers chosen for them.  For each held note the hand takes the
    cheaper of two options: keep it, paying the stretch between it and every new
    note under the chord pair limits (`_stretch_cost`), or release it early,
    paying ``P["release"]``.  A held note beyond the absolute limit of a pair
    is therefore always released, never treated as impossible: in a score a long
    bass note under a moving hand is normal, and the pianist lets go of the key.

    Returns ``(cost, released)`` with ``released`` the fingers that let go; the
    solvers free them from the next onset on.  ``hand`` is accepted for symmetry
    with the other cost functions; spans are distances, the same for both hands.
    """
    total = 0
    released = []
    for held_pitch, held_finger in held:
        keep = 0
        for (pitch, _end), finger in zip(notes, fingers):
            stretch = _stretch_cost(held_finger, finger, abs(pitch - held_pitch))
            if stretch is not None:
                keep += stretch
        if keep > P["release"]:
            total += P["release"]
            released.append(held_finger)
        else:
            total += keep
    return total, released
