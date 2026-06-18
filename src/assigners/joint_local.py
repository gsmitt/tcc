"""Joint hand assigner, local coupling: boundary DP with real chord cost.

Same Viterbi-style split-point DP as :mod:`src.hand_assigner` -- a moving pitch
boundary ``b`` per onset, with a hysteresis term ``smooth_weight * |b - b_prev|``
seeded at ``seed_boundary`` -- but the per-onset *emission* is no longer the
feasibility/cohesion proxy.  It is the **real ergonomic cost** of playing the
onset on the two hands the boundary creates:

    emission(onset, b) =   min_fingers chord_complexity(left,  fingers, "L")
                         + min_fingers chord_complexity(right, fingers, "R")

with ``left`` the notes below ``b`` and ``right`` those at/above it (a hand of
more than five notes is infeasible -> ``FEAS_PENALTY``).  So the boundary is
chosen because it yields a cheaper *fingering*, not because it looks balanced --
the project's hand/finger coupling, here in its cheap, single-onset form: the
emission ignores cross-onset finger held-state (that is :mod:`joint_full`).  This
keeps the DP as light as the proxy version, so it is safe inside the reducer loop.

Cost model and the boundary-DP structure are unchanged from their sources
(Parncutt et al. 1997 for the ergonomic cost; the single-boundary hand split is
the simplified analogue of the HMM hand separation of Nakamura, Saito & Yoshii,
Information Sciences 517, 2020).  Driving the boundary by the realised fingering
cost is this work's contribution.
"""

from itertools import combinations

from src.costs import chord_complexity
from .base import HandAssigner, onsets_with_release

FEAS_PENALTY = 1000.0   # a hand that cannot hold the notes (more than five keys)


def _hand_cost(notes, hand):
    """Cheapest ``chord_complexity`` over finger assignments for one hand.

    ``notes`` is a list of ``(pitch, end)``. Empty hand costs 0; a hand needing
    more than five fingers is infeasible.
    """
    n = len(notes)
    if n == 0:
        return 0.0
    if n > 5:
        return FEAS_PENALTY
    best = min(chord_complexity(notes, fingers, hand)
               for fingers in combinations(range(1, 6), n))
    return float(best)


class JointLocalAssigner(HandAssigner):
    def __init__(self, voices,
                 smooth_weight=0.6,
                 seed_boundary=60.0):
        super().__init__(voices)
        self.smooth_weight = smooth_weight
        self.seed_boundary = seed_boundary

    def assign(self) -> dict:
        onsets = onsets_with_release(self.voices)
        if not onsets:
            return {}

        # notes per onset as (pitch, end), ascending by pitch (onsets already are)
        note_lists = [[(p, e) for p, e, _ni in notes] for _li, _t, notes in onsets]
        all_pitches = [p for notes in note_lists for p, _e in notes]
        lo, hi = min(all_pitches), max(all_pitches)
        # Half-integer candidates from just below the lowest pitch to just above
        # the highest, so "all right" (b <= lo) and "all left" (b > hi) are reachable.
        boundaries = [lo - 0.5 + i for i in range(hi - lo + 2)]

        emit_cache = {}

        def emit(t, b):
            key = (t, b)
            if key not in emit_cache:
                notes = note_lists[t]
                left = [ne for ne in notes if ne[0] < b]
                right = [ne for ne in notes if ne[0] >= b]
                emit_cache[key] = _hand_cost(left, "L") + _hand_cost(right, "R")
            return emit_cache[key]

        # Forward pass. dp[k] = best cost of reaching this onset with boundaries[k];
        # back[t-1][k] = previous onset's boundary index chosen to reach k here.
        sw = self.smooth_weight
        dp = [emit(0, b) + sw * abs(b - self.seed_boundary) for b in boundaries]
        back = []
        for t in range(1, len(onsets)):
            new_dp = [0.0] * len(boundaries)
            choice = [0] * len(boundaries)
            for ki, b in enumerate(boundaries):
                best_c, best_j = None, 0
                for kj, bp in enumerate(boundaries):
                    c = dp[kj] + sw * abs(b - bp)
                    if best_c is None or c < best_c:
                        best_c, best_j = c, kj
                new_dp[ki] = best_c + emit(t, b)
                choice[ki] = best_j
            dp = new_dp
            back.append(choice)

        # Backtrack the optimal boundary at every onset.
        k = min(range(len(boundaries)), key=lambda i: dp[i])
        chosen = [0] * len(onsets)
        chosen[-1] = k
        for t in range(len(onsets) - 1, 0, -1):
            k = back[t - 1][k]
            chosen[t - 1] = k

        labels = {}
        for t, (layer_idx, _start, notes) in enumerate(onsets):
            b = boundaries[chosen[t]]
            for pitch, _end, note_idx in notes:
                labels[(layer_idx, note_idx)] = "L" if pitch < b else "R"
        return labels
