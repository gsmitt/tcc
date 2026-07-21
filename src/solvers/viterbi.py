"""Exact forward-DP (Viterbi) solver over the layered fingering trellis.

The cost model is first-order Markov: `fingering_transition_cost` depends only
on two consecutive layers and `chord_complexity` only on the current layer. So
choosing a fingering per layer is a shortest path over a layered DAG, solvable
left-to-right in O(L * S^2) instead of the exponential subtree re-expansion that
the DFS solvers suffer from on large inputs (500+ layers).

A DP state at a layer is `(fingers, held)`:
  - `fingers`  - the fingering tuple assigned to this layer's notes.
  - `held`     - a 5-tuple of release times (finger 1..5), i.e. a hashable
                 snapshot of `HandState`. This carries sustained-note
                 availability exactly, so the result matches the brute-force
                 optimum.

`held` is canonicalized against the time at which it will next be queried (the
next layer's onset): any finger already released by then is free for every later
layer too (onset times only increase), so it is clamped to 0. Without this, paths
that differ only in already-finished notes would form distinct states and the
trellis would re-encode the exponential path space.
"""

import math
from itertools import combinations

from ..costs import (
    MAX_MOVE_COST_HARD,
    chord_complexity,
    fingering_transition_cost,
)
from .base import FingeringSolver, SolverResult


FREE = (0, 0, 0, 0, 0)  # release time per finger when the hand starts empty


class ViterbiSolver(FingeringSolver):
    def __init__(self, layers, hand="R", fingers=(1, 2, 3, 4, 5)):
        super().__init__(layers, hand, fingers)
        self.node_visits = 0
        self.peak_states = 0

    def _available(self, held, time):
        # mirrors HandState.is_available: finger free once its note is released.
        # Only this hand's available fingers are candidates (missing fingers are
        # never offered); the held tuple stays width-5, unused slots stay 0.
        return [f for f in self.fingers if held[f - 1] <= time]

    def _assign(self, held, fingers, notes, query_time):
        # mirrors HandState.copy() + assign: untouched fingers keep their hold.
        # Any finger released by `query_time` (the next onset) is free from then
        # on, so clamp it to 0 to keep functionally-identical states merged.
        new_held = list(held)
        for f, note in zip(fingers, notes):
            new_held[f - 1] = note[1]  # note = (pitch, release_time)
        return tuple(r if r > query_time else 0 for r in new_held)

    def solve(self) -> SolverResult:
        if not self.layers:
            return SolverResult(cost=0, path=[], node_visits=0, extras={})

        # dp: state -> best cost to reach it; parent: (layer_idx, state) -> prev state
        dp = {}
        parent = {}

        first = self.layers[0]
        next_time = self.layers[1]["time"] if len(self.layers) > 1 else math.inf
        for fingers in combinations(self._available(FREE, first["time"]),
                                    len(first["notes"])):
            self.node_visits += 1
            cost = chord_complexity(first["notes"], fingers, self.hand)
            state = (fingers, self._assign(FREE, fingers, first["notes"], next_time))
            if cost < dp.get(state, math.inf):
                dp[state] = cost
                parent[(0, state)] = None
        self.peak_states = max(self.peak_states, len(dp))

        for idx in range(1, len(self.layers)):
            prev_notes = self.layers[idx - 1]["notes"]
            chord = self.layers[idx]
            notes = chord["notes"]
            time = chord["time"]
            n = len(notes)
            next_time = (self.layers[idx + 1]["time"]
                         if idx + 1 < len(self.layers) else math.inf)

            next_dp = {}
            for (prev_fingers, held), prev_cost in dp.items():
                available = self._available(held, time)
                for fingers in combinations(available, n):
                    self.node_visits += 1
                    move_cost = fingering_transition_cost(
                        prev_notes, notes, prev_fingers, fingers, self.hand
                    )
                    if move_cost > MAX_MOVE_COST_HARD:
                        continue

                    new_cost = prev_cost + move_cost + chord_complexity(
                        notes, fingers, self.hand
                    )
                    state = (fingers, self._assign(held, fingers, notes, next_time))
                    if new_cost < next_dp.get(state, math.inf):
                        next_dp[state] = new_cost
                        parent[(idx, state)] = (prev_fingers, held)

            dp = next_dp
            self.peak_states = max(self.peak_states, len(dp))
            if not dp:
                # no playable continuation (e.g. chord needs more fingers than free)
                return SolverResult(
                    cost=math.inf, path=[], node_visits=self.node_visits,
                    extras={"peak_states": self.peak_states, "failed_at": idx},
                )

        # terminate: cheapest state at the last layer, then backtrack
        last_idx = len(self.layers) - 1
        best_state = min(dp, key=dp.get)
        best_cost = dp[best_state]

        path = []
        state = best_state
        for i in range(last_idx, -1, -1):
            fingers = state[0]
            path.append((self.layers[i]["notes"], fingers))
            state = parent[(i, state)]
        path.reverse()

        return SolverResult(
            cost=best_cost,
            path=path,
            node_visits=self.node_visits,
            extras={"peak_states": self.peak_states},
        )
