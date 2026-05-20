from midi_reader import read_midi_to_layers
from voice_separator import separate_voices
from hand_assigner import assign_voices_to_hands, split_layers_by_hand
from dynamic import PianoFingeringDFS

SLICE = 50  # parameterised while the splitter is being validated


def main():
    layers = read_midi_to_layers("mond_1.mid")[:SLICE]

    voices = separate_voices(layers)
    print(f"Voices: {len(voices)}  (sizes: {[len(v) for v in voices]})")

    labels = assign_voices_to_hands(voices)
    lh_layers, rh_layers = split_layers_by_hand(layers, labels)
    print(f"LH layers: {len(lh_layers)}    RH layers: {len(rh_layers)}")

    lh_cost, lh_path, lh_visits, lh_saved = PianoFingeringDFS(lh_layers, hand="L").solve()
    rh_cost, rh_path, rh_visits, rh_saved = PianoFingeringDFS(rh_layers, hand="R").solve()

    print(f"LH  best={lh_cost}  visits={lh_visits}  saved={lh_saved}")
    print(f"RH  best={rh_cost}  visits={rh_visits}  saved={rh_saved}")

    print(lh_layers, rh_layers)

if __name__ == "__main__":
    main()
