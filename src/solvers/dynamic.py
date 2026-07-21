"""DFS solver with memoization over (layer_idx, prev_fingers)."""

import math
from itertools import combinations

from ..costs import (
    MAX_MOVE_COST_HARD,
    chord_complexity,
    fingering_transition_cost,
)
from ..hand import HandState
from .base import FingeringSolver, SolverResult


class DynamicSolver(FingeringSolver):
    def __init__(self, layers, hand="R", fingers=(1, 2, 3, 4, 5)):
        super().__init__(layers, hand, fingers)
        self.best_cost = math.inf
        self.best_path = []
        self.node_visits = 0
        self.saved_states = 0
        self.memo = {}

    def _possible_fingerings(self, n, fingers):
        return list(combinations(fingers, n))

    def _dfs(self, idx, prev_notes, prev_fingers, total_cost, path, hand_state):
        self.node_visits += 1

        if idx == len(self.layers):
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_path = path[:]
            return

        chord = self.layers[idx]
        time = chord["time"]

        key = (idx, prev_fingers)
        if key in self.memo and self.memo[key] <= total_cost:
            self.saved_states += 1
            return
        self.memo[key] = total_cost

        available_fingers = [x for x in self.fingers if hand_state.is_available(x, time)]

        for fingers in self._possible_fingerings(len(chord["notes"]), available_fingers):
            chord_cost = chord_complexity(chord["notes"], fingers, self.hand)
            if prev_notes is None:
                move_cost = 0
            else:
                move_cost = fingering_transition_cost(
                    prev_notes, chord["notes"], prev_fingers, fingers, self.hand
                )

            if move_cost > MAX_MOVE_COST_HARD:
                continue

            new_cost = total_cost + move_cost + chord_cost

            if new_cost >= self.best_cost:
                continue

            path.append((chord["notes"], fingers))
            new_hand_state = hand_state.copy()
            for f in range(len(fingers)):
                new_hand_state.assign(fingers[f], chord["notes"][f][0], chord["notes"][f][1])
            self._dfs(idx + 1, chord["notes"], fingers, new_cost, path, new_hand_state)
            path.pop()

    def solve(self) -> SolverResult:
        self._dfs(0, None, None, 0, [], HandState(self.fingers))
        return SolverResult(
            cost=self.best_cost,
            path=self.best_path,
            node_visits=self.node_visits,
            extras={"saved_states": self.saved_states},
        )
