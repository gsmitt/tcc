"""Fixed-boundary hand assigner: the trivial baseline.

Every note below a fixed pitch goes to the lower hand, every other note to the
upper one; with the default hands the boundary is middle C, the midpoint of their
reference positions (F3 and G4).  With ``H`` hands, boundary ``j`` is the midpoint
of hands ``j`` and ``j + 1``.  Nothing is optimised: the variant measures how much
of the hand accuracy any method gets for free, so the gains of the others can be
read against it.
"""

from src.hands import DEFAULT_HANDS
from .base import HandAssigner


class FixedSplitAssigner(HandAssigner):
    def __init__(self, layers, hands=DEFAULT_HANDS):
        super().__init__(layers, hands)
        self.boundaries = [(a.register + b.register) / 2.0
                           for a, b in zip(self.hands, self.hands[1:])]

    def assign(self) -> dict:
        labels = {}
        for li, layer in enumerate(self.layers):
            for ni, (pitch, _end) in enumerate(layer["notes"]):
                band = sum(1 for b in self.boundaries if pitch >= b)
                labels[(li, ni)] = self.hands[band].name
        return labels
