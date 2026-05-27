"""Voice separation for polyphonic MIDI layers.

Given the layers produced by midi_reader.read_midi_to_layers, partition every
note into a small number of voices (monophonic-ish streams) via a greedy
chain-partition heuristic in the spirit of Chew & Wu (2004).

A "note record" is the tuple
    (start_time, midi_pitch, end_time, layer_idx, note_idx_in_layer)
so the caller can map back to the original layer structure.
"""

EPSILON = 1e-6
OVERLAP_TOLERANCE = 0.05  # seconds; treat tiny overlap as legato continuation


def _flatten(layers):
    notes = []
    for layer_idx, layer in enumerate(layers):
        start = layer["time"]
        for note_idx, (pitch, end) in enumerate(layer["notes"]):
            notes.append((start, pitch, end, layer_idx, note_idx))
    notes.sort(key=lambda n: (n[0], n[1]))
    return notes


def separate_voices(layers,
                    pitch_weight=1.0,
                    time_weight=2.0,
                    max_voices=6,
                    voice_threshold=12.0):
    """Return a list of voices. Each voice is a list of note records sorted
    by start_time.
    """
    voices = []

    for note in _flatten(layers):
        start, pitch, _, _, _ = note
        candidates = []
        for vi, voice in enumerate(voices):
            last_start, last_pitch, last_end, _, _ = voice[-1]
            # A voice cannot host two notes that begin at the same time.
            if last_start >= start - EPSILON:
                continue
            # The voice's last note must (almost) be done.
            if last_end - start > OVERLAP_TOLERANCE:
                continue
            cost = (pitch_weight * abs(pitch - last_pitch)
                    + time_weight * max(0.0, start - last_end))
            candidates.append((cost, vi))

        if not candidates:
            voices.append([note])
            continue

        candidates.sort()
        best_cost, best_vi = candidates[0]
        if best_cost < voice_threshold or len(voices) >= max_voices:
            voices[best_vi].append(note)
        else:
            voices.append([note])

    return voices
