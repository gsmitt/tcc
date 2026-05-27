"""Shared piano-fingering cost machinery.

Every solver imports `DISTANCE_COSTS`, `finger_move_cost`, `chord_complexity`,
etc. from here so the cost model is defined exactly once. Hand-aware: pass
`hand="L"` (or `"R"`) to mirror the keyboard for the left hand.

The 100 sentinel in the tables marks moves that are physically impossible
(e.g. crossing a black key with the wrong finger pair). It is re-exported as
`MAX_MOVE_COST_HARD` so solvers can use it as a hard pruning threshold.
"""

MAX_MOVE_COST_HARD = 100

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
        return note_span + 2
    if note_span >= len(finger_combo):
        return note_span + 2
    return finger_combo[note_span]


def fingering_transition_cost(prev_notes, curr_notes, prev_fingers, curr_fingers, hand="R"):
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

    # 1. Penalize finger crossings.
    for i in range(len(combined) - 1):
        _, f_a = combined[i]
        _, f_b = combined[i + 1]
        if f_a >= f_b:
            total_cost += 10

    # 2. Penalize wide spans (thumb–pinky distance).
    if max_span > 12:
        total_cost += MAX_MOVE_COST_HARD
    else:
        total_cost += max(0, (max_span - 7)) * 2

    # 3. Base ergonomic cost from the distance tables.
    for i in range(len(combined) - 1):
        note_a, finger_a = combined[i]
        note_b, finger_b = combined[i + 1]

        note_span = abs(note_b[0] - note_a[0])
        transition = f"{key_color(note_a[0])}-{key_color(note_b[0])}"
        key = f"{finger_a}-{finger_b}"

        finger_combo = DISTANCE_COSTS.get(transition, {}).get(key)
        if finger_combo is not None and note_span < len(finger_combo):
            total_cost += finger_combo[note_span]
        else:
            total_cost += note_span + 2

    return total_cost
