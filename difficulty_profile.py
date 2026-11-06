"""Print the per-onset difficulty distribution of a MIDI file.

Difficulty (:mod:`src.difficulty`) is an ergonomic cost **per second**, so the
scale is piece-independent at a given tempo but not across tempi -- the same
passage scores twice as high played twice as fast, which is the dependence the
measure exists to have (Nakamura & Yoshii 2018, §II.B.1).  Use this to choose and
justify an absolute ``reduce_score`` target (`main.py`'s ``TARGET``): run it on the
piece you want to reduce and on a few reference pieces to anchor what a given D_B
means, and record the window and tempo the numbers were read at -- both are
printed in the header.

    python difficulty_profile.py [data/some.mid] [bpm]

The optional ``bpm`` overrides the tempo read from the file.  Passing half or
double the score's tempo is also the sanity check on the measure: the difficulty
should scale with it.
"""

import sys

from src.midi_reader  import read_midi
from src.difficulty   import DEFAULT_DELTA_T
from src.sheet_reducer import difficulty_profile


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mond_1.mid"
    layers, tempo = read_midi(path)

    if len(sys.argv) > 2:
        bpm = float(sys.argv[2])
        tempo_label = f"{bpm:.1f} BPM (override; file says {tempo.label()})"
    else:
        bpm = tempo.bpm
        tempo_label = tempo.label()

    prof = difficulty_profile(layers, bpm=bpm, delta_t=DEFAULT_DELTA_T)

    print(f"Difficulty profile: {path}  ({len(layers)} onsets)")
    print(f"  scale: ergonomic cost per second, Δt={DEFAULT_DELTA_T:g}s "
          f"at {tempo_label}")
    print(f"{'':5} {'min':>8} {'p50':>8} {'p90':>8} {'max':>8} {'n_inf':>6}")
    for name in ("D_L", "D_R", "D_B"):
        s = prof[name]
        print(f"{name:5} {s['min']:8.1f} {s['p50']:8.1f} {s['p90']:8.1f} "
              f"{s['p100']:8.1f} {s['n_inf']:6d}")


if __name__ == "__main__":
    main()
