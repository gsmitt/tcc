import math
from itertools import combinations
from Hand import HandState
import random

MAX_MOVE_COST = 100
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
    }
}

def key_color(midi_note: int) -> bool:
    if midi_note % 12 in {1, 3, 6, 8, 10}:
        return "b"
    return "w"

def finger_move_cost(note_prev, note_curr, finger_prev, finger_curr):
    note_span = abs(note_curr[0] - note_prev[0])
    if note_curr[0] < note_prev[0]:
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


def fingering_transition_cost(prev_notes, curr_notes, prev_fingers, curr_fingers):
    max_cost = 0
    for (n_prev, f_prev, n_curr, f_curr) in zip(prev_notes, prev_fingers, curr_notes, curr_fingers):
        if n_prev != n_curr:
            c = finger_move_cost(n_prev, n_curr, f_prev, f_curr)
            max_cost = max(max_cost, c)
    return max_cost

def chord_complexity(notes, fingers):
    if len(notes) <= 1:
        return 0

    # Sort by pitch (lowest to highest)
    combined = sorted(zip(notes, fingers), key=lambda x: x[0][0])
    total_cost = 0
    max_span = abs(combined[-1][0][0] - combined[0][0][0])

    # --- 1. Penalize finger crossings ---
    # If the finger order doesn’t match the note order, bad.
    # e.g., notes [C4, D4, E4] with fingers [2,1,3]
    for i in range(len(combined) - 1):
        _, f_a = combined[i]
        _, f_b = combined[i + 1]
        if f_a >= f_b:
            total_cost += 10  # large penalty for unnatural ordering

    # --- 2. Penalize wide spans ---
    # Based on thumb–pinky distance
    if max_span > 12:
        # Completely unrealistic beyond an octave
        total_cost += MAX_MOVE_COST
    else:
        # Gradually increase penalty near the limit
        total_cost += max(0, (max_span - 7)) * 2

    # --- 3. Base ergonomic cost from existing distance tables ---
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
            total_cost += note_span + 2  # fallback

    return total_cost


class PianoFingeringDFS:
    def __init__(self, chords):
        self.chords = chords
        self.best_cost = math.inf
        self.best_path = []
        self.node_visits = 0
        self.saved_states = 0
        self.memo = {}

    def _possible_fingerings(self, n, fingers):
        return list(combinations(fingers, n))

    def _dfs(self, idx, prev_notes, prev_fingers, total_cost, path, hand):
        self.node_visits += 1

        # Finished all chords
        if idx == len(self.chords):
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_path = path[:]
            return

        chord = self.chords[idx]
        time = chord["time"]
        
        # Memoization key
        key = (idx, prev_fingers)
        if key in self.memo and self.memo[key] <= total_cost:
            self.saved_states += 1
            return
        self.memo[key] = total_cost

        avaliable_fingers = [x for x in range(1, 6)  if hand.is_available(x,time)]

        for fingers in self._possible_fingerings(len(chord["notes"]), avaliable_fingers):
            chord_cost = chord_complexity(chord["notes"], fingers)
            if prev_notes is None:
                move_cost = 0
            else:
                move_cost = fingering_transition_cost(prev_notes, chord["notes"], prev_fingers, fingers)

            if move_cost > MAX_MOVE_COST:
                continue

            new_cost = total_cost + move_cost + chord_cost

            if new_cost >= self.best_cost:
                continue

            path.append((chord["notes"], fingers))
            new_hand = hand.copy()
            for f in range(len(fingers)):
                new_hand.assign(fingers[f], chord["notes"][f][0], chord["notes"][f][1])
            #print(new_hand.currently_pressed(time))
            self._dfs(idx + 1, chord["notes"], fingers, new_cost, path, new_hand)
            path.pop()

    def solve(self):
        self._dfs(0, None, None, 0, [], HandState())
        return self.best_cost, self.best_path, self.node_visits, self.saved_states


