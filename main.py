from src.midi_reader      import read_midi_to_layers
from src.voice_separator  import separate_voices
from src.assigners        import get_assigner, split_layers_by_hands
from src.solvers          import get_solver
from src.sheet_export     import render_fingering_pdf
from src.sheet_reducer    import reduce_score
from src.hands            import DEFAULT_HANDS, Hand

SLICE    = 2000        # whole piece; the viterbi solver scales to 800+ layers
SOLVER   = "viterbi"   # "viterbi" | "dynamic" | "greedy" | "graph"
ASSIGNER = "joint-full"  # "split" | "joint-local" | "joint-full"

# Hands the piece is fingered for. The default is the conventional two-hand
# pianist; model missing fingers by trimming a hand's `fingers`, or a duet by
# adding more hands (the coupled "joint-full" assigner supports any number).
#   Missing finger:  Hand("R", "R", fingers=(1, 2, 3), register=67.0)
#   Duet (4 hands):  two players, each (L, R), grouped for the score:
#       [Hand("S-L","L",register=41.0,group="Secondo"),
#        Hand("S-R","R",register=53.0,group="Secondo"),
#        Hand("P-L","L",register=67.0,group="Primo"),
#        Hand("P-R","R",register=79.0,group="Primo")]
# NB: REDUCE is a two-hand difficulty preprocessor; set it False for non-default
# hand configs (it does not yet account for missing fingers or >2 hands).
HANDS = DEFAULT_HANDS

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

    labels = get_assigner(ASSIGNER)(voices, hands=HANDS).assign()
    hand_layers = split_layers_by_hands(layers, labels, HANDS)
    print("Hand layers: " + "  ".join(
        f"{h.name}={len(hand_layers.get(h.name, []))}" for h in HANDS))

    Solver = get_solver(SOLVER)
    paths = {}
    for hand in HANDS:
        res = Solver(hand_layers.get(hand.name, []),
                     hand=hand.side, fingers=hand.fingers).solve()
        paths[hand.name] = res.path
        print(f"[{SOLVER}] {hand.name}  cost={res.cost}  "
              f"visits={res.node_visits}  extras={res.extras}")

    pdf = render_fingering_pdf(HANDS, hand_layers, paths, out_path="output/mond_1")
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main()
