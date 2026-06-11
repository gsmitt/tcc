"""Sheet reduction: thin a dense piano score to a target difficulty.

Deterministic, cost-based adaptation of the merged-output-HMM piano reduction of

    Nakamura & Sagayama, "Automatic Piano Reduction from Ensemble Scores Based
    on Merged-Output Hidden Markov Model", ICMC 2015;
    Nakamura & Yoshii, "Statistical Piano Reduction Controlling Performance
    Difficulty", APSIPA Trans. Signal & Information Processing 7 (2018).

Those papers maximise P(R|E) -- a piano-score model times an edit model -- under
constraints on a probabilistic difficulty measure, with two edit operations:
note deletion and octave pitch shift (paper §III.A, eq. (10)-(13)), solved by an
iterative Viterbi optimiser (paper §III.B.2). We keep the *structure* of that
method but, consistent with the rest of this project (see
:mod:`src.hand_assigner`), replace the probabilistic machinery with the
ergonomic cost in :mod:`src.costs`:

  * Difficulty is the ergonomic cost density of :mod:`src.difficulty`
    (the analogue of the paper's ``D(t) = -ln P / Δt``).
  * Musical importance follows eq. (13):
    ``h(m) = I(melodic) + I(bass) + a·Mult(m)`` -- melodic/bass notes (here the
    per-onset skyline/bassline) are protected and never edited, the rest are
    ranked by ``h`` so the least important note is removed first (the
    deterministic analogue of the largest deletion probability ``β_NP`` in
    eq. (12)).
  * Edits are note deletion and ±12 octave shift, applied in an iterative loop
    that re-measures difficulty after each batch until every onset satisfies the
    target triplet ``D_L < D̃_L ∧ D_R < D̃_R ∧ D_B < D̃_B`` (eq. (14)), or a note
    budget is exhausted (the minimal melody+bass score can stay over target,
    paper §IV.B).

Reduction runs on the combined condensed score and returns layers in the same
dict format as :mod:`src.midi_reader`, so the downstream pipeline is unchanged.
Note identity across edits is keyed by ``(layer_idx, pitch)`` (pitches are unique
within a layer after :func:`condense`).
"""

from dataclasses import dataclass, field

from .voice_separator import separate_voices
from .hand_assigner import assign_voices_to_hands, split_layers_by_hand
from .solvers import get_solver
from .difficulty import note_difficulties

MIN_MIDI, MAX_MIDI = 21, 108     # piano range, for octave-shift clamping


@dataclass
class ReduceResult:
    layers: list
    deleted: list = field(default_factory=list)   # [(layer_idx, pitch), ...]
    shifted: list = field(default_factory=list)    # [(layer_idx, old, new), ...]
    additional_note_rate: float = 0.0              # eq. (22)


def condense(layers):
    """Remove duplicate same-pitch notes within each onset (paper §III).

    Returns ``(condensed_layers, multiplicity)`` where ``multiplicity`` maps
    ``(layer_idx, pitch) -> Mult(m)``, the number of removed duplicates (used by
    the importance term, eq. (13)). The surviving note keeps the latest release.
    """
    out = []
    multiplicity = {}
    for layer in layers:
        latest = {}                       # pitch -> end (latest release kept)
        counts = {}                       # pitch -> duplicates removed
        for pitch, end in layer["notes"]:
            if pitch in latest:
                counts[pitch] = counts.get(pitch, 0) + 1
                if end > latest[pitch]:
                    latest[pitch] = end
            else:
                latest[pitch] = end
        notes = [(p, latest[p]) for p in sorted(latest)]
        li = len(out)
        for p in latest:
            multiplicity[(li, p)] = counts.get(p, 0)
        out.append({"time": layer["time"], "notes": notes})
    return out, multiplicity


def _skyline_bassline(layers):
    """Per-onset top note (melody) and bottom note (bass): the protected set.

    Paper's per-bar highest/lowest heuristic (§IV.D), applied per onset for dense
    piano input. Returns ``(melody, bass)`` as sets of ``(layer_idx, pitch)``.
    """
    melody, bass = set(), set()
    for li, layer in enumerate(layers):
        pitches = [p for p, _e in layer["notes"]]
        if not pitches:
            continue
        melody.add((li, max(pitches)))
        bass.add((li, min(pitches)))
    return melody, bass


def _importance(li, pitch, melody, bass, multiplicity, a):
    """Musical importance ``h(m)`` of a note (eq. (13))."""
    h = a * multiplicity.get((li, pitch), 0)
    if (li, pitch) in melody:
        h += 1.0
    if (li, pitch) in bass:
        h += 1.0
    return h


def _measure(layers, delta_t):
    """Run the normal pipeline once to score the current score.

    Returns ``(labels, difficulties, lh, rh, lh_layers, rh_layers)`` where
    ``labels`` maps ``(layer_idx, note_idx) -> "L"|"R"`` and ``difficulties`` is
    the per-onset ``(D_L, D_R, D_B)`` list aligned with ``layers``.
    """
    voices = separate_voices(layers)
    labels = assign_voices_to_hands(voices)
    lh_layers, rh_layers = split_layers_by_hand(layers, labels)
    Solver = get_solver("viterbi")
    lh = Solver(lh_layers, hand="L").solve()
    rh = Solver(rh_layers, hand="R").solve()
    diffs = note_difficulties(layers, lh_layers, lh.path,
                              rh_layers, rh.path, delta_t)

    # A hand whose Viterbi search failed (a chord needs more than five free
    # fingers) yields an empty path and a spurious zero difficulty there; force
    # that onset over target so the loop edits it.
    for res, hand in ((lh, "L"), (rh, "R")):
        if res.cost == float("inf"):
            fi = res.extras.get("failed_at", 0)
            src = lh_layers if hand == "L" else rh_layers
            if fi < len(src):
                ftime = src[fi]["time"]
                for i, layer in enumerate(layers):
                    if layer["time"] == ftime:
                        dl, dr, _ = diffs[i]
                        if hand == "L":
                            dl = float("inf")
                        else:
                            dr = float("inf")
                        diffs[i] = (dl, dr, dl + dr)
    return labels, diffs, lh, rh, lh_layers, rh_layers


def _overage(diff, target):
    """Normalised amount by which an onset breaks the target triplet (eq. (14)).

    Positive means out of range; ``-inf``-ish (negative) means satisfied.
    """
    dl, dr, db = diff
    tl, tr, tb = target
    return max((dl - tl) / tl, (dr - tr) / tr, (db - tb) / tb)


def _choose_hand(diff, target):
    dl, dr, db = diff
    tl, tr, tb = target
    vl, vr = dl > tl, dr > tr
    if vl and not vr:
        return "L"
    if vr and not vl:
        return "R"
    return "L" if dl >= dr else "R"   # both, or only D_B: hit the heavier hand


def reduce_score(layers, target=(20.0, 20.0, 35.0), a=0.01, delta_t=1.0,
                 max_iter=50, allow_octave_shift=True):
    """Iteratively reduce ``layers`` to the difficulty ``target`` triplet.

    ``target`` is ``(D̃_L, D̃_R, D̃_B)`` in this project's ergonomic-cost-density
    units (NOT the papers' -ln P units), so values are calibrated empirically.
    Returns a :class:`ReduceResult`.
    """
    layers, multiplicity = condense(layers)
    deleted, shifted = [], []

    for _ in range(max_iter):
        melody, bass = _skyline_bassline(layers)
        labels, diffs, *_ = _measure(layers, delta_t)

        violated = [i for i, d in enumerate(diffs) if _overage(d, target) > 0]
        if not violated:
            break
        violated.sort(key=lambda i: _overage(diffs[i], target), reverse=True)

        half = delta_t / 2.0
        edits = {}        # (layer_idx, pitch) -> "del" | ("shift", new_pitch)
        for i in violated:
            t = layers[i]["time"]
            hand = _choose_hand(diffs[i], target)

            # candidate notes: same hand, inside the window, not protected,
            # not already edited this round
            cands = []
            for j, layer in enumerate(layers):
                if not (t - half <= layer["time"] <= t + half):
                    continue
                hand_pitches = [p for ni, (p, _e) in enumerate(layer["notes"])
                                if labels.get((j, ni)) == hand]
                if not hand_pitches:
                    continue
                median = sorted(hand_pitches)[len(hand_pitches) // 2]
                for ni, (p, _e) in enumerate(layer["notes"]):
                    if labels.get((j, ni)) != hand:
                        continue
                    if (j, p) in melody or (j, p) in bass:
                        continue
                    if (j, p) in edits:
                        continue
                    cands.append((j, p, hand_pitches, median))

            if not cands:
                continue
            # lowest importance first; tie-break: furthest from the hand cluster
            j, p, hand_pitches, median = min(
                cands,
                key=lambda c: (_importance(c[0], c[1], melody, bass, multiplicity, a),
                               -abs(c[1] - c[3])),
            )

            edit = _plan_edit(layers, j, p, hand_pitches, median,
                              allow_octave_shift, edits)
            edits[(j, p)] = edit

        if not edits:
            break       # only melody+bass remain in every violated window
        layers = _apply_edits(layers, edits, deleted, shifted)

    melody, bass = _skyline_bassline(layers)
    total = sum(len(l["notes"]) for l in layers)
    # Protected = distinct melodic/bass notes (a monophonic onset's single note
    # is both, so count it once via the union, else Aadd is meaningless).
    protected = len(melody | bass)
    aadd = (total - protected) / protected if protected else 0.0
    return ReduceResult(layers=layers, deleted=deleted, shifted=shifted,
                        additional_note_rate=aadd)


def _plan_edit(layers, li, pitch, hand_pitches, median, allow_octave_shift, edits):
    """Prefer a fidelity-preserving octave fold; otherwise delete (eq. (10))."""
    if allow_octave_shift and len(hand_pitches) > 1:
        new_pitch = pitch + 12 if pitch < median else pitch - 12
        layer_pitches = {p for p, _e in layers[li]["notes"]}
        pending = {np for e in edits.values()
                   if isinstance(e, tuple) for np in (e[1],)}
        folds_inward = abs(new_pitch - median) < abs(pitch - median)
        if (MIN_MIDI <= new_pitch <= MAX_MIDI and folds_inward
                and new_pitch not in layer_pitches and new_pitch not in pending):
            return ("shift", new_pitch)
    return "del"


def _apply_edits(layers, edits, deleted, shifted):
    """Rebuild layers applying the batch of edits, keyed by ``(layer_idx, pitch)``."""
    out = []
    for li, layer in enumerate(layers):
        notes = []
        for pitch, end in layer["notes"]:
            edit = edits.get((li, pitch))
            if edit is None:
                notes.append((pitch, end))
            elif edit == "del":
                deleted.append((li, pitch))
            else:                              # ("shift", new_pitch)
                new_pitch = edit[1]
                shifted.append((li, pitch, new_pitch))
                notes.append((new_pitch, end))
        notes.sort(key=lambda ne: ne[0])
        out.append({"time": layer["time"], "notes": notes})
    return out
