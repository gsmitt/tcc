from src.midi_reader      import read_midi
from src.assigners        import get_assigner, split_layers_by_hands
from src.solvers          import get_solver
from src.sheet_export     import render_fingering_pdf
from src.sheet_reducer    import DEFAULT_TARGET, reduce_score
from src.hands            import DEFAULT_HANDS, Hand

SLICE    = 2000        # whole piece; the viterbi solver scales to 800+ layers
SOLVER   = "viterbi"   # "viterbi" | "dynamic" | "graph"
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
TARGET = DEFAULT_TARGET       # absolute (D_L, D_R, D_B) difficulty ceilings, in
                              # ergonomic cost PER SECOND over a 1 s window
                              # (src.difficulty; Nakamura & Yoshii 2018 eq. (6)).
                              # Fixed/global, not per-piece: a harder piece reduces
                              # more, an easier one less. The value and the scale it
                              # was measured on are recorded at src.sheet_reducer's
                              # DEFAULT_TARGET; re-read it with difficulty_profile.py,
                              # which prints that scale, because the measure is a
                              # time rate and a ceiling does not survive a change of
                              # window, cost model or tempo convention.


def main():
    all_layers, tempo = read_midi("data/mond_1.mid")
    layers = all_layers[:SLICE]
    print(f"Tempo: {tempo.label()}")

    if REDUCE:
        # joint-local measures difficulty inside the reduction loop: ~20x faster
        # than joint-full, which agrees with it on ~92% of notes (mond_1).
        result = reduce_score(layers, target=TARGET, bpm=tempo.bpm,
                              assigner="joint-local")
        tl, tr, tb = result.target
        print(f"Reduced (target D_L/D_R/D_B={tl:.0f}/{tr:.0f}/{tb:.0f}): "
              f"-{len(result.deleted)} notes, {len(result.shifted)} shifted, "
              f"Aadd={result.additional_note_rate:.0%}")
        if result.tempo_factor < 1.0:
            print(f"  tempo reduced to {result.tempo_factor:.0%} of the score's "
                  f"({result.reduced_bpm:.1f} BPM): preserves material at the "
                  f"cost of the piece's intended character")
        layers = result.layers

    labels = get_assigner(ASSIGNER)(layers, hands=HANDS).assign()
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
