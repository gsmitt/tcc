"""Joint hand assigner, full coupling: one product-state Viterbi trellis.

This fuses the two dynamic programs the rest of the pipeline runs *separately* --
the split-point hand DP (:mod:`src.hand_assigner`) and the per-hand fingering
Viterbi (:mod:`src.solvers.viterbi`) -- into a single trellis, so the hand
boundary at every onset is chosen against the **realised fingering cost** it
forces on *both* hands, including the cross-onset cost of moving fingers between
consecutive chords.  That coupling -- hand assignment and fingering optimised
jointly rather than in sequence against a proxy -- is this work's contribution.

A trellis state at an onset is ``(b_idx, lh_sub, rh_sub)``:

  * ``b_idx``  -- the pitch boundary; notes below it are the left hand, the rest
                  the right.
  * ``lh_sub`` / ``rh_sub`` -- ``(fingers, held)`` per hand, exactly the fingering
                  Viterbi state (:mod:`src.solvers.viterbi`): ``fingers`` is the
                  tuple assigned to that hand's notes at this onset and ``held`` a
                  5-tuple of per-finger release times, clamped against the next
                  onset so functionally identical states merge.

The step cost from a state to the next adds, for each hand,
``chord_complexity`` + ``fingering_transition_cost`` (the same two terms the
solvers minimise), plus the boundary hysteresis ``smooth_weight * |b - b_prev|``
seeded at ``seed_boundary``.  The previous hand's notes -- needed by the
transition term -- are recovered from the previous onset split at the previous
state's ``b_idx`` (the boundary lives in the state), so notes need not be stored.

Tractability.  The product state space is
``O(boundaries x lh_states x rh_states)``; a ``beam`` keeps only the K cheapest
states per onset, and a ``boundary_window`` restricts ``b`` to within W semitones
of the previous boundary (``smooth_weight`` already discourages jumps).  Overall
``O(L * B * beam * combos^2)``.  ``boundary_window`` defaults to 6 because the
exact search (``None``) is ~90 s on the whole movement with no feedback, while
W=4 is ~4x faster for 99.4% identical labels on mond_1; pass ``None`` for the
exact optimum.  Only the boundary path is returned -- the fingering computed here scores
the split and is then discarded, leaving the downstream per-hand solver (the same
Viterbi) to produce the published fingering, so the pipeline contract is unchanged.

Cost model: Parncutt et al. 1997 (via :mod:`src.costs`); hand separation in the
spirit of the HMM of Nakamura, Saito & Yoshii, Information Sciences 517 (2020).
"""

import math
from functools import lru_cache
from itertools import combinations

from src.costs import (
    MAX_MOVE_COST_HARD,
    chord_complexity,
    fingering_transition_cost,
)
from .base import HandAssigner, onsets_with_release

FREE = (0, 0, 0, 0, 0)   # release time per finger when a hand starts empty


@lru_cache(maxsize=None)
def _chord_cost(notes, fingers, hand):
    # chord_complexity depends only on (notes, fingers, hand), not on held state,
    # so the same value is recomputed across every beam state sharing a split.
    # Cache it (notes is a tuple of (pitch, release) -> hashable).
    return chord_complexity(list(notes), fingers, hand)


def _available(held, time):
    # mirrors HandState.is_available: a finger is free once its note is released
    return [f for f in range(1, 6) if held[f - 1] <= time]


def _assign(held, fingers, notes, query_time):
    # mirrors the Viterbi solver: untouched fingers keep their hold; any finger
    # released by query_time (the next onset) is free thereafter, so clamp to 0
    # to merge functionally-identical states.
    new_held = list(held)
    for f, note in zip(fingers, notes):
        new_held[f - 1] = note[1]            # note = (pitch, release_time)
    return tuple(r if r > query_time else 0 for r in new_held)


class JointFullAssigner(HandAssigner):
    def __init__(self, voices,
                 smooth_weight=0.6,
                 seed_boundary=60.0,
                 beam=32,
                 boundary_window=6):
        super().__init__(voices)
        self.smooth_weight = smooth_weight
        self.seed_boundary = seed_boundary
        self.beam = beam
        self.boundary_window = boundary_window

    def assign(self) -> dict:
        onsets = onsets_with_release(self.voices)
        if not onsets:
            return {}

        times = [t for _li, t, _notes in onsets]
        note_lists = [[(p, e) for p, e, _ni in notes]
                      for _li, _t, notes in onsets]
        all_pitches = [p for notes in note_lists for p, _e in notes]
        lo, hi = min(all_pitches), max(all_pitches)
        boundaries = [lo - 0.5 + i for i in range(hi - lo + 2)]

        # Precompute, per onset and boundary, the (left, right) note split.
        splits = []
        for notes in note_lists:
            row = []
            for b in boundaries:
                left = [ne for ne in notes if ne[0] < b]
                right = [ne for ne in notes if ne[0] >= b]
                row.append((left, right))
            splits.append(row)

        sw = self.smooth_weight
        W = self.boundary_window

        def b_candidates(prev_b_idx):
            if W is None or prev_b_idx is None:
                return range(len(boundaries))
            lo_i = max(0, prev_b_idx - W)
            hi_i = min(len(boundaries) - 1, prev_b_idx + W)
            return range(lo_i, hi_i + 1)

        def hand_steps(notes, held, prev_notes, prev_fingers, hand):
            """Yield ``(fingers, step_cost, new_held)`` for one hand at an onset.

            ``step_cost`` is ``chord_complexity + fingering_transition_cost`` (the
            transition omitted at the first onset, where ``prev_fingers`` is None).
            Branches whose transition exceeds the hard limit are pruned, as in the
            fingering Viterbi.
            """
            available = _available(held, time)
            n = len(notes)
            if n > len(available):
                return                              # hand cannot hold this onset
            notes_t = tuple(notes)
            for fingers in combinations(available, n):
                if prev_fingers is None:
                    move = 0.0
                else:
                    move = fingering_transition_cost(
                        prev_notes, notes, prev_fingers, fingers, hand)
                    if move > MAX_MOVE_COST_HARD:
                        continue
                cost = _chord_cost(notes_t, fingers, hand) + move
                yield fingers, cost, _assign(held, fingers, notes, next_time)

        # dp: state -> best cost; parent: (onset_idx, state) -> previous state.
        # state = (b_idx, (lh_fingers, lh_held), (rh_fingers, rh_held)).
        time = times[0]
        next_time = times[1] if len(onsets) > 1 else math.inf
        dp = {}
        parent = {}
        for b_idx in b_candidates(None):
            left, right = splits[0][b_idx]
            base = sw * abs(boundaries[b_idx] - self.seed_boundary)
            for lf, lc, lh in hand_steps(left, FREE, None, None, "L"):
                for rf, rc, rh in hand_steps(right, FREE, None, None, "R"):
                    state = (b_idx, (lf, lh), (rf, rh))
                    cost = base + lc + rc
                    if cost < dp.get(state, math.inf):
                        dp[state] = cost
                        parent[(0, state)] = None
        dp = self._beam(dp)

        for t in range(1, len(onsets)):
            time = times[t]
            next_time = times[t + 1] if t + 1 < len(onsets) else math.inf
            prev_notes = note_lists[t - 1]
            next_dp = {}
            for (pb_idx, (plf, plh), (prf, prh)), pcost in dp.items():
                prev_left, prev_right = splits[t - 1][pb_idx]
                bp = boundaries[pb_idx]
                for b_idx in b_candidates(pb_idx):
                    left, right = splits[t][b_idx]
                    smooth = sw * abs(boundaries[b_idx] - bp)
                    for lf, lc, lh in hand_steps(left, plh, prev_left, plf, "L"):
                        for rf, rc, rh in hand_steps(right, prh, prev_right, prf, "R"):
                            state = (b_idx, (lf, lh), (rf, rh))
                            cost = pcost + smooth + lc + rc
                            if cost < next_dp.get(state, math.inf):
                                next_dp[state] = cost
                                parent[(t, state)] = (pb_idx, (plf, plh), (prf, prh))
            if not next_dp:
                # No playable continuation at all (every split needs more fingers
                # than free). Fall back to the boundary chosen so far for the rest.
                return self._labels(onsets, boundaries, self._backtrack(
                    dp, parent, t - 1), tail_from=t)
            dp = self._beam(next_dp)

        chosen = self._backtrack(dp, parent, len(onsets) - 1)
        return self._labels(onsets, boundaries, chosen)

    def _beam(self, dp):
        if self.beam is None or len(dp) <= self.beam:
            return dp
        keep = sorted(dp.items(), key=lambda kv: kv[1])[:self.beam]
        return dict(keep)

    def _backtrack(self, dp, parent, last_t):
        """Recover the boundary index chosen at each onset 0..last_t."""
        state = min(dp, key=dp.get)
        chosen = [0] * (last_t + 1)
        for t in range(last_t, -1, -1):
            chosen[t] = state[0]
            prev = parent[(t, state)]
            if prev is None:
                break
            state = prev
        return chosen

    def _labels(self, onsets, boundaries, chosen, tail_from=None):
        """Map chosen boundary indices to per-note hand labels.

        If ``tail_from`` is set, onsets at/after it had no playable continuation;
        they reuse the last decided boundary (best effort, the downstream solver
        reports the real infeasibility).
        """
        labels = {}
        last_b_idx = chosen[-1] if chosen else 0
        for t, (layer_idx, _start, notes) in enumerate(onsets):
            if tail_from is not None and t >= tail_from:
                b_idx = last_b_idx
            else:
                b_idx = chosen[t]
                last_b_idx = b_idx
            b = boundaries[b_idx]
            for pitch, _end, note_idx in notes:
                labels[(layer_idx, note_idx)] = "L" if pitch < b else "R"
        return labels
