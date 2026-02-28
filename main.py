import random
from dynamic import PianoFingeringDFS
from midi_reader import read_midi_to_layers
from grouper import group_layers_by_time_signature

def main():
    teste = read_midi_to_layers("mond_1.mid")
    print(teste[0])
    #groups = group_layers_by_time_signature(layers, meta)
    #print(groups[0])
    #for group in groups:
    #    print(len(group))



if __name__ == "__main__":
    main()
