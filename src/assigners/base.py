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
with an ergonomic *proxy* (feasibility + cohesion).  The joint assigners
(:mod:`src.assigners.joint_local`, :mod:`src.assigners.joint_full`) instead score
each candidate split with the *real* fingering cost of :mod:`src.costs`, coupling
hand assignment to the fingering it forces -- the project's original
contribution.  Registering all three behind :func:`src.assigners.get_assigner`
mirrors the solver registry in :mod:`src.solvers` and makes the coupling depth an
ablation axis (compare staff splits, fingering cost and runtime by name).

A "note record" is the tuple produced by :mod:`src.voice_separator`:
    (start_time, midi_pitch, end_time, layer_idx, note_idx_in_layer)
The voices carry release (``end``) times, so the onset structure -- including the
release time each solver needs -- is fully recoverable from ``voices`` alone.
"""

from abc import ABC, abstractmethod

from src.hands import DEFAULT_HANDS, validate


class HandAssigner(ABC):
    """Assign every note carried by ``voices`` to a hand.

    Subclasses read :attr:`voices` and :attr:`hands` and implement :meth:`assign`.
    ``hands`` is an ordered list of :class:`src.hands.Hand`, sorted low -> high by
    register.
    """

    def __init__(self, voices, hands=DEFAULT_HANDS):
        self.voices = voices
        self.hands = validate(hands)

    @abstractmethod
    def assign(self) -> dict:
        """Return ``{(layer_idx, note_idx_in_layer): hand.name}``."""
        ...


def onsets_with_release(voices):
    """Recover per-onset note lists from the flat voice note-records.

    Returns ``[(layer_idx, start_time, [(pitch, end, note_idx), ...]), ...]``
    sorted by onset, each note list sorted by pitch.  This is the
    release-carrying analogue of :func:`src.hand_assigner._onsets_from_voices`:
    the joint assigners need the ``end`` time to feed
    :func:`src.costs.chord_complexity` and the solver-style held-finger state, and
    ``start_time`` to know when a finger has come free -- both of which the
    split-point assigner discards.  All notes of one layer share its onset start,
    so it is recorded once per layer.
    """
    by_layer = {}
    start_of = {}
    for voice in voices:
        for (start, pitch, end, layer_idx, note_idx) in voice:
            by_layer.setdefault(layer_idx, []).append((pitch, end, note_idx))
            start_of[layer_idx] = start
    return [(layer_idx, start_of[layer_idx], sorted(by_layer[layer_idx]))
            for layer_idx in sorted(by_layer)]
