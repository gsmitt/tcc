"""Configurable hand model — the spec the whole pipeline is parameterised on.

Historically the pipeline hardcoded exactly two hands ("L"/"R") with all five
fingers each. A :class:`Hand` makes both assumptions configurable:

  * **missing fingers** -- a hand whose ``fingers`` is a subset of ``{1..5}``
    (e.g. an injured hand without the ring finger). The cost model in
    :mod:`src.costs` is unchanged: a missing finger is simply never offered as a
    candidate, and the ergonomic tables (keyed by finger *pairs*) are queried only
    for the fingers that remain.
  * **duets / N hands** -- the pipeline takes an *ordered list* of hands rather
    than a fixed (L, R) pair, so two players (four hands) -- or any register
    partition -- are expressed as more entries in the list.

``side`` (``"L"`` or ``"R"``) carries the keyboard geometry the cost model needs:
the left hand's thumb sits on the highest-pitch key of a position, the right
hand's on the lowest. ``register`` is the hand's nominal centre pitch; hands are
kept sorted by it (low -> high) so the assigner's pitch boundaries fall between
consecutive hands, and it seeds those boundaries.
"""

from dataclasses import dataclass

ALL_FINGERS = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Hand:
    name: str                       # unique label, e.g. "L", "R", "P1-L"
    side: str                       # "L" or "R": thumb geometry / chord sort / fingering orientation
    fingers: tuple = ALL_FINGERS    # available fingers, subset of 1..5
    register: float = 60.0          # nominal centre pitch (MIDI); orders hands low->high, seeds boundaries
    group: str = None               # optional player id, groups staves in the output
    clef: str = None                # optional explicit LilyPond clef; else inferred from register

    def __post_init__(self):
        # normalise fingers to a sorted ascending tuple so downstream
        # combinations() and held-state indexing are deterministic.
        object.__setattr__(self, "fingers", tuple(sorted(self.fingers)))


DEFAULT_HANDS = [
    Hand("L", "L", register=53.0),   # F3, conventional bass-staff centre
    Hand("R", "R", register=67.0),   # G4, conventional treble-staff centre
]


def validate(hands):
    """Validate and return ``hands`` sorted by register (low -> high).

    Raises ``ValueError`` on an empty list, a duplicate name, a bad ``side``, or a
    finger set that is empty or not a subset of ``{1..5}``.
    """
    if not hands:
        raise ValueError("at least one hand is required")
    names = set()
    for h in hands:
        if h.name in names:
            raise ValueError(f"duplicate hand name {h.name!r}")
        names.add(h.name)
        if h.side not in ("L", "R"):
            raise ValueError(f"hand {h.name!r}: side must be 'L' or 'R', got {h.side!r}")
        if not h.fingers:
            raise ValueError(f"hand {h.name!r}: at least one finger is required")
        if not set(h.fingers).issubset(set(ALL_FINGERS)):
            raise ValueError(f"hand {h.name!r}: fingers must be a subset of {ALL_FINGERS}, "
                             f"got {h.fingers}")
    return sorted(hands, key=lambda h: h.register)
