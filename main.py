from src.midi_reader      import read_midi_to_layers
from src.voice_separator  import separate_voices
from src.assigners        import get_assigner, split_layers_by_hand
from src.solvers          import get_solver
from src.sheet_export     import render_fingering_pdf
from src.sheet_reducer    import reduce_score

SLICE    = 2000        # whole piece; the viterbi solver scales to 800+ layers
SOLVER   = "viterbi"   # "viterbi" | "dynamic" | "greedy" | "graph"
ASSIGNER = "joint-full"  # "split" | "joint-local" | "joint-full"

REDUCE = True        # thin the score before fingering
TARGET = (25.0, 45.0, 65.0)   # absolute (D_L, D_R, D_B) difficulty ceilings in
                              # ergonomic-cost-density units. Fixed/global, not
                              # per-piece: a harder piece reduces more, an easier
                              # one less. Choose/justify via difficulty_profile.py.


def main():
    layers = read_midi_to_layers("data/mond_1.mid")[:SLICE]

    if REDUCE:
        result = reduce_score(layers, target=TARGET)
        tl, tr, tb = result.target
        print(f"Reduced (target D_L/D_R/D_B={tl:.0f}/{tr:.0f}/{tb:.0f}): "
              f"-{len(result.deleted)} notes, {len(result.shifted)} shifted, "
              f"Aadd={result.additional_note_rate:.0%}")
        layers = result.layers

    voices = separate_voices(layers)
    print(f"Voices: {len(voices)}  (sizes: {[len(v) for v in voices]})")

    labels = get_assigner(ASSIGNER)(voices).assign()
    lh_layers, rh_layers = split_layers_by_hand(layers, labels)
    print(f"LH layers: {len(lh_layers)}    RH layers: {len(rh_layers)}")

    Solver = get_solver(SOLVER)
    lh = Solver(lh_layers, hand="L").solve()
    rh = Solver(rh_layers, hand="R").solve()

    print(f"[{SOLVER}] LH  cost={lh.cost}  visits={lh.node_visits}  extras={lh.extras}")
    print(f"[{SOLVER}] RH  cost={rh.cost}  visits={rh.node_visits}  extras={rh.extras}")

    pdf = render_fingering_pdf(lh_layers, lh.path, rh_layers, rh.path,
                               out_path="output/mond_1")
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main()
