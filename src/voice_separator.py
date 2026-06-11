"""Voice separation for polyphonic MIDI layers.

Greedy chain-partition heuristic in the spirit of Chew & Wu, "Separating Voices
in Polyphonic Music: A Contig Mapping Approach" (CMMR 2004): notes are processed
in time order and each is appended to the existing voice it continues most
naturally (closest in pitch and time), opening a new voice when no existing one
is a good enough continuation.  This is the streaming approximation of their
cost -- we do not build and connect contigs explicitly.

Two refinements over a plain greedy keep repeated bass/pedal tones from being
scattered across voices (the scattering that previously biased everything toward
the first voice):

  * ties are broken toward the most recently active voice, not the lowest-index
    one, so voice 0 no longer accumulates notes by default;
  * a re-struck identical pitch may continue its own voice even if the previous
    instance technically still overlaps, and is given a continuity bonus -- so a
    held/repeated pedal note stays in one voice instead of jumping to whichever
    voice happens to be free; and
  * a register-distant note opens a new voice (up to ``max_voices``) instead of
    being crammed into the cheapest far voice.

Note: hand/staff assignment (:mod:`src.hand_assigner`) now reads onsets directly
and no longer depends on this partition, so these refinements improve the voice
model itself -- for analysis and for the future within-hand polyphony noted in
:mod:`src.sheet_export` -- rather than the staff split.

A "note record" is the tuple
    (start_time, midi_pitch, end_time, layer_idx, note_idx_in_layer)
so the caller can map back to the original layer structure.
"""

EPSILON = 1e-6
OVERLAP_TOLERANCE = 1 / 32  # note-value (32nd note); treat tiny overlap as legato


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
                    max_voices=8,
                    voice_threshold=12.0,
                    continuity_bonus=6.0):
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
            same_pitch = last_pitch == pitch
            # The voice's last note must (almost) be done -- except a re-struck
            # identical pitch may continue its own voice (a repeated pedal tone).
            if not same_pitch and last_end - start > OVERLAP_TOLERANCE:
                continue
            cost = (pitch_weight * abs(pitch - last_pitch)
                    + time_weight * max(0.0, start - last_end))
            if same_pitch:
                cost -= continuity_bonus
            # Sort key: cost first, then most-recently-active voice (largest
            # last_start), then index as a deterministic final fallback.
            candidates.append((cost, -last_start, vi))

        if not candidates:
            voices.append([note])
            continue

        candidates.sort()
        best_cost, _, best_vi = candidates[0]
        if best_cost < voice_threshold:
            voices[best_vi].append(note)
        elif len(voices) < max_voices:
            # Open a new voice rather than cram a register-distant note into a
            # far one (the old behaviour that mixed registers within a voice).
            voices.append([note])
        else:
            voices[best_vi].append(note)        # hard cap reached: least-bad merge

    return voices
