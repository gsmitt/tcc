"""Evaluation harness for the fingering pipeline.

Four modes; the data-driven ones write a tidy CSV/JSON table plus a printed
summary:

  * ``ablation`` -- run the pipeline across the (reduce x assigner x solver) grid
    on a MIDI file and report, per configuration, the four metric families of
    :mod:`src.metrics`: fingering difficulty, reduction fidelity/efficacy, and
    search efficiency (with the solvers' optimality gap vs. exact Viterbi).

        python evaluate.py ablation [data/some.mid] [--slice N]

  * ``pig`` -- run the pipeline on the PIG dataset and report fingering match
    rates and hand-assignment accuracy against the human annotators.  Besides
    the three variants, ``--assigner`` takes two baselines: ``fixed`` (a fixed
    boundary at middle C) and ``oracle`` (the hands of the first annotator, so
    only the fingering is estimated -- the setting of Nakamura et al. 2020).
    The match rates are reported twice: on the finger number alone (``M_*``,
    comparable with the published values) and on the signed finger, hand and
    number together (``S_*``), where a note given to the wrong hand never counts.
    Every rate is taken over all the notes of the piece: when the solver cannot
    finger a hand, that hand's notes count as misses (``coverage`` is the share of
    notes with a prediction, ``n_failed_hands`` the hands left unfingered), so all
    variants are scored on the same notes.  ``seconds`` is the assignment plus
    fingering time, the median of ``--repeats`` runs that each start with empty
    caches.

        python evaluate.py pig [path/to/PIG/FingeringFiles] [--assigner joint-full]

  * ``agreement`` -- the human reference: on the pieces with two or more
    annotators, each annotator is scored against the others with the same rates.

        python evaluate.py agreement [path/to/PIG/FingeringFiles]

  * ``compare`` -- paired comparison of two ``pig`` runs, piece by piece: the
    mean difference with a 95% bootstrap interval, how many pieces moved each way,
    and a two-sided Wilcoxon signed-rank test (``n`` = pieces that changed) with
    Holm-adjusted p-values over all the keys printed.  ``total_cost`` is compared
    only where both runs fingered every hand.  It warns when the runs came from
    different code or settings, or were scored under the old rule.

        python evaluate.py compare output/pig_split.json output/pig_joint-full.json
            [--subset test-30]

  * ``beamgap`` -- measure what the joint-full assigner's beam costs: on short
    excerpts of a MIDI file, compare the best joint cost found with the default
    beam against the exact optimum (``beam=None``, same boundary window).  The
    exact search is exponential, so excerpts are kept short (``--length``).

        python evaluate.py beamgap [data/some.mid] [--length 16] [--stride 50]

  * ``selftest`` -- assert properties on small synthetic examples (no data or
    model needed): the definitional ordering of the match rates; that an
    unpredicted note counts as a miss; that the
    difficulty measure scales with tempo; that Viterbi matches an exhaustive
    search on random inputs with sustained notes; that M_rec follows the
    original definition; that a held note out of reach is penalised; that octave
    folds stay between bass and melody; that an unfingerable first layer fails
    cleanly; and that a four-hand duet with a three-finger hand runs end to end
    through assignment, fingering and engraving.  When the PIG dataset is present
    it also checks that the first annotator's own fingering, mapped back to the
    notes the way a real run's is, scores 1.0 against itself on every piece.

        python evaluate.py selftest

Every table is written with a ``.meta.json`` beside it: the code fingerprint
(a hash of ``evaluate.py`` and ``src/``), the git commit and whether the tree was
dirty, the machine, and the settings of the run.

The DFS baselines (dynamic/graph) are exponential, so ``ablation`` skips
them when a hand's stream exceeds ``--max-dfs`` layers; Viterbi (exact, the
production solver) always runs.
"""

import argparse
import csv
import dataclasses
import datetime
import glob
import hashlib
import inspect
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time

from src.midi_reader import read_midi
from src.assigners import get_assigner, split_layers_by_hands
from src.assigners import joint_full
from src.solvers import get_solver
from src.solvers.base import SolverResult
from src.sheet_export import render_fingering_pdf
from src.sheet_reducer import DEFAULT_TARGET, reduce_score
from src.difficulty import DEFAULT_DELTA_T, note_difficulties
from src.hands import DEFAULT_HANDS, Hand
from src import costs
from src import metrics
from src import pig_loader
from src.costs import set_span_limits

ASSIGNERS = ("split", "joint-local", "joint-full")
SOLVERS = ("viterbi", "dynamic", "graph")
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PIG_ROOT = os.path.join(HERE, "PianoFingeringDataset_v1.2",
                                "PianoFingeringDataset_v1.2", "FingeringFiles")


# --------------------------------------------------------------------------- #
# Shared pipeline steps
# --------------------------------------------------------------------------- #

def assign_and_split(layers, assigner, hands):
    """Assign hands and partition the layers into per-hand streams."""
    labels = get_assigner(assigner)(layers, hands=hands).assign()
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


def clear_caches():
    """Empty the module-level memo caches.

    ``joint_full._chord_cost`` is an ``lru_cache`` that outlives one assigner, so a
    second run of the same piece in the same process would start with a warm cache
    and look faster than the first.  Clearing it before every timed run makes all
    runs start cold.  The cache also reads the span limits, so it must be emptied
    after :func:`src.costs.set_span_limits`.
    """
    joint_full._chord_cost.cache_clear()


# --------------------------------------------------------------------------- #
# Ablation mode
# --------------------------------------------------------------------------- #

def _flatten_difficulty(diff_stats, row):
    for name, stats in diff_stats.items():
        for key, val in stats.items():
            row[f"{name}_{key}"] = val


def run_ablation(midi_path, slice_n, max_dfs, delta_t=DEFAULT_DELTA_T,
                 target=DEFAULT_TARGET):
    """Ablate over (reduce x assigner x solver) on one MIDI file.

    Difficulty is a cost per second (:mod:`src.difficulty`), so every row records
    the tempo it was measured at and whether that tempo was read from the file or
    assumed (:class:`src.midi_reader.Tempo`): rows measured under an assumed tempo
    are not comparable with rows measured under a declared one.  ``reduce`` has
    three settings rather than two, so the tempo operation can be isolated from
    the paper's note edits.
    """
    hands = DEFAULT_HANDS
    all_layers, tempo = read_midi(midi_path)
    original = all_layers[:slice_n]
    rows = []

    # False: no reduction. "notes": the paper's two operations only.
    # "notes+tempo": plus the global tempo reduction of src.sheet_reducer.
    for reduce_on in (False, "notes", "notes+tempo"):
        if reduce_on:
            red = reduce_score(original, target=target, bpm=tempo.bpm,
                               delta_t=delta_t,
                               allow_tempo_reduction=(reduce_on == "notes+tempo"))
            layers = red.layers
            fidelity = metrics.reduction_fidelity(red, original)
        else:
            red, layers, fidelity = None, original, None

        # A reduction that slowed the piece down is *played* slower, so it must be
        # scored at the tempo it produced, not at the score's.
        measured_bpm = red.reduced_bpm if red else tempo.bpm

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
                hand_layers.get("R", []), vit["R"].path,
                bpm=measured_bpm, delta_t=delta_t)
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
                    "bpm": round(tempo.bpm, 3),
                    "tempo_declared": tempo.declared,
                    "tempo_factor": red.tempo_factor if red else 1.0,
                    "measured_bpm": round(measured_bpm, 3),
                    "delta_t": delta_t,
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


def _first_annotator_hand(gt, key):
    return next((h for h in gt[key]["hands"] if h is not None), None)


def oracle_labels(layers, gt, hands):
    """Hand labels of the first annotator (the ``oracle`` baseline).

    Notes the annotator leaves without a hand fall back to the fixed boundary.
    """
    fallback = get_assigner("fixed")(layers, hands=hands).assign()
    by_side = {h.side: h.name for h in hands}
    labels = {}
    for li, layer in enumerate(layers):
        for ni, (pitch, _end) in enumerate(layer["notes"]):
            side = _first_annotator_hand(gt, (li, pitch)) if (li, pitch) in gt else None
            labels[(li, ni)] = by_side.get(side, fallback[(li, ni)])
    return labels


def _signed(finger, hand):
    if finger is None or hand is None:
        return None
    return finger if hand == "R" else -finger


def hands_without(spec):
    """Default hands with one finger removed, e.g. ``"R4"`` (right ring finger)."""
    if not spec:
        return DEFAULT_HANDS
    side, finger = spec[0].upper(), int(spec[1:])
    return [Hand(h.name, h.side, tuple(f for f in h.fingers if f != finger),
                 h.register, h.group) if h.side == side else h
            for h in DEFAULT_HANDS]


def _assign_and_solve(layers, gt, assigner, solver, hands):
    if assigner == "oracle":
        labels = oracle_labels(layers, gt, hands)
        hand_layers = split_layers_by_hands(layers, labels, hands)
    else:
        labels, hand_layers = assign_and_split(layers, assigner, hands)
    return labels, hand_layers, solve_hands(hand_layers, hands, solver)


def evaluate_piece(paths, assigner, solver, hands=DEFAULT_HANDS, repeats=1):
    """Score one PIG piece; ``seconds`` is the median of ``repeats`` cold runs.

    Every run starts with empty caches (:func:`clear_caches`), and all runs must
    return the same hands and fingering -- a run that differs means the output
    depends on something other than the input, and the check stops there.
    """
    layers, gt = pig_loader.load_piece(paths)
    if not layers:
        return None
    times, first = [], None
    for _ in range(max(1, repeats)):
        clear_caches()
        t0 = time.perf_counter()
        labels, hand_layers, results = _assign_and_solve(layers, gt, assigner,
                                                         solver, hands)
        times.append(time.perf_counter() - t0)
        snapshot = (labels, {n: (r.cost, r.path) for n, r in results.items()})
        if first is None:
            first = snapshot
        assert snapshot == first, "two runs of the same piece gave different output"
    pred_finger, pred_hand = _predictions(layers, labels, hand_layers, results)
    side_of = {h.name: h.side for h in hands}

    keys = sorted(gt)
    n_ann = len(gt[keys[0]]["fingers"]) if keys else 0
    pred_f = [pred_finger.get(k) for k in keys]
    annotators = [[gt[k]["fingers"][a] for k in keys] for a in range(n_ann)]
    # unpredicted notes (a hand the solver could not finger) count as misses
    mr = metrics.match_rates(pred_f, annotators)

    # the same rates on the signed finger: hand and number must both agree
    pred_s = [_signed(pred_finger.get(k), side_of.get(pred_hand.get(k))) for k in keys]
    signed = [[_signed(gt[k]["fingers"][a], gt[k]["hands"][a]) for k in keys]
              for a in range(n_ann)]
    mr.update({"S_" + name[2:]: v
               for name, v in metrics.match_rates(pred_s, signed).items()})

    # hand accuracy against the first annotator that labels each note, and
    # against any annotator (annotators sometimes disagree on the hand)
    pred_h = [side_of.get(pred_hand.get(k)) for k in keys]
    truth_h = [_first_annotator_hand(gt, k) for k in keys]
    mr["hand_accuracy"] = metrics.hand_accuracy(pred_h, truth_h)
    mr["hand_accuracy_any"] = metrics.hand_accuracy_any(
        pred_h, [gt[k]["hands"] for k in keys])
    mr["coverage"] = sum(f is not None for f in pred_f) / len(keys) if keys else 0.0
    mr["total_cost"] = sum(r.cost for r in results.values())
    mr["seconds"] = statistics.median(times)
    # instants out of reach (cost >= 100) and hands with no fingering at all
    from src.costs import MAX_MOVE_COST_HARD
    from src.difficulty import layer_costs
    unreachable = failed = 0
    for h in hands:
        res = results[h.name]
        if res.cost == float("inf"):
            failed += 1
            continue
        stream = hand_layers.get(h.name, [])
        unreachable += sum(1 for c in layer_costs(stream, res.path, h.side)
                           if c >= MAX_MOVE_COST_HARD)
    mr["n_unreachable"] = unreachable
    mr["n_failed_hands"] = failed
    mr["n_notes"] = len(keys)
    mr["n_annotators"] = n_ann
    return mr


def run_pig(root, assigner, solver, hands=DEFAULT_HANDS, repeats=1):
    pieces = pig_loader.discover_pieces(root)
    if not pieces:
        raise SystemExit(f"No PIG *_fingering.txt files under {root!r}")
    rows = []
    for piece, paths in sorted(pieces.items()):
        res = evaluate_piece(paths, assigner, solver, hands, repeats)
        if res:
            res["piece"] = piece
            rows.append(res)
    return rows


# --------------------------------------------------------------------------- #
# Agreement mode: the annotators scored against each other
# --------------------------------------------------------------------------- #

def run_agreement(root):
    """Score every annotator against the other annotators of the same piece.

    A human reference for the match rates, measured with the same code as the
    estimates: on each piece with two or more annotators, each annotator in turn
    is the "estimate" and the rest are the ground truth; the rates are averaged
    over the annotators of the piece.  Only ``M_gen`` (and ``S_gen``) is directly
    comparable with an estimate's: the other rates take the best of, or combine,
    the references, and a human has one reference fewer than an estimate.
    """
    rows = []
    for piece, paths in sorted(pig_loader.discover_pieces(root).items()):
        if len(paths) < 2:
            continue
        _layers, gt = pig_loader.load_piece(paths)
        keys = sorted(gt)
        n_ann = len(paths)
        fingers = [[gt[k]["fingers"][a] for k in keys] for a in range(n_ann)]
        hands = [[gt[k]["hands"][a] for k in keys] for a in range(n_ann)]
        signed = [[_signed(f, h) for f, h in zip(fingers[a], hands[a])]
                  for a in range(n_ann)]
        per_annotator = []
        for a in range(n_ann):
            others = [i for i in range(n_ann) if i != a]
            r = metrics.match_rates(fingers[a], [fingers[i] for i in others])
            r.update({"S_" + name[2:]: v for name, v in metrics.match_rates(
                signed[a], [signed[i] for i in others]).items()})
            truth_first = [next((hands[i][j] for i in others if hands[i][j]), None)
                           for j in range(len(keys))]
            r["hand_accuracy"] = metrics.hand_accuracy(hands[a], truth_first)
            r["hand_accuracy_any"] = metrics.hand_accuracy_any(
                hands[a], [[hands[i][j] for i in others] for j in range(len(keys))])
            per_annotator.append(r)
        row = {k: sum(r[k] for r in per_annotator) / n_ann for k in per_annotator[0]}
        row.update({"piece": piece, "n_notes": len(keys), "n_annotators": n_ann})
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# Self-test: definitional properties, on synthetic input
# --------------------------------------------------------------------------- #

def _uniform_stream(n, ioi, pitches):
    """A uniform monophonic stream and a solved path over it.

    ``n`` onsets spaced ``ioi`` whole notes apart, cycling through ``pitches`` so
    every layer and every transition is identical -- which makes the cost in a
    window exactly proportional to the number of onsets it holds, and therefore to
    the window's width.  Returns ``(layers, path)`` in the shapes
    :func:`src.difficulty.note_difficulties` expects.
    """
    layers, path = [], []
    for i in range(n):
        pitch = pitches[i % len(pitches)]
        notes = [(pitch, (i + 1) * ioi)]
        layers.append({"time": i * ioi, "notes": notes})
        path.append((notes, (2 + i % 2,)))      # alternate two fingers
    return layers, path


def check_tempo_scaling(bpm=120.0, ioi=1 / 64, n=400, tol=0.05):
    """Difficulty is a time rate, so twice the tempo is twice the difficulty.

    The sanity check on the unit change in :mod:`src.difficulty`: with the score
    fixed, the measured difficulty must scale with the tempo it is played at
    (Nakamura & Yoshii 2018, §II.B.1 -- the rate exists "to include the dependence
    on tempo").

    Proportionality is exact only in the regime the measure is meant for, where the
    window holds many onsets: the window is centred *on* an onset, so one narrower
    than a single inter-onset interval still collects that onset's whole cost and
    the density stops falling.  This check therefore uses a dense uniform stream
    (``1/64``-note spacing, ~32 onsets per window at ``bpm``) and averages over the
    interior onsets, away from the ends of the stream where the window is clipped.
    A real score measured with a window of two or three onsets scales monotonically
    but coarsely -- worth knowing before reading a single difficulty figure as if it
    were proportional to tempo.
    """
    layers, path = _uniform_stream(n, ioi, (60, 64))
    rh_layers, rh_path = layers, path
    lh_layers, lh_path = _uniform_stream(n, ioi, (48, 52))

    def mean_interior(bpm):
        diffs = note_difficulties(layers, lh_layers, lh_path, rh_layers, rh_path,
                                  bpm=bpm, delta_t=DEFAULT_DELTA_T)
        interior = diffs[n // 4: 3 * n // 4]
        return sum(d[2] for d in interior) / len(interior)

    half, base, double = mean_interior(bpm / 2), mean_interior(bpm), mean_interior(bpm * 2)
    print(f"mean D_B on a uniform stream: {bpm / 2:.0f} BPM -> {half:.2f}, "
          f"{bpm:.0f} BPM -> {base:.2f}, {bpm * 2:.0f} BPM -> {double:.2f}")
    print(f"  ratios: doubling {base / half:.3f} and {double / base:.3f} (expect 2.0 "
          f"+/- {tol:.0%}); halving {half / base:.3f} (expect 0.5)")
    assert abs(base / half - 2.0) <= 2.0 * tol, "doubling the tempo must double D_B"
    assert abs(double / base - 2.0) <= 2.0 * tol, "doubling the tempo must double D_B"
    assert abs(half / base - 0.5) <= 0.5 * tol, "halving the tempo must halve D_B"
    return {"half": half, "base": base, "double": double}


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
    check_unpredicted_is_miss()
    check_tempo_scaling()
    print("OK: difficulty scales with tempo")
    check_mrec_definition()
    check_held_reach()
    check_fold_stays_inside()
    check_viterbi_exact()
    check_unfingerable_first_layer()
    check_duet_end_to_end()
    check_reduce_missing_finger()
    check_pig_identity()


def check_unpredicted_is_miss():
    """A note without a prediction stays in the denominator of every rate.

    Otherwise a variant whose solver fails on one hand would be scored on the
    other hand alone, and two variants would be scored on different notes.
    """
    mr = metrics.match_rates([1, None], [[1, 2]])
    assert all(abs(v - 0.5) < 1e-9 for v in mr.values()), mr
    assert metrics.hand_accuracy(["R", None], ["R", "L"]) == 0.5
    assert metrics.hand_accuracy_any([None, "L"], [["R", "L"], ["R", "L"]]) == 0.5
    print("OK: an unpredicted note counts as a miss")


def check_pig_identity(root=DEFAULT_PIG_ROOT):
    """Annotator 1's own fingering, mapped back like a real run, matches itself.

    Builds solver results from the first annotator's hands and fingers and sends
    them through the same steps as a real run (hand split, :func:`_predictions`,
    the match rates).  Every piece must score 1.0 against annotator 1 on the
    finger, the signed finger and the hand, with every note predicted.  Anything
    less is a bug in how predictions are mapped back to notes (onset rounding,
    chord grouping, the ``(layer, pitch)`` key), which would lower every variant's
    score without any error.
    """
    if not os.path.isdir(root):
        print(f"skip: identity check needs the PIG dataset at {root}")
        return
    hands = DEFAULT_HANDS
    side_of = {h.name: h.side for h in hands}
    pieces = pig_loader.discover_pieces(root)
    n_notes = 0
    for piece, paths in sorted(pieces.items()):
        layers, gt = pig_loader.load_piece(paths)
        labels = oracle_labels(layers, gt, hands)
        hand_layers = split_layers_by_hands(layers, labels, hands)
        # looked up by the layer's own onset, not through _predictions' mapping
        finger_of = {(layer["time"], pitch): gt[(li, pitch)]["fingers"][0]
                     for li, layer in enumerate(layers)
                     for pitch, _end in layer["notes"]}
        results = {h.name: SolverResult(cost=0.0, path=[
            (hl["notes"], tuple(finger_of[(hl["time"], p)] for p, _e in hl["notes"]))
            for hl in hand_layers.get(h.name, [])]) for h in hands}
        pred_finger, pred_hand = _predictions(layers, labels, hand_layers, results)
        keys = sorted(gt)
        pred_f = [pred_finger.get(k) for k in keys]
        pred_s = [_signed(pred_finger.get(k), side_of.get(pred_hand.get(k)))
                  for k in keys]
        first_f = [gt[k]["fingers"][0] for k in keys]
        first_s = [_signed(gt[k]["fingers"][0], gt[k]["hands"][0]) for k in keys]
        assert None not in pred_f, f"{piece}: notes without a prediction"
        assert metrics.match_rates(pred_f, [first_f])["M_gen"] == 1.0, piece
        assert metrics.match_rates(pred_s, [first_s])["M_gen"] == 1.0, piece
        assert metrics.hand_accuracy([side_of.get(pred_hand.get(k)) for k in keys],
                                     [gt[k]["hands"][0] for k in keys]) == 1.0, piece
        n_notes += len(keys)
    print(f"OK: annotator 1 scores 1.0 against itself after the pipeline's mapping "
          f"({len(pieces)} PIG pieces, {n_notes} notes)")


def check_mrec_definition():
    """M_rec follows Nakamura et al. (2020, Fig. 5 and Appendix A).

    On the paper's own example the best recombination switches twice, at notes
    where the two ground truths agree, and leaves two substitutions: 8/12.  A
    switch where the annotators disagree is not allowed, so a recombination that
    would need one cannot raise the rate.
    """
    gts = [[int(c) for c in s] for s in ("143252431343", "132142431253", "142152521252")]
    est = [int(c) for c in "232153521343"]
    m = metrics.match_rates(est, gts)["M_rec"]
    assert abs(m - 8 / 12) < 1e-9, m
    # first half matches annotator A, second half B, and they never agree:
    # no switch is allowed, so M_rec falls back to the better single annotator
    est = [1, 2, 3, 4]
    m = metrics.match_rates(est, [[1, 2, 5, 5], [5, 5, 3, 4]])["M_rec"]
    assert abs(m - 0.5) < 1e-9, m
    print("OK: M_rec reproduces the paper's example (8/12) and switches only "
          "where annotators agree")


def check_held_reach():
    """A held note out of reach of the new notes is let go, at a fixed cost.

    Holding C3 while the same hand plays C6 costs exactly the release cost more
    than playing C6 after C3 ends; holding C4 under E4 costs nothing; and the
    finger that let go is free for the next onset, so a five-note chord that
    follows is still fingerable.
    """
    from src.costs import HELD_RELEASE_COST
    def run(layers, name):
        return get_solver(name)(layers, hand="R").solve().cost
    held = [{"time": 0.0, "notes": [(48, 2.0)]}, {"time": 1.0, "notes": [(84, 2.0)]}]
    freed = [{"time": 0.0, "notes": [(48, 1.0)]}, {"time": 1.0, "notes": [(84, 2.0)]}]
    near = [{"time": 0.0, "notes": [(60, 2.0)]}, {"time": 1.0, "notes": [(64, 2.0)]}]
    near_freed = [{"time": 0.0, "notes": [(60, 1.0)]}, {"time": 1.0, "notes": [(64, 2.0)]}]
    chord = {"time": 1.5, "notes": [(72, 3.0), (74, 3.0), (76, 3.0), (77, 3.0), (79, 3.0)]}
    for name in ("viterbi", "graph"):
        assert abs(run(held, name) - run(freed, name) - HELD_RELEASE_COST) < 1e-9, name
        assert abs(run(near, name) - run(near_freed, name)) < 1e-9, name
        tail = [{"time": 0.0, "notes": [(48, 3.0)]},
                {"time": 1.0, "notes": [(84, 1.2)]}, chord]
        assert run(tail, name) < float("inf"), name
    print("OK: a held note out of reach is let go at a fixed cost and frees its finger")


def check_fold_stays_inside():
    """An octave fold never lands above the melody or below the bass."""
    from src.sheet_reducer import _plan_edit
    layers = [{"time": 0.0, "notes": [(48, 1.0), (60, 1.0), (69, 1.0)]}]
    # inner C4 of a two-note right hand (C4, A4): folding up would cross the melody
    assert _plan_edit(layers, 0, 60, [60, 69], 69, True, {}) == "del"
    layers = [{"time": 0.0, "notes": [(40, 1.0), (50, 1.0), (66, 1.0), (72, 1.0)]}]
    assert _plan_edit(layers, 0, 50, [50, 66, 72], 66, True, {}) == ("shift", 62)
    print("OK: octave folds stay between the bass and the melody")


def check_viterbi_exact(n_inputs=300, seed=0):
    """Viterbi must reach the exhaustive (plain DFS) optimum on every input.

    Random 3-7 layer inputs of 1-3 notes with sustained notes, so the held-finger
    part of the state matters.  This is the check behind the thesis' claim that
    the production solver is exact.
    """
    rng = random.Random(seed)
    viterbi, exhaustive = get_solver("viterbi"), get_solver("graph")
    feasible = 0
    for k in range(n_inputs):
        t, layers = 0.0, []
        for _ in range(rng.randint(3, 7)):
            pitches = sorted(rng.sample(range(55, 75), rng.choice((1, 1, 2, 3))))
            layers.append({"time": t, "notes": [
                (p, t + rng.choice((0.5, 1, 2, 3))) for p in pitches]})
            t += rng.choice((0.5, 1))
        cv = viterbi(layers, hand="R").solve().cost
        ce = exhaustive(layers, hand="R").solve().cost
        # both inf (held notes leave too few fingers) counts as agreement
        assert cv == ce or abs(cv - ce) < 1e-9, \
            f"input {k}: viterbi {cv} != exhaustive {ce}"
        feasible += cv != float("inf")
    print(f"OK: Viterbi matches exhaustive search on {n_inputs} random inputs "
          f"({feasible} fingerable, the rest unfingerable for both)")


def check_unfingerable_first_layer():
    """A first chord with more notes than fingers fails with cost inf, at layer 0."""
    chord = {"time": 0.0, "notes": [(60, 1.0), (62, 1.0), (64, 1.0), (65, 1.0)]}
    for layers in ([chord], [chord, {"time": 1.0, "notes": [(67, 2.0)]}]):
        res = get_solver("viterbi")(layers, hand="R", fingers=(1, 2, 3)).solve()
        assert res.cost == float("inf") and res.extras.get("failed_at") == 0, res
    print("OK: unfingerable first layer fails cleanly at layer 0")


def check_duet_end_to_end(midi_path="data/mond_1.mid", n_layers=60):
    """Four hands (one with three fingers) through assign -> finger -> engrave."""
    if not os.path.exists(midi_path):
        print(f"skip: duet check needs {midi_path}")
        return
    layers, _tempo = read_midi(midi_path)
    layers = layers[:n_layers]
    hands = [Hand("S-L", "L", register=41.0, group="Secondo"),
             Hand("S-R", "R", register=53.0, group="Secondo"),
             Hand("P-L", "L", register=67.0, group="Primo"),
             Hand("P-R", "R", fingers=(1, 2, 3), register=79.0, group="Primo")]
    labels, hand_layers = assign_and_split(layers, "joint-full", hands)
    assert set(labels.values()) <= {h.name for h in hands}
    paths = {}
    for h in hands:
        res = get_solver("viterbi")(hand_layers.get(h.name, []), hand=h.side,
                                    fingers=h.fingers).solve()
        assert res.cost < float("inf"), f"{h.name} unfingerable"
        used = {f for _notes, fs in res.path for f in fs}
        assert used <= set(h.fingers), f"{h.name} used fingers {used}"
        paths[h.name] = res.path
    with tempfile.TemporaryDirectory() as tmp:
        stem = os.path.join(tmp, "duet")
        render_fingering_pdf(hands, hand_layers, paths, out_path=stem,
                             run_lilypond=False)
        with open(stem + ".ly") as fh:
            ly = fh.read()
    assert ly.count("PianoStaff") == 2, "expected one grand staff per player"
    print("OK: four-hand duet (one three-finger hand) runs end to end")


def check_reduce_missing_finger(midi_path="data/mond_1.mid", n_layers=60):
    """The reducer measures the hands it is given, fingers missing or not.

    A right hand with only fingers 1-3 must be reduced to the same ceiling with
    those fingers alone: no onset left above it and no other finger used.  A
    duet is refused: the difficulty triplet belongs to one player's two hands.
    """
    if not os.path.exists(midi_path):
        print(f"skip: reducer check needs {midi_path}")
        return
    from src.sheet_reducer import _measure
    layers, tempo = read_midi(midi_path)
    layers = layers[:n_layers]
    full = reduce_score(layers, bpm=tempo.bpm)
    hands = [Hand("L", "L", register=53.0),
             Hand("R", "R", fingers=(1, 2, 3), register=67.0)]
    red = reduce_score(layers, bpm=tempo.bpm, hands=hands)
    _labels, diffs, _lh, rh, _lhl, _rhl = _measure(
        red.layers, DEFAULT_DELTA_T, "joint-local", tempo.bpm * red.tempo_factor, hands)
    used = {f for _notes, fs in rh.path for f in fs}
    assert used <= {1, 2, 3}, f"three-finger hand used fingers {used}"
    tl, tr, tb = DEFAULT_TARGET
    assert all(dl <= tl and dr <= tr and db <= tb for dl, dr, db in diffs), \
        "reduced score left above the ceiling for the three-finger hand"
    duet = [Hand("S-L", "L", register=41.0), Hand("S-R", "R", register=53.0),
            Hand("P-L", "L", register=67.0), Hand("P-R", "R", register=79.0)]
    try:
        reduce_score(layers, bpm=tempo.bpm, hands=duet)
    except ValueError:
        pass
    else:
        raise AssertionError("the reducer should refuse four hands")
    print(f"OK: reducer with a three-finger right hand ({len(red.deleted)} deleted, "
          f"{len(red.shifted)} shifted vs {len(full.deleted)}/{len(full.shifted)} "
          f"for a full hand); duet refused")


# --------------------------------------------------------------------------- #
# Beam gap of the joint-full assigner
# --------------------------------------------------------------------------- #

def run_beamgap(midi_path, length, stride, hands=DEFAULT_HANDS):
    """Beamed vs exact joint-full cost on ``length``-onset excerpts every ``stride``."""
    layers, _tempo = read_midi(midi_path)
    Assigner = get_assigner("joint-full")
    rows = []
    for start in range(0, max(1, len(layers) - length + 1), stride):
        excerpt = layers[start:start + length]
        timings = {}
        costs = {}
        for name, beam in (("beam", 32), ("exact", None)):
            a = Assigner(excerpt, hands=hands, beam=beam)
            t0 = time.perf_counter()
            a.assign()
            timings[name] = time.perf_counter() - t0
            costs[name] = a.total_cost
        gap = costs["beam"] - costs["exact"]
        rows.append({
            "start": start, "length": len(excerpt),
            "cost_beam": costs["beam"], "cost_exact": costs["exact"],
            "gap": gap,
            "rel_gap": gap / costs["exact"] if costs["exact"] else 0.0,
            "seconds_beam": round(timings["beam"], 3),
            "seconds_exact": round(timings["exact"], 3),
        })
        print(f"start={start:>4} beam={costs['beam']:>8.2f} "
              f"exact={costs['exact']:>8.2f} gap={gap:>6.2f} "
              f"({timings['beam']:.2f}s vs {timings['exact']:.2f}s)", flush=True)
    return rows


# --------------------------------------------------------------------------- #
# Statistics over pieces
# --------------------------------------------------------------------------- #

RATE_KEYS = ("M_gen", "M_high", "M_soft", "M_rec",
             "S_gen", "S_high", "S_soft", "S_rec", "hand_accuracy",
             "hand_accuracy_any")


def _summary(rows, key):
    """Mean, standard deviation and note-weighted mean of ``key`` over pieces."""
    vals = [r[key] for r in rows]
    n = len(vals)
    mean = sum(vals) / n
    sd = (sum((v - mean) ** 2 for v in vals) / (n - 1)) ** 0.5 if n > 1 else 0.0
    weights = [r["n_notes"] for r in rows]
    wmean = sum(v * w for v, w in zip(vals, weights)) / sum(weights)
    return mean, sd, wmean


def _check_runs(path_a, path_b, rows_a, rows_b):
    """Warn when two runs cannot be compared as they stand."""
    for path, rows in ((path_a, rows_a), (path_b, rows_b)):
        if "coverage" not in next(iter(rows.values())):
            print(f"WARNING: {path} was scored before unpredicted notes counted as "
                  f"misses; its rates are not comparable with a current run")
    metas = [read_meta(p) for p in (path_a, path_b)]
    for path, meta in zip((path_a, path_b), metas):
        if meta is None:
            print(f"WARNING: {path} has no .meta.json; the code that produced it is "
                  f"unknown")
        elif meta.get("git_dirty"):
            print(f"note: {path} ran on uncommitted code "
                  f"(fingerprint {meta['code_fingerprint'][:12]})")
    if all(metas):
        if metas[0]["code_fingerprint"] != metas[1]["code_fingerprint"]:
            print("WARNING: the two runs come from different code "
                  f"({metas[0]['code_fingerprint'][:12]} vs "
                  f"{metas[1]['code_fingerprint'][:12]}); a difference between them "
                  f"may come from the code change, not from the variant")
        pa, pb = metas[0]["params"], metas[1]["params"]
        diff = sorted(k for k in set(pa) | set(pb)
                      if k != "assigner" and pa.get(k) != pb.get(k))
        if diff:
            print(f"WARNING: the runs differ in more than the assigner: {diff}")


def run_compare(path_a, path_b, subset="all"):
    """Paired, piece-by-piece comparison of two ``pig`` runs.

    For every key: the means, the mean difference ``b - a`` with a 95% bootstrap
    interval over pieces, how many pieces moved each way, and the Wilcoxon test
    with ``n`` the pieces whose value changed (pieces with no change carry no
    information for the test).  The p-values are also given Holm-adjusted over all
    the keys printed, since they are read together.  ``total_cost`` is compared
    only on the pieces where both runs fingered every hand: on the others it is
    infinite.
    """
    rows_a = {r["piece"]: r for r in json.load(open(path_a))}
    rows_b = {r["piece"]: r for r in json.load(open(path_b))}
    _check_runs(path_a, path_b, rows_a, rows_b)
    common = sorted(set(rows_a) & set(rows_b))
    if subset == "test-30":
        common = [p for p in common if int(p) <= 30]
    print(f"{len(common)} pieces in common ({subset}): a={path_a}  b={path_b}")
    for name, rows in (("a", rows_a), ("b", rows_b)):
        if "n_failed_hands" in rows[common[0]]:
            failed = [p for p in common if rows[p]["n_failed_hands"]]
            print(f"  {name}: a hand left unfingered in {len(failed)} pieces {failed}")

    tests = []
    for key in RATE_KEYS + ("coverage", "total_cost", "seconds"):
        if key not in rows_a[common[0]] or key not in rows_b[common[0]]:
            continue
        pieces = common
        if key == "total_cost":
            pieces = [p for p in common if rows_a[p][key] != float("inf")
                      and rows_b[p][key] != float("inf")]
        a = [rows_a[p][key] for p in pieces]
        b = [rows_b[p][key] for p in pieces]
        diff = [y - x for x, y in zip(a, b)]
        tests.append((key, pieces, a, b, diff, metrics.wilcoxon_signed_rank(a, b),
                      metrics.bootstrap_mean_ci(diff)))
    p_holm = metrics.holm([t[5]["p"] for t in tests])

    def num(v, sign=""):
        return f"{v:{sign}.3f}" if abs(v) < 100 else f"{v:{sign}.1f}"

    print(f"{'':18}{'a':>9}{'b':>9}{'b-a':>9}  {'95% CI':20}{'b>a':>5}{'b<a':>5}"
          f"{'n':>5}{'z':>7}{'p':>8}{'p_holm':>8}")
    for (key, pieces, a, b, diff, test, (lo, hi)), ph in zip(tests, p_holm):
        label = key if len(pieces) == len(common) else f"{key}[{len(pieces)}]"
        ci = f"[{num(lo, '+')}, {num(hi, '+')}]"
        print(f"{label:18}{num(sum(a) / len(a)):>9}{num(sum(b) / len(b)):>9}"
              f"{num(sum(diff) / len(diff), '+'):>9}  {ci:20}"
              f"{sum(d > 0 for d in diff):5}{sum(d < 0 for d in diff):5}"
              f"{test['n']:5}{test['z']:+7.2f}{test['p']:8.4f}{ph:8.4f}")
        if key == "total_cost":
            dearer = [p for p, d in zip(pieces, diff) if d > 1e-9]
            print(f"{'':18}b costs more than a on {len(dearer)} pieces: {dearer}")
    print("[k] after a key: compared on k pieces only (finite cost in both runs)")


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def _git(*cmd):
    try:
        return subprocess.run(["git", *cmd], cwd=HERE, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def code_fingerprint():
    """SHA-256 over ``evaluate.py`` and every ``src/**/*.py`` (path and content).

    Identifies the code that produced a table even when it is not committed:
    two runs with the same fingerprint ran the same code, whatever git says.
    """
    files = sorted(glob.glob(os.path.join(HERE, "src", "**", "*.py"), recursive=True))
    h = hashlib.sha256()
    for path in [os.path.join(HERE, "evaluate.py")] + files:
        h.update(os.path.relpath(path, HERE).encode() + b"\0")
        with open(path, "rb") as fh:
            h.update(fh.read() + b"\0")
    return h.hexdigest()


def _cpu_model():
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def provenance(args, hands=DEFAULT_HANDS):
    """What produced a table: code version, machine, and every setting it ran with.

    The constants listed are the ones a run's result depends on that are not
    command-line options; the cost weights written inside functions are covered by
    the code fingerprint.
    """
    jf_defaults = {k: v.default for k, v in
                   inspect.signature(joint_full.JointFullAssigner.__init__)
                   .parameters.items() if v.default is not inspect.Parameter.empty
                   and k != "hands"}
    pairs = lambda d: {f"{a}-{b}": v for (a, b), v in sorted(d.items())}
    params = {k: v for k, v in vars(args).items()
              if k not in ("out", "root", "midi", "a", "b")}
    params.update({
        "hands": [dataclasses.asdict(h) for h in hands],
        "max_comfort": pairs(costs.MAX_COMFORT),
        "max_abs": pairs(costs.MAX_ABS),
        "held_release_cost": costs.HELD_RELEASE_COST,
        "max_move_cost_hard": costs.MAX_MOVE_COST_HARD,
        "group_eps": pig_loader.GROUP_EPS,
        "joint_full_defaults": jf_defaults,
        "default_target": list(DEFAULT_TARGET),
        "default_delta_t": DEFAULT_DELTA_T,
    })
    status = _git("status", "--porcelain", "--", "evaluate.py", "src")
    return {
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "argv": sys.argv,
        "data": getattr(args, "root", None) or getattr(args, "midi", None),
        "code_fingerprint": code_fingerprint(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": _cpu_model(),
        "params": params,
    }


def read_meta(out_path):
    """The provenance written next to a table (``x.json`` -> ``x.meta.json``)."""
    stem = out_path[:-len(".json")] if out_path.endswith(".json") else out_path
    try:
        with open(stem + ".meta.json") as fh:
            return json.load(fh)
    except OSError:
        return None


def write_table(rows, out_stem, meta=None):
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
    written = f"{out_stem}.csv and {out_stem}.json"
    if meta is not None:
        with open(out_stem + ".meta.json", "w") as fh:
            json.dump(meta, fh, indent=2, default=str)
        written += " (+ .meta.json)"
    print(f"Wrote {written} ({len(rows)} rows)")


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
    p.add_argument("root", nargs="?", default=DEFAULT_PIG_ROOT)
    p.add_argument("--assigner", default="joint-full",
                   choices=ASSIGNERS + ("fixed", "oracle"))
    p.add_argument("--solver", default="viterbi", choices=SOLVERS)
    p.add_argument("--limits", default="tcc", choices=("tcc", "parncutt"),
                   help="span limits of the thumb pairs (sensitivity experiment)")
    p.add_argument("--remove-finger", default=None,
                   help='remove one finger from one hand, e.g. "R4" (needs a '
                        'coupled assigner)')
    p.add_argument("--repeats", type=int, default=1,
                   help="cold runs per piece; 'seconds' is their median")
    p.add_argument("--out", default="output/eval_pig")

    g = sub.add_parser("agreement")
    g.add_argument("root", nargs="?", default=DEFAULT_PIG_ROOT)
    g.add_argument("--out", default="output/eval_agreement")

    b = sub.add_parser("beamgap")
    b.add_argument("midi", nargs="?", default="data/mond_1.mid")
    b.add_argument("--length", type=int, default=16,
                   help="onsets per excerpt (the exact search is exponential)")
    b.add_argument("--stride", type=int, default=50,
                   help="onsets between excerpt starts")
    b.add_argument("--out", default="output/eval_beamgap")

    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--subset", default="all", choices=("all", "test-30"))

    sub.add_parser("selftest")

    args = ap.parse_args()

    if args.mode == "selftest":
        run_selftest()
        return

    if args.mode == "compare":
        run_compare(args.a, args.b, args.subset)
        return

    hands = DEFAULT_HANDS
    if args.mode == "pig":
        set_span_limits(args.limits)
        clear_caches()
        hands = hands_without(args.remove_finger)
    # taken before the run, so a file edited while it runs is not credited to it
    meta = provenance(args, hands)

    if args.mode == "agreement":
        rows = run_agreement(args.root)
        for subset, sel in (("all", rows),
                            ("test-30", [r for r in rows if int(r["piece"]) <= 30])):
            if sel:
                print(f"{subset} ({len(sel)} pieces with 2+ annotators): " + "  ".join(
                    "{}={:.3f}±{:.3f} (w {:.3f})".format(k, *_summary(sel, k))
                    for k in RATE_KEYS))
        write_table(rows, args.out, meta)
        return

    if args.mode == "beamgap":
        rows = run_beamgap(args.midi, args.length, args.stride)
        if rows:
            n = len(rows)
            hit = sum(1 for r in rows if r["gap"] <= 1e-9)
            print("-" * 60)
            print(f"{hit}/{n} excerpts at the exact optimum; "
                  f"max gap {max(r['gap'] for r in rows):.2f}, "
                  f"mean relative gap {sum(r['rel_gap'] for r in rows) / n:.2%}")
        write_table(rows, args.out, meta)
        return

    if args.mode == "ablation":
        rows = run_ablation(args.midi, args.slice, args.max_dfs)
        for r in rows:
            print(f"reduce={r['reduce']!s:11} {r['assigner']:11} {r['solver']:8} "
                  f"cost={r['total_cost']:>8.1f} gap={r['optimality_gap']:>6.1f} "
                  f"D_B_p90={r.get('D_B_p90', 0):>6.1f} "
                  f"tempo={r['tempo_factor']:>4.0%} "
                  f"visits={r['node_visits']:>8} {r['seconds']:>7.3f}s")
        write_table(rows, args.out, meta)
        return

    if args.mode == "pig":
        rows = run_pig(args.root, args.assigner, args.solver, hands, args.repeats)
        if rows:
            for r in rows:
                flag = (f"  FAILED {r['n_failed_hands']} hand(s), coverage "
                        f"{r['coverage']:.0%}" if r["n_failed_hands"] else "")
                print(f"{r['piece']:24} " + " ".join(
                    f"{k}={r[k]:.3f}" for k in RATE_KEYS) + f"  (n={r['n_notes']})"
                    + flag)
            print("-" * 60)
            for subset, sel in (("all", rows),
                                ("test-30", [r for r in rows if int(r["piece"]) <= 30])):
                if not sel:
                    continue
                print(f"{subset} ({len(sel)} pieces): " + "  ".join(
                    "{}={:.3f}±{:.3f} (w {:.3f})".format(k, *_summary(sel, k))
                    for k in RATE_KEYS))
            failed = [r["piece"] for r in rows if r["n_failed_hands"]]
            print(f"a hand left unfingered in {len(failed)} pieces {failed}; "
                  f"its notes count as misses")
            secs = [r["seconds"] for r in rows]
            print(f"time: {sum(secs):.1f} s in all, median {statistics.median(secs):.3f}"
                  f" s per piece (each the median of {args.repeats} cold run(s))")
        write_table(rows, args.out, meta)
        return


if __name__ == "__main__":
    main()
