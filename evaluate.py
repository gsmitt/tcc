"""Evaluation harness for the fingering pipeline.

Two modes, both writing a tidy CSV/JSON table plus a printed summary:

  * ``ablation`` -- run the pipeline across the (reduce x assigner x solver) grid
    on a MIDI file and report, per configuration, the four metric families of
    :mod:`src.metrics`: fingering difficulty, reduction fidelity/efficacy, and
    search efficiency (with the solvers' optimality gap vs. exact Viterbi).

        python evaluate.py ablation [data/some.mid] [--slice N]

  * ``pig`` -- run the pipeline on the PIG dataset and report fingering match
    rates and hand-assignment accuracy against the human annotators.

        python evaluate.py pig path/to/PIG/FingeringFiles [--assigner joint-full]

  * ``selftest`` -- assert the definitional ordering of the match rates on a small
    synthetic example (no data or model needed).

        python evaluate.py selftest

The DFS baselines (dynamic/graph/greedy) are exponential, so ``ablation`` skips
them when a hand's stream exceeds ``--max-dfs`` layers; Viterbi (exact, the
production solver) always runs.
"""

import argparse
import csv
import json
import os
import time

from src.midi_reader import read_midi_to_layers
from src.voice_separator import separate_voices
from src.assigners import get_assigner, split_layers_by_hands
from src.solvers import get_solver
from src.sheet_reducer import reduce_score
from src.difficulty import note_difficulties
from src.hands import DEFAULT_HANDS
from src import metrics
from src import pig_loader

ASSIGNERS = ("split", "joint-local", "joint-full")
SOLVERS = ("viterbi", "dynamic", "graph", "greedy")


# --------------------------------------------------------------------------- #
# Shared pipeline steps
# --------------------------------------------------------------------------- #

def assign_and_split(layers, assigner, hands):
    """Voice-separate, assign hands, and partition into per-hand streams."""
    voices = separate_voices(layers)
    labels = get_assigner(assigner)(voices, hands=hands).assign()
    hand_layers = split_layers_by_hands(layers, labels, hands)
    return labels, hand_layers


def solve_hands(hand_layers, hands, solver):
    """Solve every hand's fingering; return ``{hand.name: SolverResult}``."""
    Solver = get_solver(solver)
    results = {}
    for hand in hands:
        results[hand.name] = Solver(hand_layers.get(hand.name, []),
                                    hand=hand.side, fingers=hand.fingers).solve()
    return results


# --------------------------------------------------------------------------- #
# Ablation mode
# --------------------------------------------------------------------------- #

def _flatten_difficulty(diff_stats, row):
    for name, stats in diff_stats.items():
        for key, val in stats.items():
            row[f"{name}_{key}"] = val


def run_ablation(midi_path, slice_n, max_dfs, delta_t=1.0, target=(25.0, 45.0, 65.0)):
    hands = DEFAULT_HANDS
    original = read_midi_to_layers(midi_path)[:slice_n]
    rows = []

    for reduce_on in (False, True):
        if reduce_on:
            red = reduce_score(original, target=target)
            layers = red.layers
            fidelity = metrics.reduction_fidelity(red, original)
        else:
            red, layers, fidelity = None, original, None

        for assigner in ASSIGNERS:
            labels, hand_layers = assign_and_split(layers, assigner, hands)
            longest = max((len(v) for v in hand_layers.values()), default=0)

            # Viterbi is exact: it defines the difficulty read-out and the
            # optimality baseline the other solvers are compared against.
            vit = solve_hands(hand_layers, hands, "viterbi")
            vit_stats = metrics.solver_stats(vit)
            base_cost = vit_stats["total_cost"]

            diffs = note_difficulties(
                layers, hand_layers.get("L", []), vit["L"].path,
                hand_layers.get("R", []), vit["R"].path, delta_t)
            diff_stats = metrics.difficulty_stats(diffs)
            sat = metrics.target_satisfaction(diffs, target)

            for solver in SOLVERS:
                if solver != "viterbi" and longest > max_dfs:
                    continue  # DFS baseline would blow up on this input
                t0 = time.perf_counter()
                res = vit if solver == "viterbi" else solve_hands(
                    hand_layers, hands, solver)
                elapsed = time.perf_counter() - t0
                st = metrics.solver_stats(res)

                gap = (st["total_cost"] - base_cost
                       if base_cost not in (float("inf"),) else float("inf"))
                row = {
                    "reduce": reduce_on, "assigner": assigner, "solver": solver,
                    "total_cost": st["total_cost"], "optimality_gap": gap,
                    "node_visits": st["node_visits"],
                    "peak_states": st["peak_states"],
                    "feasible": st["feasible"], "seconds": round(elapsed, 4),
                    "target_satisfaction": sat["satisfaction_rate"],
                    "n_violations": sat["n_violations"],
                }
                _flatten_difficulty(diff_stats, row)
                if fidelity:
                    row.update({f"fid_{k}": v for k, v in fidelity.items()})
                rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# PIG mode
# --------------------------------------------------------------------------- #

def _predictions(layers, labels, hand_layers, results):
    """Map solver output back to ``(layer_idx, midi) -> (finger, hand)``."""
    time_to_layer = {round(l["time"], 9): i for i, l in enumerate(layers)}
    pred_finger, pred_hand = {}, {}
    for name, res in results.items():
        for layer, (notes, fingers) in zip(hand_layers.get(name, []), res.path):
            li = time_to_layer[round(layer["time"], 9)]
            for (midi, _off), f in zip(notes, fingers):
                pred_finger[(li, midi)] = f
    for (layer_idx, note_idx), hname in labels.items():
        midi = layers[layer_idx]["notes"][note_idx][0]
        pred_hand[(layer_idx, midi)] = hname
    return pred_finger, pred_hand


def evaluate_piece(paths, assigner, solver):
    hands = DEFAULT_HANDS
    layers, gt = pig_loader.load_piece(paths)
    if not layers:
        return None
    labels, hand_layers = assign_and_split(layers, assigner, hands)
    results = solve_hands(hand_layers, hands, solver)
    pred_finger, pred_hand = _predictions(layers, labels, hand_layers, results)

    keys = sorted(gt)
    n_ann = len(gt[keys[0]]["fingers"]) if keys else 0
    pred_f = [pred_finger.get(k) for k in keys]
    annotators = [[gt[k]["fingers"][a] for k in keys] for a in range(n_ann)]
    mr = metrics.match_rates(pred_f, annotators)

    pred_h = [pred_hand.get(k) for k in keys]
    truth_h = [next((h for h in gt[k]["hands"] if h is not None), None)
               for k in keys]
    mr["hand_accuracy"] = metrics.hand_accuracy(pred_h, truth_h)
    mr["n_notes"] = len(keys)
    mr["n_annotators"] = n_ann
    return mr


def run_pig(root, assigner, solver):
    pieces = pig_loader.discover_pieces(root)
    if not pieces:
        raise SystemExit(f"No PIG *_fingering.txt files under {root!r}")
    rows = []
    for piece, paths in sorted(pieces.items()):
        res = evaluate_piece(paths, assigner, solver)
        if res:
            res["piece"] = piece
            rows.append(res)
    return rows


# --------------------------------------------------------------------------- #
# Self-test: definitional ordering of the match rates
# --------------------------------------------------------------------------- #

def run_selftest():
    pred = [1, 2, 3, 4, 5]
    annotators = [
        [1, 2, 9, 9, 9],   # matches first two
        [9, 9, 3, 4, 9],   # matches middle two
        [9, 9, 9, 9, 5],   # matches last one
    ]
    mr = metrics.match_rates(pred, annotators)
    print("match rates:", {k: round(v, 3) for k, v in mr.items()})
    assert mr["M_high"] >= mr["M_gen"] - 1e-9, "M_high >= M_gen"
    assert mr["M_soft"] >= mr["M_high"] - 1e-9, "M_soft >= M_high"
    assert mr["M_soft"] >= mr["M_rec"] - 1e-9, "M_soft >= M_rec"
    assert mr["M_rec"] >= mr["M_high"] - 1e-9, "M_rec >= M_high"
    # every note is covered by exactly one annotator here -> soft == 1.0
    assert abs(mr["M_soft"] - 1.0) < 1e-9, "soft should cover all notes"
    print("hand accuracy:", metrics.hand_accuracy(["L", "R", "R"], ["L", "L", "R"]))
    print("OK: M_gen <= M_high <= M_rec <= M_soft")


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def write_table(rows, out_stem):
    if not rows:
        print("(no rows)")
        return
    os.makedirs(os.path.dirname(out_stem) or ".", exist_ok=True)
    cols = list(dict.fromkeys(k for row in rows for k in row))
    with open(out_stem + ".csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    with open(out_stem + ".json", "w") as fh:
        json.dump(rows, fh, indent=2, default=str)
    print(f"Wrote {out_stem}.csv and {out_stem}.json ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    a = sub.add_parser("ablation")
    a.add_argument("midi", nargs="?", default="data/mond_1.mid")
    a.add_argument("--slice", type=int, default=120,
                   help="layers to evaluate (keeps DFS baselines tractable)")
    a.add_argument("--max-dfs", type=int, default=80,
                   help="skip DFS solvers when a hand stream exceeds this length")
    a.add_argument("--out", default="output/eval_ablation")

    p = sub.add_parser("pig")
    p.add_argument("root")
    p.add_argument("--assigner", default="joint-full", choices=ASSIGNERS)
    p.add_argument("--solver", default="viterbi", choices=SOLVERS)
    p.add_argument("--out", default="output/eval_pig")

    sub.add_parser("selftest")

    args = ap.parse_args()

    if args.mode == "selftest":
        run_selftest()
        return

    if args.mode == "ablation":
        rows = run_ablation(args.midi, args.slice, args.max_dfs)
        for r in rows:
            print(f"reduce={r['reduce']!s:5} {r['assigner']:11} {r['solver']:8} "
                  f"cost={r['total_cost']:>8.1f} gap={r['optimality_gap']:>6.1f} "
                  f"D_B_p90={r.get('D_B_p90', 0):>6.1f} "
                  f"visits={r['node_visits']:>8} {r['seconds']:>7.3f}s")
        write_table(rows, args.out)
        return

    if args.mode == "pig":
        rows = run_pig(args.root, args.assigner, args.solver)
        if rows:
            keys = ("M_gen", "M_high", "M_soft", "M_rec", "hand_accuracy")
            n = len(rows)
            avg = {k: sum(r[k] for r in rows) / n for k in keys}
            for r in rows:
                print(f"{r['piece']:24} " + " ".join(
                    f"{k}={r[k]:.3f}" for k in keys) + f"  (n={r['n_notes']})")
            print("-" * 60)
            print(f"{'CORPUS MEAN':24} " + " ".join(
                f"{k}={avg[k]:.3f}" for k in keys) + f"  ({n} pieces)")
        write_table(rows, args.out)
        return


if __name__ == "__main__":
    main()
