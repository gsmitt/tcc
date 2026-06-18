"""Print the per-onset difficulty distribution of a MIDI file.

Difficulty (:mod:`src.difficulty`) is an ergonomic-cost density in fixed units,
so these numbers are a piece-independent scale.  Use it to choose and justify an
absolute ``reduce_score`` target (`main.py`'s ``TARGET``): run it on the piece you
want to reduce and on a few reference pieces to anchor what a given D_B means.

    python difficulty_profile.py [data/some.mid]
"""

import sys

from src.midi_reader  import read_midi_to_layers
from src.sheet_reducer import difficulty_profile


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mond_1.mid"
    layers = read_midi_to_layers(path)
    prof = difficulty_profile(layers)

    print(f"Difficulty profile: {path}  ({len(layers)} onsets)")
    print(f"{'':5} {'min':>8} {'p50':>8} {'p90':>8} {'max':>8} {'n_inf':>6}")
    for name in ("D_L", "D_R", "D_B"):
        s = prof[name]
        print(f"{name:5} {s['min']:8.1f} {s['p50']:8.1f} {s['p90']:8.1f} "
              f"{s['p100']:8.1f} {s['n_inf']:6d}")


if __name__ == "__main__":
    main()
