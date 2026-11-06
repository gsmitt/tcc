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

  * Difficulty is the ergonomic cost per second of :mod:`src.difficulty`
    (the analogue of the paper's ``D(t) = -ln P / Δt``), so it depends on the
    tempo the score is played at -- which is what makes the third operation
    below possible.
  * Musical importance follows eq. (13):
    ``h(m) = I(melodic) + I(bass) + a·Mult(m)`` -- melodic/bass notes (here the
    per-onset skyline/bassline) are protected and never edited, the rest are
    ranked by ``h`` so the least important note is removed first (the
    deterministic analogue of the largest deletion probability ``β_NP`` in
    eq. (12)).
  * Edits are note deletion, ±12 octave shift and -- added here, see below --
    global tempo reduction, applied in an iterative loop that re-measures
    difficulty after each batch until every onset satisfies the target triplet
    ``D_L < D̃_L ∧ D_R < D̃_R ∧ D_B < D̃_B`` (eq. (14)), or no edit is left to make
    (the minimal melody+bass score can stay over target, paper §IV.B).

Tempo reduction as a third edit operation
-----------------------------------------
Difficulty is a cost *per second* (:mod:`src.difficulty`), so playing slower
lowers it.  That makes a global tempo factor a genuine reduction operation
alongside the paper's two, and an extremely common one among performers: Allingham
& Wöllner, "Slow practice and tempo management strategies in instrumental music
learning", Psychology of Music 50(6) (2022), report 96.5% of 256 instrumentalists
using slow practice.

Three constraints shape how it is applied here.

1. **Global, never local.**  One factor for the whole piece.  Slowing only the
   hard passage would distort the piece's rhythmic structure, which is a larger
   infidelity than the difficulty it buys back.

2. **With a floor** (``tempo_floor``).  The measure is linear in tempo, so
   unchecked it would call 20 BPM trivial; the motor literature says otherwise.
   Allingham & Wöllner, "Putting practice under the microscope: The perceived uses
   and limitations of slow instrumental music practice", Psychology of Music 51(3)
   (2023), §Discussion, report that slow movement can be *harder* to control than
   fast (Van Der Wel et al., 2009) and that motor-system organisation changes with
   execution speed (Dahl et al., 2011; Goebl & Palmer, 2008; Winold et al., 1994)
   -- one respondent notes slow practice "frequently changes the technique".  The
   floor is therefore a model requirement, not editorial caution: outside a band
   around the intended tempo the difficulty/tempo relation stops holding, so the
   model must not be asked to extrapolate there.  The default admits **half the
   score's tempo** (``tempo_floor=0.5``), the conventional "half tempo" of
   practice; no source gives a numeric bound, so this is a declared choice and the
   single number to revisit if the band is ever measured.

3. **Not a free win.**  Respondents in the same study report the intended tempo as
   essential to a piece's character.  Slowing down preserves every note but loses
   that; deleting a note preserves the tempo but loses material.  The two
   operations spend *different* kinds of fidelity and there is no obvious exchange
   rate between them, so the loop does not trade them off by a common score.

**Choice criterion.**  Each iteration picks one operation.  Tempo reduction fires
only when suppression has nothing left to offer: an over-target onset whose whole
window holds only protected (melodic/bass) notes, so the target could not be
reached there without editing material the reducer is defined never to edit.
Further deletion *elsewhere* cannot fix such an onset, so at that point the real
choice is slowing down or leaving the onset over target.  Because the factor is
global, the step also relieves every other violated onset, which is where the
preserved notes come from -- the point of the operation is to spend character to
keep material that deletion would otherwise have taken.

*Alternative considered:* fire the tempo step only once deletion has stalled
everywhere (the loop's old give-up condition).  Rejected because by then the
deletions are already made: the score would be both thinned and slowed, and the
factor would buy only target satisfaction on the protected-note remainder, not
preserved material.  The criterion above is deliberately the earlier trigger.  An
infinite difficulty does *not* trigger it: that is a chord the solver cannot
finger at all, a playability failure no tempo fixes.

Reduction runs on the combined condensed score and returns layers in the same
dict format as :mod:`src.midi_reader`, so the downstream pipeline is unchanged.
Note identity across edits is keyed by ``(layer_idx, pitch)`` (pitches are unique
within a layer after :func:`condense`).
"""

from dataclasses import dataclass, field

from .assigners import get_assigner, split_layers_by_hand
from .solvers import get_solver
from .difficulty import DEFAULT_DELTA_T, note_difficulties, window_whole_notes

MIN_MIDI, MAX_MIDI = 21, 108     # piano range, for octave-shift clamping

# Tempo-reduction bounds, as fractions of the score's own tempo (see the
# module docstring): the floor admitted, and the decrement per loop iteration.
DEFAULT_TEMPO_FLOOR = 0.5        # half tempo: this project's choice. Allingham &
                                 # Wöllner (2023) motivate *having* a floor (slow
                                 # playing changes technique); the value is ours.
DEFAULT_TEMPO_STEP = 0.1         # 10% of the nominal tempo per step

# Default difficulty ceiling (D̃_L, D̃_R, D̃_B), in ergonomic cost per second.
#
# CALIBRATION.  The ceiling is the 90th percentile of the per-onset difficulty of
# each hand and of both together, pooled over the 120 PIG pieces outside the
# 30-piece test set of Nakamura, Saito & Yoshii (2020) (pieces 031-150), measured
# from the notes alone -- no annotated fingering is used -- with the
# ``joint-local`` assigner the reduction loop uses, Δt = 1 s, and PIG's
# performance times read as whole notes of one second (bpm = 240):
#
#       p50   p75   p85   p90   p95   p99
#   D_L  8.0  21.0  34.0  44.0  61.2 136.0
#   D_R 10.0  28.0  44.0  57.0  82.0 143.0
#   D_B 23.0  52.0  73.0  89.0 123.0 209.0
#
# It leaves nine onsets in ten of those pieces alone and edits the hardest tenth;
# the asymmetry between the hands comes from the data, not from a choice.  The
# reduction results are reported on the 30 test pieces as well, which the
# ceiling never saw.  Re-measure this block whenever the cost model, the window
# or the time convention changes (``difficulty_profile``): the numbers do not
# transfer across any of the three.
DEFAULT_TARGET = (44.0, 57.0, 89.0)


@dataclass
class ReduceResult:
    layers: list
    deleted: list = field(default_factory=list)   # [(layer_idx, pitch), ...]
    shifted: list = field(default_factory=list)    # [(layer_idx, old, new), ...]
    additional_note_rate: float = 0.0              # eq. (22)
    target: tuple = (0.0, 0.0, 0.0)                # the (D̃_L, D̃_R, D̃_B) actually used
    tempo_factor: float = 1.0                      # global tempo applied, as a fraction of the score's
    bpm: float = 0.0                               # the score's own tempo the factor is relative to

    @property
    def reduced_bpm(self):
        """The tempo the reduced score is to be played at (``bpm * factor``)."""
        return self.bpm * self.tempo_factor


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


def _measure(layers, delta_t, assigner, bpm):
    """Run the normal pipeline once to score the current score.

    Returns ``(labels, difficulties, lh, rh, lh_layers, rh_layers)`` where
    ``labels`` maps ``(layer_idx, note_idx) -> "L"|"R"`` and ``difficulties`` is
    the per-onset ``(D_L, D_R, D_B)`` list aligned with ``layers``.

    ``bpm`` is the tempo to measure at -- for the reduction loop, the score's
    tempo already multiplied by the current tempo factor -- and ``delta_t`` the
    difficulty window in seconds.  Only the difficulty read-out depends on either:
    the assignment and the fingering are tempo-free.
    """
    labels = get_assigner(assigner)(layers).assign()
    lh_layers, rh_layers = split_layers_by_hand(layers, labels)
    Solver = get_solver("viterbi")
    lh = Solver(lh_layers, hand="L").solve()
    rh = Solver(rh_layers, hand="R").solve()
    diffs = note_difficulties(layers, lh_layers, lh.path, rh_layers, rh.path,
                              bpm=bpm, delta_t=delta_t)

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


def _percentile(values, p):
    """The ``p``-th percentile (linear interpolation) of the finite ``values``.

    Infinite difficulties (an onset the solver could not finger, i.e. exactly the
    spots reduction must fix) are dropped: they exceed any finite target anyway,
    so the baseline scale is taken from the playable material.
    """
    vals = sorted(v for v in values if v != float("inf"))
    if not vals:
        return float("inf")
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def difficulty_profile(layers, *, bpm, delta_t=DEFAULT_DELTA_T, assigner="joint-local",
                       percentiles=(50, 90, 100)):
    """Per-onset difficulty distribution of a score, per hand and combined.

    Measures the (condensed) score once and reports, for ``D_L``/``D_R``/``D_B``,
    the ``min`` and the requested ``percentiles`` of the per-onset difficulty,
    plus ``n_inf`` (onsets the solver could not finger at all).

    The difficulty is an ergonomic cost **per second** (:mod:`src.costs` over the
    :mod:`src.difficulty` window), so the scale is piece-independent only *at a
    given tempo*: the same passage scores twice as high played twice as fast.  Use
    this to choose and justify an absolute :func:`reduce_score` ``target`` -- pick a
    ceiling once, globally, and read it back here against several pieces to anchor
    what it means (e.g. roughly which D_B counts as easy vs advanced) -- and record
    the ``bpm`` and ``delta_t`` the ceiling was read at, since a ceiling chosen on
    one scale is meaningless on another.
    """
    layers, _multiplicity = condense(layers)
    _labels, diffs, *_ = _measure(layers, delta_t, assigner, bpm)
    out = {}
    for name, idx in (("D_L", 0), ("D_R", 1), ("D_B", 2)):
        vals = [d[idx] for d in diffs]
        finite = [v for v in vals if v != float("inf")]
        stats = {"min": min(finite) if finite else float("inf")}
        for p in percentiles:
            stats[f"p{int(p)}"] = _percentile(vals, p)
        stats["n_inf"] = sum(1 for v in vals if v == float("inf"))
        out[name] = stats
    return out


def reduce_score(layers, target=DEFAULT_TARGET, *, bpm, a=0.01,
                 delta_t=DEFAULT_DELTA_T, max_iter=50, allow_octave_shift=True,
                 allow_tempo_reduction=True, tempo_floor=DEFAULT_TEMPO_FLOOR,
                 tempo_step=DEFAULT_TEMPO_STEP, assigner="joint-local"):
    """Iteratively reduce ``layers`` to the difficulty ``target`` triplet.

    ``target`` is an **absolute** ceiling ``(D̃_L, D̃_R, D̃_B)`` in this project's
    ergonomic cost per second (:mod:`src.costs` over the :mod:`src.difficulty`
    window; NOT the papers' -ln P units).  Those units are fixed across pieces --
    the same physical hand effort over the same span of seconds yields the same
    difficulty -- so a single global ``target`` transfers between pieces: a harder
    piece is reduced more, an easier one less (like arranging to a fixed grade).
    The raw numbers are not self-explanatory, so choose/justify them with
    :func:`difficulty_profile`, which reports a piece's difficulty distribution on
    the same scale, and note the ``delta_t`` they were read at.

    ``bpm`` is the score's own tempo (:class:`src.midi_reader.Tempo`), required
    because the difficulty is a time rate: the same notes at a different tempo are
    a different reduction problem.  The reducer may lower the *effective* tempo as
    an edit, down to ``tempo_floor`` times ``bpm`` in ``tempo_step`` decrements
    (see the module docstring for the operation, its floor and the criterion that
    selects it); ``allow_tempo_reduction=False`` restores the paper's two
    operations, which is the comparison that isolates what the third one buys.

    ``assigner`` names the hand assigner used to re-measure difficulty each
    iteration (:func:`src.assigners.get_assigner`); it defaults to
    ``"joint-local"``, the cheapest assigner that scores a split by the real
    ergonomic cost.  ``"joint-full"`` (what the final output uses) is ~20x slower
    per call, and this loop runs the pipeline up to ``max_iter`` times, so the
    ceiling is enforced on a close approximation of the final effort (on
    ``data/mond_1.mid`` the two assigners agree on ~92% of notes).
    Returns a :class:`ReduceResult`, whose ``tempo_factor`` reports the applied
    tempo alongside the deleted and shifted notes.
    """
    if not 0.0 < tempo_floor <= 1.0:
        raise ValueError(f"tempo_floor must be in (0, 1], got {tempo_floor!r}: it "
                         f"is a fraction of the score's own tempo, and the model "
                         f"is not declared valid below it (module docstring)")
    if not 0.0 < tempo_step <= 1.0:
        raise ValueError(f"tempo_step must be in (0, 1], got {tempo_step!r}")

    layers, multiplicity = condense(layers)
    deleted, shifted = [], []
    tempo_factor = 1.0

    for _ in range(max_iter):
        melody, bass = _skyline_bassline(layers)
        labels, diffs, *_ = _measure(layers, delta_t, assigner,
                                     bpm * tempo_factor)

        violated = [i for i, d in enumerate(diffs) if _overage(d, target) > 0]
        if not violated:
            break
        violated.sort(key=lambda i: _overage(diffs[i], target), reverse=True)

        # The window the edits are drawn from is the window the difficulty was
        # measured over, so it follows the effective tempo too.
        half = window_whole_notes(delta_t, bpm * tempo_factor) / 2.0
        edits = {}        # (layer_idx, pitch) -> "del" | ("shift", new_pitch)
        deadlocked = False
        for i in violated:
            t = layers[i]["time"]
            hand = _choose_hand(diffs[i], target)

            # candidate notes: same hand, inside the window, not protected,
            # not already edited this round
            cands = []
            editable = False   # any unprotected note at all, claimed or not
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
                    editable = True
                    if (j, p) in edits:
                        continue
                    cands.append((j, p, hand_pitches, median))

            if not cands:
                # Suppression is out of material here only if the window holds
                # nothing but protected notes: fixing this onset would then mean
                # editing melody/bass, and no deletion elsewhere can help it.
                # That is the tempo operation's trigger -- unless the difficulty
                # is infinite, which is an unfingerable chord rather than a
                # density the tempo could thin out.  If the window's editable
                # notes were merely claimed by another onset this round, those
                # edits already work on this window: re-measure, don't slow down.
                if not editable and _tempo_would_help(diffs[i]):
                    deadlocked = True
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

        # One operation per iteration: slow down *instead of* editing notes, so
        # the lower tempo gets a chance to spare the deletions the other violated
        # onsets would otherwise have cost (module docstring, "Choice criterion").
        if (deadlocked and allow_tempo_reduction
                and tempo_factor > tempo_floor + 1e-9):
            # round: keeps the reported factor a clean fraction of the
            # score's tempo instead of a float-accumulation artefact.
            tempo_factor = max(tempo_floor, round(tempo_factor - tempo_step, 6))
            continue

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
                        additional_note_rate=aadd, target=target,
                        tempo_factor=tempo_factor, bpm=bpm)


def _tempo_would_help(diff):
    """Is this onset's difficulty a *density* the tempo can thin out?

    True when both hands' difficulties are finite.  An infinite ``D_L``/``D_R``
    comes from a Viterbi failure (a chord needing more free fingers than the hand
    has, see :func:`_measure`): no tempo makes it playable, so it must not drive
    the tempo down.
    """
    return all(d != float("inf") for d in diff)


def _plan_edit(layers, li, pitch, hand_pitches, median, allow_octave_shift, edits):
    """Prefer a fidelity-preserving octave fold; otherwise delete (eq. (10)).

    The folded note must stay strictly between the onset's lowest and highest
    notes, the bass and the melody the reducer protects.  Without that, folding
    toward the median of a two-note hand (an inner note and the melody, whose
    median *is* the melody) sent the inner note an octave up, above the melody, in
    almost every fold: the melody was never edited but stopped being the top
    voice.
    """
    if allow_octave_shift and len(hand_pitches) > 1:
        new_pitch = pitch + 12 if pitch < median else pitch - 12
        layer_pitches = {p for p, _e in layers[li]["notes"]}
        pending = {np for e in edits.values()
                   if isinstance(e, tuple) for np in (e[1],)}
        folds_inward = abs(new_pitch - median) < abs(pitch - median)
        inside = min(layer_pitches) < new_pitch < max(layer_pitches)
        if (MIN_MIDI <= new_pitch <= MAX_MIDI and folds_inward and inside
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
