"""Render solver output to a PDF music sheet with fingering, via LilyPond.

Takes the per-hand solver results (the ``SolverResult.path`` produced by the
solvers in :mod:`src.solvers`) together with the per-hand layers, builds a
grand-staff LilyPond score with a fingering number on every note, and shells
out to the system ``lilypond`` to produce a PDF. No Python dependencies beyond
the standard library (the project stays ``mido``-only).

Faithful rhythm: real measures + time signature, triplets/tuplets, rests, and
ties across barlines. Durations come from the layers' note-value fractions
(quarter = 0.25), recovered exactly with ``Fraction(t).limit_denominator(960)``.

Known limitations (sufficient for the Moonlight excerpt this targets):
- One LilyPond voice per hand (chord-per-onset). True within-hand polyphony --
  a note held while another moves in the *same* hand at a later onset -- is
  approximated (clamped to the next onset), not split into \\voiceOne/\\voiceTwo.
  Future work could use the per-voice output of :mod:`src.voice_separator`.
- Tuplets are detected per beat with equal subdivisions (triplets, sextuplets,
  ...). Tuplets spanning multiple beats or nested/mixed tuplets are out of scope.
- Time signature defaults to 4/4 (parameter). Reading it from the MIDI meta is
  possible later.
"""

import os
import subprocess
from collections import OrderedDict
from fractions import Fraction
from math import gcd, lcm

# Snap tolerance: note ends within this of the next onset are treated as legato
# (no rest), absorbing the short note-offs typical of MIDI articulation.
SNAP = Fraction(1, 64)

_SHARP_NAMES = ["c", "cis", "d", "dis", "e", "f",
                "fis", "g", "gis", "a", "ais", "b"]
_FLAT_NAMES = ["c", "des", "d", "ees", "e", "f",
               "ges", "g", "aes", "a", "bes", "b"]


# --------------------------------------------------------------------------- #
# Pitch and duration conversion
# --------------------------------------------------------------------------- #
def _midi_to_lily(midi, accidental="sharp"):
    """MIDI note number -> absolute LilyPond pitch (60 -> c', 61 -> cis')."""
    names = _FLAT_NAMES if accidental == "flat" else _SHARP_NAMES
    name = names[midi % 12]
    n = midi // 12 - 4          # MIDI 60 -> c', 48 -> c, 72 -> c''
    if n > 0:
        name += "'" * n
    elif n < 0:
        name += "," * (-n)
    return name


def _decompose(d):
    """A dyadic duration (whole-note fraction) -> LilyPond duration tokens.

    Greedy largest dotted power-of-two value; several tokens mean a tied note
    (e.g. 5/16 -> ["4", "16"], 3/8 -> ["4."]).
    """
    out = []
    rem = d
    while rem > 0:
        best = None
        for k in range(0, 9):                       # whole .. 1/256
            base = Fraction(1, 2 ** k)
            for dots, mult in ((0, Fraction(1)), (1, Fraction(3, 2)),
                               (2, Fraction(7, 4))):
                val = base * mult
                if val <= rem and (best is None or val > best[0]):
                    best = (val, 2 ** k, dots)
        if best is None:
            break
        val, denom, dots = best
        out.append(str(denom) + "." * dots)
        rem -= val
    return out


def _is_tuplet(dur):
    """True if ``dur`` has a non-power-of-two denominator (a tuplet member)."""
    d = dur.denominator
    while d % 2 == 0:
        d //= 2
    return d > 1


def _frac_gcd(a, b):
    return Fraction(gcd(a.numerator, b.numerator),
                    lcm(a.denominator, b.denominator))


def _largest_pow2_le(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


# --------------------------------------------------------------------------- #
# Events -> token stream -> measures
# --------------------------------------------------------------------------- #
def _build_events(layers, path):
    """(layers, path) -> [(onset, end, [(midi, finger), ...]), ...].

    ``path[i]`` is index-aligned 1:1 with ``layers[i]`` (the solver appends one
    entry per layer), so fingers pair with notes by position.
    """
    events = []
    for i, layer in enumerate(layers):
        onset = Fraction(layer["time"]).limit_denominator(960)
        notes = layer["notes"]
        fingers = path[i][1] if i < len(path) and path[i][1] else ()
        ends = [end for (_m, end) in notes]
        end = Fraction(max(ends)).limit_denominator(960) if ends else onset
        nf = []
        for j, (midi, _e) in enumerate(notes):
            finger = fingers[j] if j < len(fingers) else None
            nf.append((midi, finger))
        events.append((onset, end, nf))
    events.sort(key=lambda e: e[0])
    return events


def _events_to_tokens(events):
    """Events -> contiguous (start, dur, content) tokens covering the timeline.

    ``content`` is a ``[(midi, finger), ...]`` list for a note/chord or ``None``
    for a rest. Note duration is the inter-onset interval (legato); a rest is
    inserted only when a note ends well before the next onset.
    """
    tokens = []
    cursor = Fraction(0)
    n = len(events)
    for idx in range(n):
        onset, end, notes = events[idx]
        if onset > cursor:                          # leading silence / gap
            tokens.append((cursor, onset - cursor, None))
            cursor = onset
        next_onset = events[idx + 1][0] if idx + 1 < n else end
        if next_onset - end > SNAP:                 # clear gap -> note + rest
            dur = end - onset
            if dur <= 0:
                dur = next_onset - onset
            tokens.append((onset, dur, notes))
            cursor = onset + dur
        else:                                       # legato -> fill to next
            dur = next_onset - onset
            tokens.append((onset, dur, notes))
            cursor = onset + dur
    return [t for t in tokens if t[1] > 0]


def _split_measures(tokens, measure_len):
    """Split tokens at barlines -> pieces (start, dur, content, first, tie_next).

    ``first`` marks the first piece of a note (the one that carries fingering);
    ``tie_next`` ties a note piece to its continuation in the next measure.
    """
    pieces = []
    for start, dur, content in tokens:
        seg_start = start
        remaining = dur
        first = True
        while remaining > 0:
            midx = int(seg_start // measure_len)
            measure_end = (midx + 1) * measure_len
            seg_dur = min(remaining, measure_end - seg_start)
            more = seg_dur < remaining
            pieces.append((seg_start, seg_dur, content, first,
                           more and content is not None))
            seg_start += seg_dur
            remaining -= seg_dur
            first = False
    return pieces


def _render_piece(content, dur, scale, emit_finger, tie_next, accidental):
    """Render one note/chord/rest piece (possibly several tied tokens).

    LilyPond ordering is ``pitch duration -finger`` for a single note and
    ``<pitch-finger ...> duration`` for a chord (fingering inside the chord).
    """
    dtoks = _decompose(dur * scale)
    if content is None:
        return " ".join("r" + t for t in dtoks)

    is_chord = len(content) > 1
    segs = []
    for j, t in enumerate(dtoks):
        with_finger = emit_finger and j == 0
        if is_chord:
            inner = []
            for midi, finger in content:
                p = _midi_to_lily(midi, accidental)
                if with_finger and finger is not None:
                    p += "-" + str(finger)
                inner.append(p)
            segs.append("<" + " ".join(inner) + ">" + t)
        else:
            midi, finger = content[0]
            seg = _midi_to_lily(midi, accidental) + t
            if with_finger and finger is not None:
                seg += "-" + str(finger)
            segs.append(seg)
    s = "~ ".join(segs)
    return s + "~" if tie_next else s


def _render_measure(pieces, measure_start, beat_len, accidental):
    """Render the pieces of a single measure, wrapping tuplet beats."""
    out = []
    pos = measure_start
    i, n = 0, len(pieces)
    while i < n:
        start, dur, content, first, tie_next = pieces[i]
        if _is_tuplet(dur):
            beat_end = (pos // beat_len + 1) * beat_len
            group, gpos = [], pos
            while i < n and gpos < beat_end and _is_tuplet(pieces[i][1]):
                group.append(pieces[i])
                gpos += pieces[i][1]
                i += 1
            g = group[0][1]
            for gp in group[1:]:
                g = _frac_gcd(g, gp[1])
            # Tuplet number = odd part of the subdivision's denominator, so the
            # ratio is correct even for a partial group (e.g. a beat cut short
            # by the slice). written = actual * n/m is always dyadic.
            ncount = g.denominator
            while ncount % 2 == 0:
                ncount //= 2
            m = _largest_pow2_le(ncount)
            ratio = Fraction(ncount, m)
            inner = " ".join(
                _render_piece(c, d, ratio, fst, tn, accidental)
                for (_s, d, c, fst, tn) in group
            )
            out.append(f"\\tuplet {ncount}/{m} {{ {inner} }}")
            pos = gpos
        else:
            out.append(_render_piece(content, dur, Fraction(1),
                                     first, tie_next, accidental))
            pos += dur
            i += 1
    return " ".join(out)


def _render_staff(events, time_signature, accidental):
    """Events for one hand -> LilyPond music string (measures, bar checks)."""
    num, den = time_signature
    measure_len = Fraction(num, den)
    beat_len = Fraction(1, den)

    tokens = _events_to_tokens(events)
    if not tokens:
        return "s1"

    pieces = _split_measures(tokens, measure_len)
    measures = OrderedDict()
    for p in pieces:
        measures.setdefault(int(p[0] // measure_len), []).append(p)

    rendered = [
        _render_measure(measures[midx], midx * measure_len, beat_len, accidental)
        for midx in sorted(measures)
    ]
    # Bar checks between measures only; the final measure may be intentionally
    # incomplete when the input is a mid-piece slice.
    return " |\n    ".join(rendered)


# --------------------------------------------------------------------------- #
# LilyPond document + compilation
# --------------------------------------------------------------------------- #
def _staff_clef(hand, layers):
    """Clef for a hand: explicit if set, else by register / median pitch."""
    if hand.clef:
        return hand.clef
    pitches = [m for layer in layers for (m, _e) in layer["notes"]]
    centre = (sum(pitches) / len(pitches)) if pitches else hand.register
    return "treble" if centre >= 60 else "bass"


def _build_document(staves, time_signature, key, single_group):
    """Assemble the LilyPond document from per-staff specs (top -> bottom).

    ``staves`` is a list of ``(staff_id, clef, orientation, music, group)``.
    Staves sharing a ``group`` are wrapped in one ``PianoStaff`` (a player's grand
    staff); ungrouped staves stand alone. ``single_group`` (no groups configured)
    wraps every staff in a single ``PianoStaff`` -- the classic two-hand grand
    staff, so the default output is unchanged.
    """
    num, den = time_signature
    key_str = f"  \\key {key}\n" if key else ""
    time_str = f"\\time {num}/{den}"

    defs = []
    vars_ = []
    for i, (staff_id, clef, orient, music, group) in enumerate(staves):
        var = "staff" + chr(ord("A") + i)        # LilyPond ids must be letters only
        vars_.append((var, staff_id, group))
        defs.append(
            f"{var} = {{\n  \\clef {clef}\n  {time_str}\n{key_str}"
            f"  \\set fingeringOrientations = #'({orient})\n  {music}\n}}"
        )

    def staff_line(var, staff_id):
        return f'\\new Staff = "{staff_id}" \\{var}'

    if single_group:
        body = "  \\new PianoStaff <<\n" + "".join(
            f"    {staff_line(v, sid)}\n" for v, sid, _g in vars_
        ) + "  >>"
    else:
        # group consecutive staves by their (non-None) group id into PianoStaves.
        chunks = []
        i = 0
        while i < len(vars_):
            v, sid, g = vars_[i]
            if g is None:
                chunks.append([vars_[i]])
                i += 1
            else:
                run = [vars_[i]]
                i += 1
                while i < len(vars_) and vars_[i][2] == g:
                    run.append(vars_[i])
                    i += 1
                chunks.append(run)
        lines = []
        for chunk in chunks:
            if len(chunk) > 1 or chunk[0][2] is not None:
                lines.append("    \\new PianoStaff <<")
                lines += [f"      {staff_line(v, sid)}" for v, sid, _g in chunk]
                lines.append("    >>")
            else:
                v, sid, _g = chunk[0]
                lines.append(f"    {staff_line(v, sid)}")
        body = "  \\new StaffGroup <<\n" + "\n".join(lines) + "\n  >>"

    defs_str = "\n\n".join(defs)
    return f'''\\version "2.26.0"

\\paper {{
  indent = 0\\mm
  line-width = 180\\mm
}}

\\header {{
  tagline = ##f
}}

{defs_str}

\\score {{
<<
{body}
>>
  \\layout {{ }}
}}
'''


def _run_lilypond(ly_path, out_base):
    result = subprocess.run(
        ["lilypond", "--pdf", "-o", out_base, ly_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"lilypond failed (exit {result.returncode}):\n{result.stderr}"
        )
    return out_base + ".pdf"


def render_fingering_pdf(hands, hand_layers, hand_paths,
                         out_path="output/score", time_signature=(4, 4),
                         key=None, accidental="sharp", run_lilypond=True):
    """Render fingered sheet music to ``<out_path>.pdf`` (and ``<out_path>.ly``).

    ``hands`` is the ordered list of :class:`src.hands.Hand` (low -> high);
    ``hand_layers`` and ``hand_paths`` are dicts keyed by ``hand.name`` (the
    per-hand layer stream and the solver's fingering path). One staff is rendered
    per hand; hands sharing a ``group`` form a player's grand staff. Returns the
    PDF path. Set ``run_lilypond=False`` to only emit the ``.ly``.
    """
    single_group = all(h.group is None for h in hands)
    # Display top -> bottom = high register -> low.
    staves = []
    for hand in sorted(hands, key=lambda h: h.register, reverse=True):
        layers = hand_layers.get(hand.name, [])
        path = hand_paths.get(hand.name, [])
        music = _render_staff(_build_events(layers, path), time_signature, accidental)
        clef = _staff_clef(hand, layers)
        orient = "up" if hand.side == "R" else "down"
        staves.append((hand.name, clef, orient, music, hand.group))
    doc = _build_document(staves, time_signature, key, single_group)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    ly_path = out_path + ".ly"
    with open(ly_path, "w") as f:
        f.write(doc)

    if run_lilypond:
        _run_lilypond(ly_path, out_path)
    return out_path + ".pdf"
