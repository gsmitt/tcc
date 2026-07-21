"""Load the PIG piano-fingering dataset for ground-truth evaluation.

PIG (Nakamura, Saito & Yoshii, *Statistical Learning and Estimation of Piano
Fingering*, Information Sciences 517 (2020)) ships one or more *fingering files*
per piece -- each a different annotator's fingering of the **same** note
sequence.  A fingering file is tab-separated, ``//`` comment header, one note per
line::

    noteID  onset  offset  spelledPitch  onsetVel  offsetVel  channel  finger

  * ``spelledPitch`` is a note name like ``C4``, ``F#5``, ``Ab3``.
  * ``finger`` is a signed integer 1..5, sign = hand (``+`` right, ``-`` left);
    a finger *substitution* is written ``start_end`` (e.g. ``4_1``) -- we take the
    starting finger.  ``channel`` (0 right / 1 left) is redundant with the sign.

Because every annotator file numbers the notes the same way (``noteID`` is the
onset-ordered index of an identical score), the files align note-for-note by
``noteID``.  :func:`load_piece` uses the first file for timing/pitch, groups notes
into the pipeline's onset ``layers`` (:mod:`src.midi_reader` format), and returns
per-note ground truth aligned to the ``(layer_idx, midi_pitch)`` key the solver
output can be looked up by.

Times are the performance times in seconds; the pipeline only uses them for
relative onset/release order (held-finger availability), so seconds are fine.
"""

import os
import glob

# Grouping tolerance: notes whose onsets fall within this many seconds of the
# layer's onset are treated as one simultaneous chord (performance timing is not
# exactly simultaneous).
GROUP_EPS = 0.03

_STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def spelled_to_midi(name):
    """Convert a spelled pitch (``C4``, ``F#5``, ``Bb3``, ``C##4``) to MIDI number.

    Scientific pitch notation with C4 = 60.
    """
    i = 1
    while i < len(name) and name[i] in "#b":
        i += 1
    letter, accidentals, octave = name[0], name[1:i], name[i:]
    semitone = _STEP[letter.upper()]
    semitone += accidentals.count("#") - accidentals.count("b")
    return (int(octave) + 1) * 12 + semitone


def _parse_finger(field):
    """Return ``(finger_magnitude, hand)`` from a PIG finger field.

    Handles substitutions ``start_end`` (keeps ``start``) and the signed-hand
    convention (positive right, negative left).
    """
    start = field.split("_")[0]
    val = int(start)
    hand = "R" if val >= 0 else "L"
    return abs(val), hand


def parse_fingering_file(path):
    """Parse one PIG fingering file into onset-ordered note records.

    Returns ``[{"note_id", "onset", "offset", "midi", "finger", "hand"}, ...]``.
    """
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            cols = line.split("\t")
            if len(cols) < 8:
                cols = line.split()
            if len(cols) < 8:
                continue
            note_id = int(cols[0])
            onset, offset = float(cols[1]), float(cols[2])
            midi = spelled_to_midi(cols[3])
            finger, hand = _parse_finger(cols[7])
            records.append({"note_id": note_id, "onset": onset, "offset": offset,
                            "midi": midi, "finger": finger, "hand": hand})
    records.sort(key=lambda r: (r["onset"], r["midi"]))
    return records


def load_piece(paths):
    """Build onset layers plus aligned ground truth from a piece's annotator files.

    ``paths`` is the list of fingering files for one piece.  Returns
    ``(layers, ground_truth)`` where:

      * ``layers`` -- ``[{"time", "notes": [(midi, offset), ...]}, ...]`` in the
        :mod:`src.midi_reader` format, notes grouped into chords by onset.
      * ``ground_truth`` -- ``{(layer_idx, midi): {"fingers": [...], "hands":
        [...]}}``: one entry per note, with the finger and hand each annotator
        assigned it (``None`` where an annotator lacks that note), positionally
        aligned across annotators.

    The first file defines timing/pitch; the rest contribute only fingers/hands,
    aligned by ``note_id`` (identical across a piece's files).
    """
    per_file = [parse_fingering_file(p) for p in paths]
    if not per_file or not per_file[0]:
        return [], {}
    by_id = [{r["note_id"]: r for r in recs} for recs in per_file]
    ref = per_file[0]

    layers = []
    ground_truth = {}
    cur_notes = None
    cur_onset = None
    cur_seen = None                     # pitches already in the current layer

    def flush():
        if cur_notes:
            layers.append({"time": cur_onset, "notes": list(cur_notes)})

    for rec in ref:
        if cur_onset is None or rec["onset"] - cur_onset > GROUP_EPS:
            flush()
            cur_notes, cur_seen = [], set()
            cur_onset = rec["onset"]
            layer_idx = len(layers)     # index this layer will get on flush
        midi = rec["midi"]
        if midi in cur_seen:            # duplicate pitch in a chord: keep the first
            continue
        cur_seen.add(midi)
        cur_notes.append((midi, rec["offset"]))

        nid = rec["note_id"]
        fingers, hands = [], []
        for idx in by_id:
            r = idx.get(nid)
            fingers.append(r["finger"] if r else None)
            hands.append(r["hand"] if r else None)
        ground_truth[(layer_idx, midi)] = {"fingers": fingers, "hands": hands}
    flush()
    return layers, ground_truth


def discover_pieces(root):
    """Group PIG fingering files by piece under ``root``.

    PIG names files ``<piece>-<annotator>_fingering.txt``.  Returns
    ``{piece_id: [paths sorted by annotator]}``.
    """
    pieces = {}
    for path in sorted(glob.glob(os.path.join(root, "**", "*_fingering.txt"),
                                 recursive=True)):
        base = os.path.basename(path)
        stem = base[:-len("_fingering.txt")]
        piece = stem.rsplit("-", 1)[0] if "-" in stem else stem
        pieces.setdefault(piece, []).append(path)
    return pieces
