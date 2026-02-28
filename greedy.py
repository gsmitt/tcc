import math
from itertools import combinations
import random

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
    }
}

MAX_MOVE_COST = 10

def finger_move_cost(note_prev, note_curr, finger_prev, finger_curr):
    note_span = abs(note_curr - note_prev)
    if note_curr < note_prev:
        key = f"{finger_curr}-{finger_prev}"
    else:
        key = f"{finger_prev}-{finger_curr}"
    finger_combo = DISTANCE_COSTS["w-w"].get(key, None)
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

def chord_complexity(notes):
    return 0 if len(notes) == 1 else len(notes) - 1


class PianoFingeringDFS:
    def __init__(self, chords):
        self.chords = [sorted(c) for c in chords]
        self.best_cost = math.inf
        self.best_path = []
        self.node_visits = 0

    def _possible_fingerings(self, n):
        return list(combinations(range(1, 6), n))

    def _dfs(self, idx, prev_notes, prev_fingers, total_cost, path, max_cost, next_frontier):
        self.node_visits += 1

        if idx == len(self.chords):
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_path = path[:]
            return

        chord = self.chords[idx]
        chord_cost = chord_complexity(chord)

        for fingers in self._possible_fingerings(len(chord)):
            if prev_notes is None:
                move_cost = 0
            else:
                move_cost = fingering_transition_cost(prev_notes, chord, prev_fingers, fingers)

            if move_cost > max_cost:
                # store for next iteration
                next_frontier.append((idx, prev_notes, prev_fingers, total_cost, path[:]))
                continue

            new_cost = total_cost + move_cost + chord_cost

            if new_cost >= self.best_cost:
                continue

            path.append((chord, fingers))
            self._dfs(idx + 1, chord, fingers, new_cost, path, max_cost, next_frontier)
            path.pop()

    def solve_incremental(self):
        max_cost = 1
        frontier = [(0, None, None, 0, [])]

        while max_cost <= MAX_MOVE_COST:
            print(f"Trying with MAX_MOVE_COST={max_cost}")
            next_frontier = []
            for state in frontier:
                self._dfs(*state, max_cost, next_frontier)
                if self.best_cost < math.inf:
                    print(f"Found solution at difficulty {max_cost}")
                    return self.best_cost, self.best_path, self.node_visits
            frontier = next_frontier
            max_cost += 1

        return self.best_cost, self.best_path, self.node_visits


def main():
    chords = [[random.randint(60, 70)] for i in range(30)]
    solver = PianoFingeringDFS(chords)
    cost, path, visits = solver.solve_incremental()
    print("Best cost:", cost)
    print("Path:")
    for step in path:
        print(" ", step)
    print("Node visits:", visits)


if __name__ == "__main__":
    main()
