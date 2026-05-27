"""IDA*-style DFS solver with an incremental difficulty threshold.

Starts with `max_cost = 1` and grows the per-move difficulty cap each
iteration. Branches whose move cost exceeds the current cap are deferred
to a frontier for the next pass. The first iteration that finds any
feasible solution wins.
"""

import math
from itertools import combinations

from ..costs import chord_complexity, fingering_transition_cost
from ..hand import HandState
from .base import FingeringSolver, SolverResult


MAX_THRESHOLD = 10


class GreedySolver(FingeringSolver):
    def __init__(self, layers, hand="R"):
        super().__init__(layers, hand)
        self.best_cost = math.inf
        self.best_path = []
        self.node_visits = 0

    def _possible_fingerings(self, n, fingers):
        return list(combinations(fingers, n))

    def _dfs(self, idx, prev_notes, prev_fingers, total_cost, path,
             hand_state, max_cost, next_frontier):
        self.node_visits += 1

        if idx == len(self.layers):
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_path = path[:]
            return

        chord = self.layers[idx]
        time = chord["time"]
        available_fingers = [x for x in range(1, 6) if hand_state.is_available(x, time)]

        for fingers in self._possible_fingerings(len(chord["notes"]), available_fingers):
            chord_cost = chord_complexity(chord["notes"], fingers, self.hand)
            if prev_notes is None:
                move_cost = 0
            else:
                move_cost = fingering_transition_cost(
                    prev_notes, chord["notes"], prev_fingers, fingers, self.hand
                )

            if move_cost > max_cost:
                next_frontier.append((
                    idx, prev_notes, prev_fingers, total_cost, path[:], hand_state.copy()
                ))
                continue

            new_cost = total_cost + move_cost + chord_cost
            if new_cost >= self.best_cost:
                continue

            path.append((chord["notes"], fingers))
            new_hand_state = hand_state.copy()
            for f in range(len(fingers)):
                new_hand_state.assign(fingers[f], chord["notes"][f][0], chord["notes"][f][1])
            self._dfs(idx + 1, chord["notes"], fingers, new_cost, path,
                      new_hand_state, max_cost, next_frontier)
            path.pop()

    def solve(self) -> SolverResult:
        max_cost = 1
        frontier = [(0, None, None, 0, [], HandState())]

        while max_cost <= MAX_THRESHOLD:
            next_frontier = []
            for state in frontier:
                self._dfs(*state, max_cost, next_frontier)
                if self.best_cost < math.inf:
                    return SolverResult(
                        cost=self.best_cost,
                        path=self.best_path,
                        node_visits=self.node_visits,
                        extras={"final_threshold": max_cost},
                    )
            frontier = next_frontier
            max_cost += 1

        return SolverResult(
            cost=self.best_cost,
            path=self.best_path,
            node_visits=self.node_visits,
            extras={"final_threshold": max_cost},
        )
