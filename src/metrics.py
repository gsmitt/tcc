"""Evaluation metrics for the fingering pipeline.

This module does not introduce any new model: it aggregates quantities the
pipeline already produces (:mod:`src.costs`, :mod:`src.difficulty`,
:mod:`src.sheet_reducer`, the solver ``SolverResult``) into the numbers the
thesis reports.  Four families:

1. **Fingering difficulty / playability** (intrinsic, no ground truth) --
   :func:`difficulty_stats`, :func:`solver_stats`.  The ergonomic cost density of
   :mod:`src.difficulty`, read out as a distribution instead of an optimisation
   target.

2. **Reduction fidelity & efficacy** -- :func:`reduction_fidelity`,
   :func:`target_satisfaction`.  Fidelity is note-preservation + edit-severity,
   weighted by the musical-importance term ``h(m)`` of the reducer
   (Nakamura & Yoshii, *Statistical Piano Reduction Controlling Performance
   Difficulty*, APSIPA Trans. 7 (2018), eq. (13), (22)).

3. **Fingering accuracy vs. ground truth** -- :func:`match_rates`,
   :func:`hand_accuracy`.  The match-rate family of
   Nakamura, Saito & Yoshii, *Statistical Learning and Estimation of Piano
   Fingering*, Information Sciences 517 (2020): general / highest / soft /
   recombination match rate against multiple annotators.

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
    }


def target_satisfaction(diffs, target):
    """Fraction of onsets whose difficulty is within the reduction budget.

    An onset satisfies the budget when ``D_L < D̃_L ∧ D_R < D̃_R ∧ D_B < D̃_B``
    (Nakamura & Yoshii eq. (14)).  ``diffs`` is a per-onset ``(D_L, D_R, D_B)``
    list, ``target`` the ``(D̃_L, D̃_R, D̃_B)`` ceiling.  Reports the satisfaction
    rate and ``n_violations``; the efficacy side of the fidelity/difficulty
    trade-off (pair it with :func:`reduction_fidelity`).
    """
    tl, tr, tb = target
    if not diffs:
        return {"satisfaction_rate": 1.0, "n_violations": 0, "n_onsets": 0}
    violations = sum(1 for dl, dr, db in diffs
                     if not (dl < tl and dr < tr and db < tb))
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
    """Fraction of notes where ``pred[i] == truth[i]``, over notes both label.

    ``None`` on either side (unpredicted note, or unlabelled by this annotator)
    excludes the note from the denominator.
    """
    matched = considered = 0
    for p, t in zip(pred, truth):
        if p is None or t is None:
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
    not label).

    Returns:
      * ``M_gen`` -- general: mean match rate over annotators.
      * ``M_high`` -- highest: best single annotator.
      * ``M_soft`` -- soft: fraction of notes matching *any* annotator.
      * ``M_rec`` -- recombination: match against the best per-note recombination
        of annotators, charging one note of penalty per annotator switch (a
        concrete, reproducible reading of Nakamura's recombined ground truth).
        By construction ``M_high <= M_rec <= M_soft``.
    """
    if not annotators:
        return {"M_gen": 0.0, "M_high": 0.0, "M_soft": 0.0, "M_rec": 0.0}

    rates = [_match_rate(pred, t) for t in annotators]
    m_gen = sum(rates) / len(rates)
    m_high = max(rates)

    # Notes considered = those the estimate labels and >=1 annotator labels.
    idxs = [i for i, p in enumerate(pred)
            if p is not None and any(t[i] is not None for t in annotators)]
    n = len(idxs)
    if n == 0:
        return {"M_gen": m_gen, "M_high": m_high, "M_soft": 0.0, "M_rec": 0.0}

    soft = sum(1 for i in idxs
               if any(pred[i] == t[i] for t in annotators if t[i] is not None))
    m_soft = soft / n

    # Recombination: DP over the considered notes; state = chosen annotator.
    # score = matches - (switches).  Staying on one annotator reproduces M_high,
    # so the optimum is >= M_high; the per-switch charge keeps it <= M_soft.
    K = len(annotators)
    prev = [0.0] * K            # best score ending on annotator k at note i-1
    for pos, i in enumerate(idxs):
        cur = [0.0] * K
        best_prev = max(prev)
        for k in range(K):
            t = annotators[k][i]
            gain = 1.0 if (t is not None and pred[i] == t) else 0.0
            if pos == 0:
                cur[k] = gain
            else:
                stay = prev[k]
                switch = best_prev - 1.0     # one-note penalty to change annotator
                cur[k] = gain + max(stay, switch)
        prev = cur
    m_rec = max(0.0, max(prev)) / n

    return {"M_gen": m_gen, "M_high": m_high, "M_soft": m_soft, "M_rec": m_rec}


def hand_accuracy(pred_hands, truth_hands):
    """Fraction of notes whose predicted hand matches the ground-truth hand.

    Validates the hand-assignment step independently of finger numbers (PIG's
    signed finger encodes the hand).  ``None`` on either side excludes the note.
    """
    matched = considered = 0
    for p, t in zip(pred_hands, truth_hands):
        if p is None or t is None:
            continue
        considered += 1
        if p == t:
            matched += 1
    return matched / considered if considered else 0.0
