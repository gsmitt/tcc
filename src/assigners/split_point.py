"""Split-point hand assigner (the project's original, proxy-cost baseline).

Thin wrapper over :func:`src.hand_assigner.assign_voices_to_hands`, which decides
each note's staff with a moving pitch boundary chosen by a Viterbi-style DP whose
emission is an ergonomic *proxy* (a soft feasibility penalty plus a chord-cohesion
penalty) -- see that module's docstring for the full model and sources.

Kept behaviourally identical to the standalone function so it is an unchanged
baseline for the joint assigners to be compared against.
"""

from src.hand_assigner import assign_voices_to_hands
from .base import HandAssigner


class SplitPointAssigner(HandAssigner):
    """Boundary-DP assigner with the proxy emission (the existing baseline)."""

    def __init__(self, voices, **params):
        super().__init__(voices)
        self.params = params

    def assign(self) -> dict:
        return assign_voices_to_hands(self.voices, **self.params)
