"""Fit the model parameters that no source fixes, on PIG pieces 031-150.

The parameters, their hand-picked starting values and the grid each one is
searched on are in :mod:`src.params`, with the reasons why the remaining chosen
numbers are not fitted.  Pieces 001-030, the test set of Nakamura, Saito &
Yoshii (2020), are never loaded here (:data:`src.pig_loader.TEST_PIECES`).

Stages, run in this order by ``all`` (``cost``, ``stability`` for each assigner,
then ``ceiling``):

  * ``cost``      -- the weights of the ergonomic cost, with the annotators' own
                     hands (assigner ``oracle``: only the fingering is chosen),
                     so they favour no hand assigner; maximises the mean M_gen
                     over the 120 training pieces.
  * ``stability`` -- the boundary-stability weight of one assigner (``--variant``;
                     for ``split`` also its cohesion penalty), with the fitted
                     cost weights; maximises the mean S_gen, where hand and
                     finger must both agree.
  * ``ceiling``   -- re-measures the difficulty ceiling with the weights in
                     force: the 90th percentile of the per-onset difficulty of
                     each hand and of both, pooled over the training pieces,
                     with ``joint-local`` (``src.sheet_reducer``); not a fit, a
                     measurement.  It depends on the cost weights and on
                     ``smooth_local``, so every run ends with it.

Search: coordinate descent.  Starting from the hand-picked values, each round
tries every grid value of each parameter in turn, the others held fixed, and
keeps the best (a tie keeps the current value); it stops after a round that
changes nothing, or after ``--rounds`` rounds.  A best value that is the largest
one on its grid is reported (and recorded in ``parametros.json``): the best
setting may lie beyond the grid, which should then be extended.  Every trial is the mean of the
metric over the training pieces, evaluated in parallel (``--processes``), and
cached, so no setting is scored twice.

Output: ``parametros.json`` at the repository root (the values, the ceiling and
how they were obtained), which ``main.py`` and ``evaluate.py`` then use by
default; and a CSV of every trial in ``output/otimizacao/``.

    python otimizar.py all [--processes N]
    python otimizar.py cost [--processes N] [--rounds R]
    python otimizar.py ceiling [--processes N]
    python otimizar.py stability --variant joint-full [--processes N]

``evaluate.py --params hand-picked ...`` runs the evaluation with the starting
values instead, which is how the effect of the fit is measured on pieces 001-030.
"""

import argparse
import csv
import datetime
import multiprocessing
import os
import sys
import time

import evaluate
from src import params, pig_loader
from src.difficulty import DEFAULT_DELTA_T
from src.hands import DEFAULT_HANDS
from src.sheet_reducer import _measure, _percentile, condense

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "output", "otimizacao")
PIG_BPM = 240.0      # PIG times are seconds: one whole note per second (pig_loader)


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

def training_pieces(root=evaluate.DEFAULT_PIG_ROOT):
    """``[(piece_id, paths), ...]`` for PIG pieces 031-150, never 001-030."""
    pieces = pig_loader.discover_pieces(root)
    train = [(p, pieces[p]) for p in sorted(pieces) if p not in pig_loader.TEST_PIECES]
    if any(p in pig_loader.TEST_PIECES for p, _ in train):
        raise AssertionError("a test piece reached the training set")
    return train


# --------------------------------------------------------------------------- #
# Workers (top level so the process pool can import them)
# --------------------------------------------------------------------------- #

def _score_piece(task):
    paths, assigner, values, metric = task
    params.set(**values)
    row = evaluate.evaluate_piece(paths, assigner, "viterbi", DEFAULT_HANDS)
    return None if row is None else row[metric]


def _piece_difficulties(task):
    paths, values = task
    params.set(**values)
    layers, _gt = pig_loader.load_piece(paths)
    layers, _mult = condense(layers)
    _labels, diffs, *_ = _measure(layers, DEFAULT_DELTA_T, "joint-local", PIG_BPM)
    return diffs


# --------------------------------------------------------------------------- #
# Scoring and search
# --------------------------------------------------------------------------- #

class Scorer:
    """Mean of one metric over the training pieces, for a given setting."""

    def __init__(self, pieces, assigner, metric, pool, log_path):
        self.pieces, self.assigner, self.metric = pieces, assigner, metric
        self.pool, self.cache, self.trials = pool, {}, 0
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._log_header = not os.path.exists(log_path)

    def __call__(self, values):
        key = tuple(sorted(values.items()))
        if key in self.cache:
            return self.cache[key]
        t0 = time.time()
        tasks = [(paths, self.assigner, values, self.metric) for _p, paths in self.pieces]
        scores = [s for s in self.pool.map(_score_piece, tasks) if s is not None]
        mean = sum(scores) / len(scores)
        self.cache[key] = mean
        self.trials += 1
        self._log(values, mean, len(scores), time.time() - t0)
        return mean

    def _log(self, values, mean, n, seconds):
        names = sorted(values)
        with open(self.log_path, "a", newline="") as fh:
            w = csv.writer(fh)
            if self._log_header:
                w.writerow(["created", "assigner", "metric", "pieces", "score", "seconds"] + names)
                self._log_header = False
            w.writerow([datetime.datetime.now().isoformat(timespec="seconds"),
                        self.assigner, self.metric, n, f"{mean:.6f}",
                        f"{seconds:.1f}"] + [values[k] for k in names])


def coordinate_descent(score, start, names, rounds):
    """Best values for ``names`` (the others fixed at ``start``), and its score."""
    best = dict(start)
    best_score = score(best)
    first_score = best_score
    for r in range(1, rounds + 1):
        changed = False
        for name in names:
            grid = sorted(set(params.GRID[name]) | {best[name]})
            for v in grid:
                trial = {**best, name: float(v)}
                s = score(trial)
                print(f"  round {r}  {name:22s} = {v:<6g} {score.metric} = {s:.5f}"
                      f"{'  *' if s > best_score + 1e-12 else ''}", flush=True)
                if s > best_score + 1e-12:
                    best, best_score, changed = trial, s, True
        if not changed or len(names) == 1:     # one parameter: one round suffices
            break
    return best, first_score, best_score, r


def at_upper_edge(values, names):
    """The parameters whose value is the largest on their grid."""
    edge = [n for n in names if values[n] >= max(params.GRID[n])]
    for n in edge:
        print(f"WARNING: {n} = {values[n]:g} is the largest value on its grid; "
              f"the best value may lie beyond it", flush=True)
    return edge


def measure_ceiling(pieces, values, pool):
    """p90 of the per-onset (D_L, D_R, D_B), pooled over ``pieces``."""
    per_piece = pool.map(_piece_difficulties, [(paths, values) for _p, paths in pieces])
    pooled = [d for diffs in per_piece for d in diffs]
    return tuple(_percentile([d[i] for d in pooled], 90) for i in range(3))


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #

def _meta_base():
    return {
        "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        "git_commit": evaluate._git("rev-parse", "HEAD"),
        "code_fingerprint": evaluate.code_fingerprint(),
        "training_pieces": "PIG 031-150 (120 pieces)",
        "excluded_pieces": "PIG 001-030, the test set of Nakamura, Saito & Yoshii (2020)",
    }


def _load_existing():
    """Values, ceiling and stage records already in parametros.json, if any."""
    import json
    if not os.path.exists(params.OPTIMIZED_FILE):
        return dict(params.HAND_PICKED), list(params.HAND_PICKED_CEILING), {}
    with open(params.OPTIMIZED_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    values = {**params.HAND_PICKED, **data["values"]}
    return values, data.get("ceiling", list(params.HAND_PICKED_CEILING)), \
        data.get("meta", {}).get("stages", {})


def _save(values, ceiling, stages):
    meta = {**_meta_base(), "stages": stages}
    params.save(params.OPTIMIZED_FILE, values, ceiling, meta)
    print(f"wrote {os.path.relpath(params.OPTIMIZED_FILE, ROOT)}")


def stage_cost(pieces, pool, rounds):
    values, ceiling, stages = _load_existing()
    start = {**values, **{k: params.HAND_PICKED[k] for k in params.COST_PARAMS}}
    score = Scorer(pieces, "oracle", "M_gen", pool, os.path.join(LOG_DIR, "custo.csv"))
    print(f"cost stage: {len(params.COST_PARAMS)} parameters, assigner oracle, M_gen")
    best, before, after, used = coordinate_descent(score, start, params.COST_PARAMS, rounds)
    stages["cost"] = {"metric": "M_gen", "assigner": "oracle", "search": "coordinate descent",
                      "rounds": used, "trials": score.trials,
                      "start": {k: start[k] for k in params.COST_PARAMS},
                      "score_start": round(before, 6), "score_best": round(after, 6),
                      "at_upper_edge": at_upper_edge(best, params.COST_PARAMS)}
    _save(best, ceiling, stages)
    print(f"M_gen {before:.5f} -> {after:.5f} ({score.trials} trials)")
    return best


def stage_ceiling(pieces, pool):
    values, _old, stages = _load_existing()
    ceiling = measure_ceiling(pieces, values, pool)
    stages["ceiling"] = {"what": "p90 of per-onset D_L, D_R, D_B pooled over the training "
                                 "pieces, notes only, joint-local, bpm 240, window 1 s",
                         "value": [round(c, 6) for c in ceiling]}
    _save(values, ceiling, stages)
    print("ceiling (D_L, D_R, D_B):", tuple(round(c, 2) for c in ceiling))
    return ceiling


def stage_stability(pieces, pool, variant, rounds):
    values, ceiling, stages = _load_existing()
    names = params.STABILITY_PARAMS[variant]
    start = {**values, **{k: params.HAND_PICKED[k] for k in names}}
    score = Scorer(pieces, variant, "S_gen", pool,
                   os.path.join(LOG_DIR, f"estabilidade-{variant}.csv"))
    print(f"stability stage: {names}, assigner {variant}, S_gen")
    best, before, after, used = coordinate_descent(score, start, names, rounds)
    stages[f"stability/{variant}"] = {"metric": "S_gen", "assigner": variant,
                                      "search": "coordinate descent", "rounds": used,
                                      "trials": score.trials,
                                      "start": {k: start[k] for k in names},
                                      "score_start": round(before, 6),
                                      "score_best": round(after, 6),
                                      "at_upper_edge": at_upper_edge(best, names)}
    _save({**values, **{k: best[k] for k in names}}, ceiling, stages)
    print(f"S_gen {before:.5f} -> {after:.5f} ({score.trials} trials)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=("all", "cost", "ceiling", "stability"))
    ap.add_argument("--variant", choices=sorted(params.STABILITY_PARAMS),
                    help="assigner whose stability is fitted (stage stability)")
    ap.add_argument("--processes", type=int, default=None,
                    help="parallel workers (default: all CPUs, 4 for joint-full)")
    ap.add_argument("--rounds", type=int, default=4,
                    help="maximum rounds of coordinate descent")
    ap.add_argument("--root", default=evaluate.DEFAULT_PIG_ROOT,
                    help="PIG FingeringFiles folder")
    args = ap.parse_args()
    if args.stage == "stability" and not args.variant:
        ap.error("stage stability needs --variant")

    pieces = training_pieces(args.root)
    print(f"{len(pieces)} training pieces ({pieces[0][0]}-{pieces[-1][0]}); "
          f"test pieces 001-030 excluded")
    cpus = os.cpu_count() or 2

    def pool_for(variant):
        n = args.processes or (min(4, cpus) if variant == "joint-full" else cpus)
        return multiprocessing.Pool(n)

    if args.stage in ("all", "cost"):
        with pool_for("oracle") as pool:
            stage_cost(pieces, pool, args.rounds)
    variants = (["split", "joint-local", "joint-full"] if args.stage == "all"
                else [args.variant] if args.stage == "stability" else [])
    for v in variants:
        with pool_for(v) as pool:
            stage_stability(pieces, pool, v, args.rounds)
    with pool_for("joint-local") as pool:      # every run ends with the ceiling
        stage_ceiling(pieces, pool)


if __name__ == "__main__":
    main()
