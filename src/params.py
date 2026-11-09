"""Model parameters that no source fixes, in one place, with their search space.

Every number the method needs either comes from a source -- the movement tables
of Hart, Bosch & Tsai (2000), the span limits of Parncutt et al. (1997), the
window and importance weights of Nakamura & Yoshii (2018), the 30 ms chord
tolerance of Nakamura, Saito & Yoshii (2020), the MIDI default tempo -- or was
chosen by this project.  The ones chosen here that change the fingering or the
hand split live in this module: the hand-picked values the project started from,
the grid each one is searched on, and the stage of ``otimizar.py`` that fits it:

  * stage ``cost``      -- the weights of the ergonomic cost, fitted with the
    annotators' own hands (assigner ``oracle``), so that they favour no hand
    assigner, maximising the mean M_gen over the training pieces;
  * stage ``stability`` -- each assigner's boundary-stability weight,
    maximising the mean S_gen (hand and finger must both agree), one assigner
    at a time; with ``joint-full`` also the chord-span threshold and weight
    (below).

A fitted value replaces the starting one only when the gain is shown on the
training pieces: the paired 95% bootstrap interval of the per-piece difference
must lie above zero (``otimizar.py``).  A weight the data cannot tell apart from
its starting value keeps the starting value.

Both stages see only PIG pieces 031-150.  Pieces 001-030, the test set of
Nakamura, Saito & Yoshii (2020), are never used to fit anything
(:data:`src.pig_loader.TEST_PIECES`).

Terms removed because the fit showed them to do nothing or to do harm (PIG
031-150, 2026-11-08): the crossing penalty inside a chord, which never applies
because every chord fingering is generated from the thumb side, so none is
crossed (:func:`src.costs.chord_complexity` now rejects a crossed one); the
constant base of the stretch cost, which the fit set to 0 and which 0 and 3 did
not distinguish, so a stretch costs only its weight per semitone; and the
``split`` proxy's penalty for splitting a chord one hand could take, which the
fit set to 0 with a large gain in S_gen.

The chord-span threshold and weight never change a fingering: the term depends
only on the chord's pitches, the same for every fingering of it.  They act only
on how the joint assigners divide the notes and on the difficulty measure, so
the ``cost`` stage cannot fit them and they are not in :data:`COST_PARAMS`.
They are fitted with ``joint-full``, the method itself, in its stability stage;
``joint-local`` is fitted after it and uses the same values, so the cost model
stays one for every assigner.  (Switching the term off lowered the S_gen of
``joint-full`` by about half a point on the training pieces, so it is kept.)

Chosen numbers that are *not* here, and why they are not fitted: the beam (32)
and boundary window (6) of ``joint-full`` only trade time for exactness, so a
fit would always push them to the largest value tried (their cost is measured
instead, ``evaluate.py beamgap``); the reducer's tempo floor and step and its
iteration cap, and the engraver's quantisation, have no reference in PIG to fit
against; 100 (``costs.MAX_MOVE_COST_HARD``) and 1000 (the proxy's infeasibility
penalty) stand for "impossible" and only need to dominate every real cost.

The difficulty ceiling is not fitted either, but it is measured on the cost
model: the 90th percentile of the per-onset difficulty on the same training
pieces (``sheet_reducer``), with ``joint-local``.  It is stored next to the
values it was measured with, and ``otimizar.py`` re-measures it at the end of
every run, after the weights it depends on have been fitted.

The values in force are the fitted ones in ``parametros.json`` at the repository
root when that file exists, else the hand-picked ones; :func:`use` switches.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTIMIZED_FILE = os.path.join(ROOT, "parametros.json")

# The values the project used before any fitting.
HAND_PICKED = {
    # ergonomic cost (src.costs)
    "chord_span_threshold": 7.0,   # total chord span (semitones) above which ...
    "chord_span_weight": 2.0,      # ... each extra semitone costs this much
    "stretch_weight": 3.0,         # a pair past its comfortable span, per semitone past it
    "release": 10.0,               # letting a held note go before its written end
    "untabulated_offset": 2.0,     # a move the tables do not cover costs span + offset
    "unison": 1.0,                 # a repeated note (span 0, not tabulated)
    "comfort_1_5": 12.0,           # comfortable span of the 1-5 pair; absolute = +2
    # hand assigners (src.assigners)
    "smooth_split": 0.6,           # boundary stability, per semitone moved ...
    "smooth_local": 0.6,           # ... one weight per assigner
    "smooth_full": 0.6,
}
# (D_L, D_R, D_B) measured with HAND_PICKED on this code, as ``otimizar.py``
# measures it.  (The 44/57/89 of earlier drafts belong to the model before the
# left-hand chord order was fixed in the joint assigners and before the three
# terms above were removed.)
HAND_PICKED_CEILING = (51.0, 36.0, 78.0)

# Grid each parameter is searched on (the hand-picked value is always included).
# The grid of each parameter.  A grid starts at 0 (the term switched off) or at
# the smallest sensible value, and must reach past the best value: ``otimizar.py``
# warns when the best value is the largest one tried.  Two upper limits are set
# by the model rather than by taste: ``release`` stays below 100, the cost of an
# impossible stretch, so a held note beyond the absolute span is still released;
# ``comfort_1_5`` stops at 13, the comfortable 1-5 span of Parncutt et al. (1997)
# (MaxComf; with the +2 the absolute span is then their MaxPrac of 15), so the
# warning does not apply to it (``CAPPED``).
_SMOOTH = [0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0]
GRID = {
    "chord_span_threshold": [5, 6, 7, 8, 9, 10, 12],
    "chord_span_weight": [0, 0.5, 1, 2, 3, 4, 6],
    "stretch_weight": [0.5, 1, 2, 3, 4, 6],
    "release": [2, 4, 6, 8, 10, 12, 15, 20, 30, 40, 50, 60, 80],
    "untabulated_offset": [0, 1, 2, 3, 4, 6, 8],
    "unison": [0, 1, 2, 3],
    "comfort_1_5": [10, 11, 12, 13],
    "smooth_split": _SMOOTH,
    "smooth_local": _SMOOTH,
    "smooth_full": _SMOOTH,
}

CAPPED = {"comfort_1_5"}   # the largest grid value is a limit from the source

COST_PARAMS = ["stretch_weight", "release", "untabulated_offset", "unison",
               "comfort_1_5"]
STABILITY_PARAMS = {"split": ["smooth_split"],
                    "joint-local": ["smooth_local"],
                    "joint-full": ["smooth_full", "chord_span_threshold",
                                   "chord_span_weight"]}
# joint-full before joint-local: joint-local uses the chord-span values it fits
STABILITY_ORDER = ["split", "joint-full", "joint-local"]

# The live values: read directly (``params.VALUES["release"]``) by hot code.
VALUES = dict(HAND_PICKED)
CEILING = list(HAND_PICKED_CEILING)
SOURCE = "hand-picked"


def get(name):
    return VALUES[name]


def current():
    """A copy of the values in force, with the ceiling and where they came from."""
    return {"values": dict(VALUES), "ceiling": list(CEILING), "source": SOURCE}


def set(ceiling=None, **values):
    """Change parameter values (and optionally the ceiling) in place.

    Unknown names are an error.  Anything that caches a cost is refreshed, so a
    change takes effect on the next call.
    """
    unknown = [k for k in values if k not in VALUES]
    if unknown:
        raise KeyError(f"unknown parameter(s) {unknown}; known: {sorted(VALUES)}")
    changed = any(VALUES[k] != float(v) for k, v in values.items())
    for k, v in values.items():
        VALUES[k] = float(v)
    if ceiling is not None:
        CEILING[:] = [float(c) for c in ceiling]
    if changed:
        _refresh()


def _refresh():
    # late imports: these modules read this one, not the other way round
    from src import costs
    costs.set_span_limits(costs.current_span_limits())
    from src.assigners import joint_full
    joint_full._chord_cost.cache_clear()


def load(path):
    """Use the values stored in ``path`` (a file written by :func:`save`)."""
    global SOURCE
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    set(ceiling=data.get("ceiling"), **{k: v for k, v in data["values"].items()
                                        if k in VALUES})
    SOURCE = os.path.relpath(path, ROOT)


def use(spec):
    """``"hand-picked"``, ``"optimized"`` (``parametros.json``) or a file path."""
    global SOURCE
    if spec in (None, "", "optimized"):
        if os.path.exists(OPTIMIZED_FILE):
            load(OPTIMIZED_FILE)
            return
        spec = "hand-picked"
    if spec == "hand-picked":
        set(ceiling=HAND_PICKED_CEILING, **HAND_PICKED)
        SOURCE = "hand-picked"
        return
    load(spec)


def save(path, values, ceiling, meta):
    data = {"values": {k: values[k] for k in HAND_PICKED},
            "ceiling": [round(c, 6) for c in ceiling],
            "meta": meta}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def ceiling():
    return tuple(CEILING)


# Values in force at import: the fitted ones when they exist.  Done without
# _refresh() (nothing is cached yet); costs applies the 1-5 limits on import.
if os.path.exists(OPTIMIZED_FILE):
    with open(OPTIMIZED_FILE, encoding="utf-8") as _fh:
        _data = json.load(_fh)
    VALUES.update({k: float(v) for k, v in _data["values"].items() if k in VALUES})
    if _data.get("ceiling"):
        CEILING[:] = [float(c) for c in _data["ceiling"]]
    SOURCE = "parametros.json"
