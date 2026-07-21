"""Split-point hand assigner (the project's original, proxy-cost baseline).

Thin wrapper over :func:`src.hand_assigner.assign_voices_to_hands`, which decides
each note's staff with a moving pitch boundary chosen by a Viterbi-style DP whose
emission is an ergonomic *proxy* (a soft feasibility penalty plus a chord-cohesion
penalty) -- see that module's docstring for the full model and sources.

Kept behaviourally identical to the standalone function so it is an unchanged
baseline for the joint assigners to be compared against.
"""

from src.hand_assigner import assign_voices_to_hands
from src.hands import DEFAULT_HANDS
from .base import HandAssigner


class SplitPointAssigner(HandAssigner):
    """Boundary-DP assigner with the proxy emission (the existing baseline).

    A two-hand reference only (the proxy emission has no per-hand finger model);
    use joint-full for more than two hands.
    """

    def __init__(self, voices, hands=DEFAULT_HANDS, **params):
        super().__init__(voices, hands)
        if len(self.hands) != 2:
            raise ValueError("split is a two-hand baseline; use joint-full for "
                             "more than two hands")
        params.setdefault("seed_boundary",
                          (self.hands[0].register + self.hands[1].register) / 2.0)
        self.params = params

    def assign(self) -> dict:
        low, high = self.hands
        labels = assign_voices_to_hands(self.voices, **self.params)
        return {k: (low.name if v == "L" else high.name) for k, v in labels.items()}
