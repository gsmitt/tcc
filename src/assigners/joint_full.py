"""Joint hand assigner, full coupling: one product-state Viterbi trellis.

This fuses the two dynamic programs the rest of the pipeline runs *separately* --
the split-point hand DP (:mod:`src.hand_assigner`) and the per-hand fingering
Viterbi (:mod:`src.solvers.viterbi`) -- into a single trellis, so the hand
boundaries at every onset are chosen against the **realised fingering cost** they
force on *every* hand, including the cross-onset cost of moving fingers between
consecutive chords.  That coupling -- hand assignment and fingering optimised
jointly rather than in sequence against a proxy -- is this work's contribution.

Generalised to ``H`` hands.  The hands are ordered low -> high by register, and
``H - 1`` pitch boundaries ``b_1 <= b_2 <= ... <= b_{H-1}`` partition each onset
into ``H`` register bands: band 0 is the notes below ``b_1``, band ``j`` the notes
in ``[b_j, b_{j+1})``, band ``H-1`` the notes at/above ``b_{H-1}``.  For the
default two-hand config this is exactly the original single moving boundary
(``b_1`` = the split point, band 0 = left hand, band 1 = right hand).

A trellis state at an onset is ``(b_tuple, hand_subs)``:

  * ``b_tuple``   -- the ``H-1`` boundary indices (into the pitch-candidate axis),
                     non-decreasing.
  * ``hand_subs`` -- one ``(fingers, held)`` per band, exactly the fingering
                     Viterbi state (:mod:`src.solvers.viterbi`): ``fingers`` the
                     tuple assigned to that band's notes and ``held`` a 5-tuple of
                     per-finger release times, clamped against the next onset so
                     functionally identical states merge.  Each band uses its
                     hand's ``side`` (keyboard geometry) and available ``fingers``
                     (so a hand with missing fingers never offers them).

The step cost adds, for each band, ``chord_complexity`` +
``fingering_transition_cost`` (the same two terms the solvers minimise), plus the
boundary hysteresis ``smooth_weight * sum_j |b_j - b_j_prev|``.  Each boundary is
seeded at the midpoint of its two adjacent hands' registers.

Tractability.  A ``beam`` keeps only the K cheapest states per onset, and a
``boundary_window`` restricts each ``b_j`` to within W semitones of its previous
value (its seed at the first onset).  Only the boundary path is returned -- the
fingering computed here scores the split and is then discarded, leaving the
downstream per-hand solver (the same Viterbi) to produce the published fingering,
so the pipeline contract is unchanged.

Cost model: Parncutt et al. 1997 (via :mod:`src.costs`); hand separation in the
spirit of the HMM of Nakamura, Saito & Yoshii, Information Sciences 517 (2020).
"""

import math
from bisect import bisect_left
from functools import lru_cache
from itertools import combinations, product

from src.costs import (
    MAX_MOVE_COST_HARD,
    chord_complexity,
    fingering_transition_cost,
)
from src.hands import DEFAULT_HANDS
from .base import HandAssigner, onsets_with_release

FREE = (0, 0, 0, 0, 0)   # release time per finger when a hand starts empty


@lru_cache(maxsize=None)
def _chord_cost(notes, fingers, hand):
    # chord_complexity depends only on (notes, fingers, hand), not on held state,
    # so the same value is recomputed across every beam state sharing a split.
    # Cache it (notes is a tuple of (pitch, release) -> hashable).
    return chord_complexity(list(notes), fingers, hand)


def _available(held, time, fingers):
    # mirrors HandState.is_available: a finger is free once its note is released.
    # Only this hand's fingers are candidates (missing fingers never offered).
    return [f for f in fingers if held[f - 1] <= time]


def _assign(held, fingers, notes, query_time):
    # mirrors the Viterbi solver: untouched fingers keep their hold; any finger
    # released by query_time (the next onset) is free thereafter, so clamp to 0
    # to merge functionally-identical states.
    new_held = list(held)
    for f, note in zip(fingers, notes):
        new_held[f - 1] = note[1]            # note = (pitch, release_time)
    return tuple(r if r > query_time else 0 for r in new_held)


class JointFullAssigner(HandAssigner):
    def __init__(self, voices, hands=DEFAULT_HANDS,
                 smooth_weight=0.6,
                 beam=32,
                 boundary_window=6):
        super().__init__(voices, hands)
        self.smooth_weight = smooth_weight
        self.beam = beam
        self.boundary_window = boundary_window

    def assign(self) -> dict:
        onsets = onsets_with_release(self.voices)
        if not onsets:
            return {}

        hands = self.hands
        H = len(hands)
        nb = H - 1                       # number of pitch boundaries
        sides = [h.side for h in hands]
        fingerset = [h.fingers for h in hands]

        times = [t for _li, t, _notes in onsets]
        note_lists = [[(p, e) for p, e, _ni in notes]
                      for _li, _t, notes in onsets]
        all_pitches = [p for notes in note_lists for p, _e in notes]
        lo, hi = min(all_pitches), max(all_pitches)
        boundaries = [lo - 0.5 + i for i in range(hi - lo + 2)]
        nbnd = len(boundaries)

        # Per onset and boundary index, how many notes fall below boundaries[c]
        # (notes are pitch-sorted ascending). A b_tuple then slices the note list
        # into H contiguous bands in O(H).
        cuts = []
        for notes in note_lists:
            pitches = [p for p, _e in notes]
            cuts.append([bisect_left(pitches, b) for b in boundaries])

        # If there is only one hand there are no boundaries: every note is band 0.
        if nb == 0:
            return self._labels(onsets, boundaries, [()] * len(onsets))

        # Per-boundary seed index: midpoint of the two adjacent hands' registers.
        seed_idx = []
        for j in range(nb):
            s = (hands[j].register + hands[j + 1].register) / 2.0
            seed_idx.append(min(range(nbnd), key=lambda i: abs(boundaries[i] - s)))

        sw = self.smooth_weight
        W = self.boundary_window

        def bands_of(notes, cut_row, b_tuple):
            """Slice an onset's pitch-sorted notes into H bands by b_tuple."""
            ps = [0] + [cut_row[c] for c in b_tuple] + [len(notes)]
            return [notes[ps[j]:ps[j + 1]] for j in range(H)]

        def b_tuples(centers):
            """Non-decreasing boundary index tuples, each within W of its center
            (full range when W is None or ``centers`` is None)."""
            if W is None or centers is None:
                wins = [(0, nbnd - 1)] * nb
            else:
                wins = [(max(0, c - W), min(nbnd - 1, c + W)) for c in centers]

            def rec(j, lo_bound):
                if j == nb:
                    yield ()
                    return
                start = max(wins[j][0], lo_bound)
                for c in range(start, wins[j][1] + 1):
                    for rest in rec(j + 1, c):
                        yield (c,) + rest

            yield from rec(0, 0)

        def hand_steps(notes, held, prev_notes, prev_fingers, side, fingers):
            """Yield ``(fingers, step_cost, new_held)`` for one band at an onset.

            ``step_cost`` is ``chord_complexity + fingering_transition_cost`` (the
            transition omitted at the first onset, where ``prev_fingers`` is None).
            Branches whose transition exceeds the hard limit are pruned.
            """
            available = _available(held, time, fingers)
            n = len(notes)
            if n > len(available):
                return                              # hand cannot hold this onset
            notes_t = tuple(notes)
            for fg in combinations(available, n):
                if prev_fingers is None:
                    move = 0.0
                else:
                    move = fingering_transition_cost(
                        prev_notes, notes, prev_fingers, fg, side)
                    if move > MAX_MOVE_COST_HARD:
                        continue
                cost = _chord_cost(notes_t, fg, side) + move
                yield fg, cost, _assign(held, fg, notes, next_time)

        def expand(b_tuple, bands, prev_bands, prev_subs):
            """Yield ``(hand_subs, cost)`` over the product of per-band fingerings.

            ``prev_bands``/``prev_subs`` are None at the first onset.
            """
            opts = []
            for j in range(H):
                pn = prev_bands[j] if prev_bands is not None else None
                pf = prev_subs[j][0] if prev_subs is not None else None
                band_opts = list(hand_steps(bands[j], prev_subs[j][1] if prev_subs is not None else FREE,
                                            pn, pf, sides[j], fingerset[j]))
                if not band_opts:
                    return                          # a band cannot be held: prune
                opts.append(band_opts)
            for combo in product(*opts):
                subs = tuple((c[0], c[2]) for c in combo)
                cost = sum(c[1] for c in combo)
                yield subs, cost

        # dp: state -> best cost; parent: (onset_idx, state) -> previous state.
        # state = (b_tuple, hand_subs); hand_subs = ((fingers, held), ... x H).
        time = times[0]
        next_time = times[1] if len(onsets) > 1 else math.inf
        dp = {}
        parent = {}
        for b_tuple in b_tuples(None):       # first onset: full boundary range
            bands = bands_of(note_lists[0], cuts[0], b_tuple)
            base = sw * sum(abs(boundaries[c] - boundaries[s])
                            for c, s in zip(b_tuple, seed_idx))
            for subs, cost in expand(b_tuple, bands, None, None):
                state = (b_tuple, subs)
                total = base + cost
                if total < dp.get(state, math.inf):
                    dp[state] = total
                    parent[(0, state)] = None
        dp = self._beam(dp)

        for t in range(1, len(onsets)):
            time = times[t]
            next_time = times[t + 1] if t + 1 < len(onsets) else math.inf
            prev_notes = note_lists[t - 1]
            prev_cut = cuts[t - 1]
            next_dp = {}
            for (pb_tuple, psubs), pcost in dp.items():
                prev_bands = bands_of(prev_notes, prev_cut, pb_tuple)
                for b_tuple in b_tuples(pb_tuple):
                    bands = bands_of(note_lists[t], cuts[t], b_tuple)
                    smooth = sw * sum(abs(boundaries[c] - boundaries[pc])
                                      for c, pc in zip(b_tuple, pb_tuple))
                    for subs, cost in expand(b_tuple, bands, prev_bands, psubs):
                        state = (b_tuple, subs)
                        total = pcost + smooth + cost
                        if total < next_dp.get(state, math.inf):
                            next_dp[state] = total
                            parent[(t, state)] = (pb_tuple, psubs)
            if not next_dp:
                # No playable continuation at all (every split needs more fingers
                # than free). Fall back to the boundaries chosen so far.
                return self._labels(onsets, boundaries,
                                    self._backtrack(dp, parent, t - 1), tail_from=t)
            dp = self._beam(next_dp)

        chosen = self._backtrack(dp, parent, len(onsets) - 1)
        return self._labels(onsets, boundaries, chosen)

    def _beam(self, dp):
        if self.beam is None or len(dp) <= self.beam:
            return dp
        keep = sorted(dp.items(), key=lambda kv: kv[1])[:self.beam]
        return dict(keep)

    def _backtrack(self, dp, parent, last_t):
        """Recover the boundary tuple chosen at each onset 0..last_t."""
        state = min(dp, key=dp.get)
        chosen = [()] * (last_t + 1)
        for t in range(last_t, -1, -1):
            chosen[t] = state[0]
            prev = parent[(t, state)]
            if prev is None:
                break
            state = prev
        return chosen

    def _labels(self, onsets, boundaries, chosen, tail_from=None):
        """Map chosen boundary tuples to per-note hand labels.

        A note's band is the count of chosen boundaries it lies at/above; the band
        index selects the hand (hands are ordered low -> high). If ``tail_from`` is
        set, onsets at/after it reuse the last decided boundaries (best effort).
        """
        labels = {}
        last_b = chosen[-1] if chosen else ()
        for t, (layer_idx, _start, notes) in enumerate(onsets):
            if tail_from is not None and t >= tail_from:
                b_tuple = last_b
            else:
                b_tuple = chosen[t]
                last_b = b_tuple
            bvals = [boundaries[c] for c in b_tuple]
            for pitch, _end, note_idx in notes:
                band = sum(1 for bv in bvals if pitch >= bv)
                labels[(layer_idx, note_idx)] = self.hands[band].name
        return labels
