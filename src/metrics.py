"""Evaluation metrics for the fingering pipeline.

This module does not introduce any new model: it aggregates quantities the
pipeline already produces (:mod:`src.costs`, :mod:`src.difficulty`,
:mod:`src.sheet_reducer`, the solver ``SolverResult``) into the numbers the
thesis reports.  Four families:

1. **Fingering difficulty / playability** (intrinsic, no ground truth) --
   :func:`difficulty_stats`, :func:`solver_stats`.  The ergonomic cost *per
   second* of :mod:`src.difficulty`, read out as a distribution instead of an
   optimisation target -- so a distribution is only comparable with another one
   measured at the same tempo and window.

2. **Reduction fidelity & efficacy** -- :func:`reduction_fidelity`,
   :func:`target_satisfaction`.  Fidelity is note-preservation + edit-severity,
   weighted by the musical-importance term ``h(m)`` of the reducer
   (Nakamura & Yoshii, *Statistical Piano Reduction Controlling Performance
   Difficulty*, APSIPA Trans. 7 (2018), eq. (13), (22)), *plus* the tempo factor
   the reducer applied -- a second, non-commensurable fidelity axis (see
   :func:`reduction_fidelity`).

3. **Fingering accuracy vs. ground truth** -- :func:`match_rates`,
   :func:`hand_accuracy`, :func:`hand_accuracy_any`.  The match-rate family of
   Nakamura, Saito & Yoshii, *Statistical Learning and Estimation of Piano
   Fingering*, Information Sciences 517 (2020): general / highest / soft /
   recombination match rate against multiple annotators.

4. **Paired comparison of two runs** -- :func:`wilcoxon_signed_rank`,
   :func:`bootstrap_mean_ci`, :func:`holm`.  Piece-by-piece tests of whether one
   variant scores higher than another, an interval for the size of the
   difference, and the correction for reading many such tests together.

Every function is a pure aggregation over data structures the pipeline already
returns, so it never changes solver/assigner/reducer behaviour.
"""

from .sheet_reducer import condense, _skyline_bassline, _importance

INF = float("inf")


# --------------------------------------------------------------------------- #
# 1. Fingering difficulty / playability
# --------------------------------------------------------------------------- #

def percentile(values, p):
    """``p``-th percentile (linear interpolation) of the *finite* ``values``.

    Infinite difficulties -- onsets the solver could not finger, i.e. exactly the
    spots reduction must fix -- are dropped so the scale reflects playable
    material; count them separately with ``n_inf``.  Mirrors
    :func:`src.difficulty` / ``sheet_reducer._percentile`` so the numbers match
    ``difficulty_profile``.
    """
    vals = sorted(v for v in values if v != INF)
    if not vals:
        return INF
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def difficulty_stats(diffs, percentiles=(50, 90, 100)):
    """Distribution of the per-onset ``(D_L, D_R, D_B)`` difficulty triplet.

    ``diffs`` is the list returned by :func:`src.difficulty.note_difficulties`.
    Returns ``{"D_L": {...}, "D_R": {...}, "D_B": {...}}`` where each entry has
    ``min``, the requested percentiles (``p50`` ...), and ``n_inf`` (onsets no
    finger assignment could play).
    """
    out = {}
    for name, idx in (("D_L", 0), ("D_R", 1), ("D_B", 2)):
        vals = [d[idx] for d in diffs]
        finite = [v for v in vals if v != INF]
        stats = {"min": min(finite) if finite else INF}
        for p in percentiles:
            stats[f"p{int(p)}"] = percentile(vals, p)
        stats["n_inf"] = sum(1 for v in vals if v == INF)
        out[name] = stats
    return out


def solver_stats(results_by_hand):
    """Cost and search-cost summary over a config's per-hand solver results.

    ``results_by_hand`` maps ``hand.name -> SolverResult``.  Returns total and
    per-hand fingering cost (the objective the solvers minimise), plus the search
    metrics ``node_visits`` and ``peak_states`` (summed across hands).  ``feasible``
    is False when any hand's search failed (cost ``inf``).
    """
    costs = {name: r.cost for name, r in results_by_hand.items()}
    total = sum(costs.values()) if costs else 0.0
    node_visits = sum(r.node_visits for r in results_by_hand.values())
    peak_states = sum(r.extras.get("peak_states", 0)
                      for r in results_by_hand.values())
    return {
        "total_cost": total,
        "cost_by_hand": costs,
        "node_visits": node_visits,
        "peak_states": peak_states,
        "feasible": all(c != INF for c in costs.values()),
    }


# --------------------------------------------------------------------------- #
# 2. Reduction fidelity & efficacy
# --------------------------------------------------------------------------- #

def reduction_fidelity(reduce_result, original_layers, a=0.01):
    """How faithful a reduction is to the original score.

    Fidelity = note-preservation + edit-severity, weighted by musical importance
    (the reducer's ``h(m) = a*Mult(m) + I(melodic) + I(bass)``).  ``original_layers``
    is the score *before* reduction (any format from :mod:`src.midi_reader`); it is
    condensed here so counts line up with ``reduce_result`` (which is keyed on the
    condensed score).

    Returns:
      * ``note_preservation`` -- retained / original notes (a shifted note counts
        as retained, only relocated by an octave).
      * ``deletion_rate`` / ``shift_rate`` -- edit severity, deletion being the
        harsher (content-removing) edit.
      * ``importance_weighted_preservation`` -- ``Σ h(m) over unedited / Σ h(m)
        over all``; near 1.0 means edits fell on low-importance inner voices and
        spared the melody/bass (which the reducer protects, so this is >= the raw
        preservation rate).
      * ``additional_note_rate`` -- ``A_add`` from the reducer (eq. (22)), passed
        through.
      * ``tempo_factor`` -- the global tempo the reduction applied, as a fraction
        of the score's own (1.0 = untouched).

    **Read ``tempo_factor`` next to the note figures, never instead of them.**  The
    reducer's third operation (:mod:`src.sheet_reducer`) buys difficulty by slowing
    the piece down, which *raises* every note-based number here: a reduction that
    preserved 98% of the notes at 50% tempo is not more faithful than one that
    preserved 90% at full tempo, it is differently unfaithful.  Allingham &
    Wöllner (2023) report the intended tempo as essential to a piece's character
    for their respondents, so the tempo factor is a fidelity loss on its own axis,
    with no exchange rate against deleted notes.  These two numbers are reported
    side by side for exactly that reason and must not be collapsed into one score.
    """
    orig, mult = condense(original_layers)
    melody, bass = _skyline_bassline(orig)
    total = sum(len(layer["notes"]) for layer in orig)

    deletions = len(reduce_result.deleted)
    shifts = len(reduce_result.shifted)
    edited = set(reduce_result.deleted)
    edited |= {(li, old) for (li, old, _new) in reduce_result.shifted}

    num = den = 0.0
    for li, layer in enumerate(orig):
        for pitch, _end in layer["notes"]:
            h = _importance(li, pitch, melody, bass, mult, a)
            den += h
            if (li, pitch) not in edited:
                num += h

    return {
        "orig_notes": total,
        "deletions": deletions,
        "shifts": shifts,
        "note_preservation": 1.0 - deletions / total if total else 1.0,
        "deletion_rate": deletions / total if total else 0.0,
        "shift_rate": shifts / total if total else 0.0,
        "importance_weighted_preservation": num / den if den else 1.0,
        "additional_note_rate": reduce_result.additional_note_rate,
        "tempo_factor": reduce_result.tempo_factor,
    }


def target_satisfaction(diffs, target):
    """Fraction of onsets whose difficulty is within the reduction budget.

    An onset satisfies the budget when none of its three difficulties is above its
    ceiling, ``D_L <= D̃_L ∧ D_R <= D̃_R ∧ D_B <= D̃_B`` (Nakamura & Yoshii eq. (14),
    with ``<`` there).  The equality matters here: the costs are integers and the
    window is 1 s, so many onsets sit exactly on a ceiling (a 90th percentile of the
    same values), and the reducer (:func:`src.sheet_reducer._overage`) only edits an
    onset strictly above one.  Counting the tie as a violation would report as
    failed an onset the reducer, by its own rule, had no reason to touch.  ``diffs`` is a per-onset ``(D_L, D_R, D_B)``
    list, ``target`` the ``(D̃_L, D̃_R, D̃_B)`` ceiling.  Reports the satisfaction
    rate and ``n_violations``; the efficacy side of the fidelity/difficulty
    trade-off (pair it with :func:`reduction_fidelity`).
    """
    tl, tr, tb = target
    if not diffs:
        return {"satisfaction_rate": 1.0, "n_violations": 0, "n_onsets": 0}
    violations = sum(1 for dl, dr, db in diffs
                     if not (dl <= tl and dr <= tr and db <= tb))
    n = len(diffs)
    return {
        "satisfaction_rate": (n - violations) / n,
        "n_violations": violations,
        "n_onsets": n,
    }


# --------------------------------------------------------------------------- #
# 3. Fingering accuracy vs. ground truth (PIG)
# --------------------------------------------------------------------------- #

def _match_rate(pred, truth):
    """Fraction of the notes ``truth`` labels where ``pred[i] == truth[i]``.

    A note the annotator left unlabelled (``truth[i] is None``) is excluded.  A note
    the estimate left unpredicted (``pred[i] is None``, e.g. every note of a hand
    the solver could not finger) stays in the denominator and counts as a miss, so
    every variant is scored on the same notes.  Excluding it instead would score a
    variant that fails on a hard passage only on the notes it did finger, and the
    comparison between variants would depend on which of them fails where.
    """
    matched = considered = 0
    for p, t in zip(pred, truth):
        if t is None:
            continue
        considered += 1
        if p == t:
            matched += 1
    return matched / considered if considered else 0.0


def match_rates(pred, annotators):
    """Match-rate family against multiple ground-truth annotators.

    Piano fingering is not unique, so estimates are scored against every
    annotator (Nakamura, Saito & Yoshii 2020).  ``pred`` is the per-note predicted
    finger list; ``annotators`` is a list of ground-truth finger lists, each
    aligned index-for-index with ``pred`` (use ``None`` for a note an annotator did
    not label).  A ``None`` in ``pred`` counts as a miss in every rate (see
    :func:`_match_rate`).

    Returns:
      * ``M_gen`` -- general: mean match rate over annotators.
      * ``M_high`` -- highest: best single annotator.
      * ``M_soft`` -- soft: fraction of notes matching *any* annotator.
      * ``M_rec`` -- recombination: match against the recombined ground truth of
        Nakamura et al. (2020, Sec. 6.2 and Appendix A): the reference may switch
        from one annotator to another only at a note where both give the same
        finger, each switch costs as much as one mismatch (C_rec = 1), and
        switching where the fingers differ is not allowed (C'_rec = infinity).
        By construction ``M_high <= M_rec <= M_soft``.
    """
    if not annotators:
        return {"M_gen": 0.0, "M_high": 0.0, "M_soft": 0.0, "M_rec": 0.0}

    rates = [_match_rate(pred, t) for t in annotators]
    m_gen = sum(rates) / len(rates)
    m_high = max(rates)

    # Notes considered = those >=1 annotator labels; an unpredicted note is a miss.
    idxs = [i for i in range(len(pred))
            if any(t[i] is not None for t in annotators)]
    n = len(idxs)
    if n == 0:
        return {"M_gen": m_gen, "M_high": m_high, "M_soft": 0.0, "M_rec": 0.0}

    soft = sum(1 for i in idxs
               if any(pred[i] == t[i] for t in annotators if t[i] is not None))
    m_soft = soft / n

    # Recombination: DP over the considered notes; state = chosen annotator.
    # score = matches - switches = N - E_rec.  Staying on one annotator
    # reproduces M_high, so the optimum is >= M_high; switches are allowed only
    # where the two annotators agree on the finger, and cost one note each.
    K = len(annotators)
    prev = [0.0] * K            # best score ending on annotator k at note i-1
    for pos, i in enumerate(idxs):
        cur = [0.0] * K
        for k in range(K):
            t = annotators[k][i]
            gain = 1.0 if (t is not None and pred[i] == t) else 0.0
            if pos == 0:
                cur[k] = gain
                continue
            best = prev[k]                                   # stay on k
            if t is not None:
                for j in range(K):
                    if j != k and annotators[j][i] == t:     # switch j -> k here
                        best = max(best, prev[j] - 1.0)
            cur[k] = gain + best
        prev = cur
    m_rec = max(0.0, max(prev)) / n

    return {"M_gen": m_gen, "M_high": m_high, "M_soft": m_soft, "M_rec": m_rec}


def hand_accuracy(pred_hands, truth_hands):
    """Fraction of notes whose predicted hand matches the ground-truth hand.

    Validates the hand-assignment step independently of finger numbers (PIG's
    signed finger encodes the hand).  A note without a ground-truth hand is
    excluded; a note without a predicted hand counts as a miss, as in
    :func:`_match_rate`.
    """
    matched = considered = 0
    for p, t in zip(pred_hands, truth_hands):
        if t is None:
            continue
        considered += 1
        if p == t:
            matched += 1
    return matched / considered if considered else 0.0


def hand_accuracy_any(pred_hands, truth_hand_lists):
    """Fraction of notes whose predicted hand matches the hand of *any* annotator.

    The hand counterpart of ``M_soft``: where annotators disagree on the hand,
    either choice counts.  ``truth_hand_lists[i]`` holds the hands the annotators
    gave note ``i`` (``None`` for an annotator without that note).  A note no
    annotator labels is excluded; a note without a predicted hand is a miss.
    """
    matched = considered = 0
    for p, hands in zip(pred_hands, truth_hand_lists):
        labelled = [h for h in hands if h is not None]
        if not labelled:
            continue
        considered += 1
        if p in labelled:
            matched += 1
    return matched / considered if considered else 0.0


# --------------------------------------------------------------------------- #
# 4. Paired comparison of two runs
# --------------------------------------------------------------------------- #

def bootstrap_mean_ci(values, level=0.95, n_resamples=10000, seed=0):
    """Percentile bootstrap confidence interval for the mean of ``values``.

    Resamples ``values`` with replacement and takes the central ``level`` share of
    the resampled means (Efron & Tibshirani, *An Introduction to the Bootstrap*,
    1993, ch. 13).  For a paired comparison ``values`` are the per-piece
    differences, so the piece is the sampling unit.  Seeded, so the interval is the
    same on every run.  Returns ``(low, high)``.
    """
    import random
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(n_resamples))
    alpha = 1.0 - level
    low = means[int(alpha / 2 * n_resamples)]
    high = means[int((1 - alpha / 2) * n_resamples) - 1]
    return (low, high)


def holm(pvalues):
    """Holm-adjusted p-values, returned in the order given.

    Holm, *A Simple Sequentially Rejective Multiple Test Procedure*, Scand. J.
    Statist. 6 (1979): sort the m p-values ascending, multiply the k-th smallest
    (k = 0, 1, ...) by m - k, keep the sequence non-decreasing and cap it at 1.
    Rejecting where the adjusted value is below alpha keeps the chance of any false
    rejection in the family at most alpha.
    """
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for k, i in enumerate(order):
        running = max(running, min(1.0, (m - k) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def wilcoxon_signed_rank(a, b):
    """Two-sided Wilcoxon signed-rank test for paired samples ``a`` and ``b``.

    Zero differences are dropped (Wilcoxon's original treatment), tied absolute
    differences share their average rank, and the p-value comes from the normal
    approximation with the tie correction -- adequate for the 150 PIG pieces (it
    is the usual large-sample form; scipy is not a dependency of this project).
    Returns ``{"n", "W", "z", "p"}`` with ``W`` the sum of positive ranks of
    ``b - a``.
    """
    import math
    d = [y - x for x, y in zip(a, b) if y != x]
    n = len(d)
    if n == 0:
        return {"n": 0, "W": 0.0, "z": 0.0, "p": 1.0}
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    ties = 0.0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    mean = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - ties / 48.0
    z = (w_plus - mean) / math.sqrt(var) if var > 0 else 0.0
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return {"n": n, "W": w_plus, "z": z, "p": p}
