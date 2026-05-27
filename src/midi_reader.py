from mido import MidiFile

def read_midi_to_layers(path: str):
    """
    layer:
        {
            "time": float,  # seconds
            "notes": [(note_number, end)]
        }
    """
    mid = MidiFile(path)
    events = []
    active_notes = {}

    current_time = 0.0
    for msg in mid:
        current_time += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            active_notes[msg.note] = current_time
        elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
            if msg.note in active_notes:
                start = active_notes.pop(msg.note)
                events.append((start, msg.note, current_time))

    events.sort(key=lambda x: x[0])

    layers = []
    if not events:
        return layers

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
    return layers
