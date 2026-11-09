"""Common interface for hand (staff) assigners.

A hand assigner decides, for every note carried by the voice partition, which
hand plays it.  All variants return the same mapping

    {(layer_idx, note_idx_in_layer): hand.name}

(``hand.name`` is ``"L"``/``"R"`` for the default two-hand config, but an
arbitrary label for a duet/N-hand config), so they are interchangeable downstream
via :func:`split_layers_by_hands` (re-exported from :mod:`src.assigners`).

Every assigner is parameterised on an ordered list of :class:`src.hands.Hand`
(sorted low -> high by register). The coupled ``joint-full`` assigner supports any
number of hands -- the boundaries it places fall between consecutive hands; the
proxy baselines (``split``, ``joint-local``) remain two-hand references.

The split-point assigner (:mod:`src.assigners.split_point`) chooses the staff
with an ergonomic *proxy* (feasibility only).  The joint assigners
(:mod:`src.assigners.joint_local`, :mod:`src.assigners.joint_full`) instead score
each candidate split with the *real* fingering cost of :mod:`src.costs`, coupling
hand assignment to the fingering it forces -- the project's original
contribution.  Registering all three behind :func:`src.assigners.get_assigner`
mirrors the solver registry in :mod:`src.solvers` and makes the coupling depth an
ablation axis (compare staff splits, fingering cost and runtime by name).

Assigners read the layer sequence produced by :mod:`src.midi_reader` directly:
``[{"time": onset, "notes": [(pitch, end), ...]}, ...]``.
"""

from abc import ABC, abstractmethod

from src.hands import DEFAULT_HANDS, validate


class HandAssigner(ABC):
    """Assign every note of ``layers`` to a hand.

    Subclasses read :attr:`layers` and :attr:`hands` and implement :meth:`assign`.
    ``hands`` is an ordered list of :class:`src.hands.Hand`, sorted low -> high by
    register.
    """

    def __init__(self, layers, hands=DEFAULT_HANDS):
        self.layers = layers
        self.hands = validate(hands)

    @abstractmethod
    def assign(self) -> dict:
        """Return ``{(layer_idx, note_idx_in_layer): hand.name}``."""
        ...


def thumb_first(notes, side):
    """``notes`` (``(pitch, end)`` pairs) ordered from the thumb side of a hand.

    The thumb sits on the lowest key of a right-side hand and on the highest of a
    left-side one.  The fingerings the assigners try come from
    ``itertools.combinations``, which yields fingers in ascending order, so the
    notes must be in this order for finger 1 to land on the thumb-side note, as
    in the solvers (:func:`src.hand_assigner.split_layers_by_hands`) and as
    :func:`src.costs.chord_complexity` and
    :func:`src.costs.fingering_transition_cost` expect.
    """
    return sorted(notes, key=lambda ne: ne[0], reverse=(side == "L"))


def onsets_with_release(layers):
    """Per-onset note lists: ``[(layer_idx, onset, [(pitch, end, note_idx), ...]), ...]``.

    Each note list is sorted by pitch.  The joint assigners need ``end`` to feed
    :func:`src.costs.chord_complexity` and the solver-style held-finger state, and
    the onset to know when a finger has come free; the split-point assigner
    discards both.
    """
    return [(li, layer["time"],
             sorted((p, e, ni) for ni, (p, e) in enumerate(layer["notes"])))
            for li, layer in enumerate(layers) if layer["notes"]]
