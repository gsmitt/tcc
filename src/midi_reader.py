"""MIDI -> onset layers, plus the piece's tempo.

Two things come out of a MIDI file here:

  * **layers** -- the pipeline's score representation: one entry per onset time,
    with the pitches starting there and their release times.  Times are
    *note-value fractions* (whole = 1, quarter = 0.25), the unit used by every
    layer downstream (voice separation, hand assignment, fingering).  That unit
    is tempo-free on purpose: fingering does not change when the piece is played
    slower, so nothing in the solver chain needs seconds.

  * **tempo** -- a :class:`Tempo`, read from the file's ``set_tempo`` messages.
    Only :mod:`src.difficulty` needs it: performance difficulty is a *time rate*
    of cost (Nakamura & Yoshii, "Statistical Piano Reduction Controlling
    Performance Difficulty", APSIPA Trans. Signal & Information Processing 7
    (2018), eq. (6), SS II.B.1), so converting a note-value window into seconds
    requires knowing how long a whole note lasts.

When a file carries no ``set_tempo``, we assume ``FALLBACK_BPM`` = 120 BPM, the
default the format itself prescribes: "All MIDI Files should specify tempo and
time signature.  If they don't, the time signature is assumed to be 4/4, and the
tempo 120 beats per minute" (MIDI Manufacturers Association, *Standard MIDI
Files 1.0*, RP-001, 1996, p. 5).  Missing tempo is common: Ramoneda et al.,
"Towards Explainable and Interpretable Musical Difficulty Estimation: A
Parameter-efficient Approach", ISMIR 2024, SS 3.1, report it absent in 23% of
their scores (they assume 100 BPM there).  Like them, we flag the assumption
rather than hide it (:attr:`Tempo.declared`): a difficulty measured under a
presumed tempo is not comparable with one measured under a tempo actually read
from the score.

**Limitation (tempo map).** A piece whose tempo varies gets its *first*
``set_tempo``; the remaining changes are counted in :attr:`Tempo.n_changes` and
ignored.  A per-onset tempo map would make the conversion below local instead of
global and is left as an extension; it matters most for performance MIDI, where
expressive timing is encoded as hundreds of tempo changes around a nominal value.
"""

from dataclasses import dataclass

from mido import MidiFile, merge_tracks, tempo2bpm

# Tempo assumed when the file declares none: the Standard MIDI Files default
# (MMA RP-001, 1996, p. 5).
FALLBACK_BPM = 120.0


@dataclass(frozen=True)
class Tempo:
    """The piece's tempo, and how honestly we know it.

    ``bpm`` is in quarter notes per minute (the MIDI convention), so a whole note
    lasts ``240 / bpm`` seconds.  ``declared`` is False when ``bpm`` is the
    assumed :data:`FALLBACK_BPM` instead of a value read from the file.
    ``n_changes`` counts the ``set_tempo`` messages *after* the first one, i.e.
    how much of a tempo map this first version is throwing away.
    """

    bpm: float
    declared: bool
    n_changes: int = 0

    @property
    def seconds_per_whole(self):
        """Duration of a whole note in seconds (a quarter note is one beat)."""
        return 240.0 / self.bpm

    def label(self):
        """One-line provenance string, for printed output and result tables."""
        if not self.declared:
            return (f"{self.bpm:.1f} BPM (assumed: no set_tempo in file; "
                    f"Standard MIDI Files default)")
        extra = (f", {self.n_changes} later tempo change(s) ignored"
                 if self.n_changes else "")
        return f"{self.bpm:.1f} BPM (read from set_tempo{extra})"


def read_midi(path: str):
    """Read ``path`` once, returning ``(layers, tempo)``.

    layer:
        {
            "time": float,  # note-value fraction (whole=1, quarter=0.25)
            "notes": [(note_number, end)]
        }
    """
    mid = MidiFile(path)
    ticks_per_whole = mid.ticks_per_beat * 4
    events = []
    active_notes = {}
    tempos = []

    current_ticks = 0
    for msg in merge_tracks(mid.tracks):
        current_ticks += msg.time
        current_time = current_ticks / ticks_per_whole
        if msg.type == "set_tempo":
            tempos.append(msg.tempo)
        elif msg.type == "note_on" and msg.velocity > 0:
            active_notes[msg.note] = current_time
        elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
            if msg.note in active_notes:
                start = active_notes.pop(msg.note)
                events.append((start, msg.note, current_time))

    events.sort(key=lambda x: x[0])

    layers = []
    if events:
        current_t = events[0][0]
        current_layer = {"time": current_t, "notes": []}

        for start, note, end in events:
            if abs(start - current_t) < 1e-6:
                current_layer["notes"].append((note, end))
            else:
                layers.append(current_layer)
                current_t = start
                current_layer = {"time": current_t, "notes": [(note, end)]}

        layers.append(current_layer)

    return layers, _tempo_from(tempos)


def read_midi_to_layers(path: str):
    """Just the layers of :func:`read_midi` (the tempo-free part of the read)."""
    return read_midi(path)[0]


def _tempo_from(tempos):
    """First ``set_tempo`` as a :class:`Tempo`, or the declared fallback."""
    if tempos:
        return Tempo(bpm=float(tempo2bpm(tempos[0])), declared=True,
                     n_changes=len(tempos) - 1)
    return Tempo(bpm=FALLBACK_BPM, declared=False, n_changes=0)
