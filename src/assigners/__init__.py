"""Hand-assigner registry — pick an assigner by name.

Mirrors :mod:`src.solvers`: every assigner implements :class:`HandAssigner` and
returns ``{(layer_idx, note_idx): "L"|"R"}``, so callers swap the staff-split
algorithm by name.  ``split_layers_by_hand`` (the partition step that consumes the
labels) is shared and re-exported from :mod:`src.hand_assigner`.

  * ``split``       -- the original boundary DP with the ergonomic *proxy* emission.
  * ``joint-local`` -- boundary DP whose emission is the real per-onset chord cost.
  * ``joint-full``  -- one trellis fusing the hand boundary and the fingering
                       Viterbi (cross-onset finger cost), the full coupling.
"""

from src.hand_assigner import split_layers_by_hand, split_layers_by_hands
from .base import HandAssigner
from .split_point import SplitPointAssigner
from .joint_local import JointLocalAssigner
from .joint_full import JointFullAssigner


ASSIGNERS = {
    "split":       SplitPointAssigner,
    "joint-local": JointLocalAssigner,
    "joint-full":  JointFullAssigner,
}


def get_assigner(name):
    if name not in ASSIGNERS:
        raise ValueError(f"Unknown assigner {name!r}. Available: {list(ASSIGNERS)}")
    return ASSIGNERS[name]
