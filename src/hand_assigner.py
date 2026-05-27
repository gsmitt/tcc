"""Assign voices to hands and split MIDI layers into per-hand streams.

Given the voices produced by voice_separator.separate_voices, decide which
voices go to the left hand and which to the right by enumerating all 2-way
partitions and scoring each by per-layer playability (chord-size and span)
plus a register-separation reward.
"""


def _voice_stats(voice):
    pitches = [n[1] for n in voice]
    return {
        "mean": sum(pitches) / len(pitches),
        "min": min(pitches),
        "max": max(pitches),
    }


def assign_voices_to_hands(voices,
                           max_notes_per_hand=5,
                           max_span_semitones=14,
                           separation_weight=2.0):
    """Return a dict (layer_idx, note_idx_in_layer) -> "L" | "R".

    Every note in every voice is labelled.
    """
    n_voices = len(voices)
    if n_voices == 0:
        return {}

    voice_stats = [_voice_stats(v) for v in voices]

    if n_voices == 1:
        hand = "R" if voice_stats[0]["mean"] >= 60 else "L"
        return {(n[3], n[4]): hand for n in voices[0]}

    # layer_notes_per_voice[v] = {layer_idx: [pitch, ...]}
    layer_notes_per_voice = []
    for voice in voices:
        d = {}
        for note in voice:
            d.setdefault(note[3], []).append(note[1])
        layer_notes_per_voice.append(d)

    best_cost = float("inf")
    best_assignment = None

    # Voice 0 fixed to "L" to break the L/R relabel symmetry.
    for bits in range(2 ** (n_voices - 1)):
        assignment = ["L"]
        for i in range(n_voices - 1):
            assignment.append("R" if (bits >> i) & 1 else "L")
        if "R" not in assignment:
            continue

        layer_pitches = {"L": {}, "R": {}}
        for vi, hand in enumerate(assignment):
            for lidx, pitches in layer_notes_per_voice[vi].items():
                layer_pitches[hand].setdefault(lidx, []).extend(pitches)

        feasible = True
        span_cost = 0.0
        for hand in ("L", "R"):
            for pitches in layer_pitches[hand].values():
                if len(pitches) > max_notes_per_hand:
                    feasible = False
                    break
                if len(pitches) >= 2:
                    span = max(pitches) - min(pitches)
                    if span > max_span_semitones:
                        feasible = False
                        break
                    span_cost += span
            if not feasible:
                break
        if not feasible:
            continue

        lh_means = [voice_stats[vi]["mean"] for vi, h in enumerate(assignment) if h == "L"]
        rh_means = [voice_stats[vi]["mean"] for vi, h in enumerate(assignment) if h == "R"]
        sep = abs(sum(lh_means) / len(lh_means) - sum(rh_means) / len(rh_means))

        total_cost = span_cost - separation_weight * sep
        if total_cost < best_cost:
            best_cost = total_cost
            best_assignment = assignment[:]

    if best_assignment is None:
        # Every partition was infeasible. Fall back to pitch-mean split.
        order = sorted(range(n_voices), key=lambda i: voice_stats[i]["mean"])
        best_assignment = ["L"] * n_voices
        for vi in order[(n_voices + 1) // 2:]:
            best_assignment[vi] = "R"

    # Make sure LH ends up the lower-register hand.
    lh_voices = [vi for vi, h in enumerate(best_assignment) if h == "L"]
    rh_voices = [vi for vi, h in enumerate(best_assignment) if h == "R"]
    if lh_voices and rh_voices:
        lh_mean = sum(voice_stats[vi]["mean"] for vi in lh_voices) / len(lh_voices)
        rh_mean = sum(voice_stats[vi]["mean"] for vi in rh_voices) / len(rh_voices)
        if lh_mean > rh_mean:
            best_assignment = ["R" if h == "L" else "L" for h in best_assignment]

    labels = {}
    for vi, hand in enumerate(best_assignment):
        for note in voices[vi]:
            labels[(note[3], note[4])] = hand
    return labels


def split_layers_by_hand(layers, hand_labels):
    """Partition each layer's notes by hand label.

    Returns (lh_layers, rh_layers). Layers with no notes for a hand are
    omitted from that hand's stream.
    """
    lh_layers = []
    rh_layers = []
    for layer_idx, layer in enumerate(layers):
        lh_notes = []
        rh_notes = []
        for note_idx, (pitch, end) in enumerate(layer["notes"]):
            hand = hand_labels.get((layer_idx, note_idx))
            if hand == "L":
                lh_notes.append((pitch, end))
            elif hand == "R":
                rh_notes.append((pitch, end))
        if lh_notes:
            lh_layers.append({"time": layer["time"], "notes": lh_notes})
        if rh_notes:
            rh_layers.append({"time": layer["time"], "notes": rh_notes})
    return lh_layers, rh_layers
