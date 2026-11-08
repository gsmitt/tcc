"""Assign every note to a hand (staff) via a register split-point.

An earlier version partitioned the notes into monophonic voices and assigned each
whole voice to a hand by its mean pitch.  That granularity produced two artefacts
on polyphonic textures: a re-struck low pedal tone scattered across voices would
drag a high-mean voice's outliers into the treble staff, and a chord whose notes
landed in voices assigned to different hands was split across staves.  The voice
partition was dropped from the pipeline along with it.

This version decides the staff of each *note* directly, per onset, with a moving
pitch boundary ``b`` (the "split point"): notes below ``b`` go to the left hand,
notes at/above ``b`` to the right.  Because the left hand is always the lower
side of ``b``, it is the lower-register hand by construction.

The boundary is chosen by a Viterbi-style dynamic program over the sequence of
onsets, minimising

    sum_t emission(onset_t, b_t)  +  sum_t smooth_weight * |b_t - b_{t-1}|

where ``emission``

  * softly forbids a hand that exceeds the ergonomic limits -- more than
    ``max_notes_per_hand`` keys, or a stretch wider than ``max_span_semitones``;
  * adds a ``cohesion_penalty`` when ``b`` splits an onset whose notes would all
    fit one hand, so tight chords and octaves stay on one staff.

The ``smooth_weight`` (hysteresis) term keeps ``b`` stable from onset to onset:
absent a feasibility/cohesion reason to move, the boundary stays put, which is
what stops a repeated pedal tone from flip-flopping between staves.  ``b`` is
seeded at ``seed_boundary`` (≈ middle C) so the first division is the
conventional one; thereafter it only moves when the music forces it.  (We use a
*seed* rather than a per-onset pull toward middle C on purpose: a standing pull
would slowly drag the boundary up through a low arpeggio note and re-introduce
the very staff-jumping this fixes.)

Sources this is adapted from (verify exact pages before citing in the thesis):
  * the "stay on the same hand over time" penalty is the simplified, single-
    boundary analogue of the HMM hand-separation in Nakamura, Saito & Yoshii,
    "Statistical Learning and Estimation of Piano Fingering", Information
    Sciences 517 (2020);
  * the keys-per-hand / stretch limits follow Parncutt, Sloboda, Clarke,
    Raekallio & Desain, "An Ergonomic Model of Keyboard Fingering for Melodic
    Fragments", Music Perception 14(4) (1997), Table 1, p. 346 (the *span*
    limits only -- the per-interval move costs are Hart, Bosch & Tsai 2000,
    see :mod:`src.costs`);
  * deciding the split by pitch distance is in the spirit of the contig-
    connection cost of Chew & Wu, "Separating Voices in Polyphonic Music: A
    Contig Mapping Approach", CMMR (2004).

Assigners read the layer sequence of :mod:`src.midi_reader` directly.
"""

FEAS_PENALTY = 1000.0   # soft "infeasible": exceeds keys-per-hand or stretch


def _onsets_from_layers(layers):
    """Return ``[(layer_idx, [(pitch, note_idx), ...]), ...]``, each list pitch-sorted."""
    return [(li, sorted((p, ni) for ni, (p, _e) in enumerate(layer["notes"])))
            for li, layer in enumerate(layers) if layer["notes"]]


def _emission(pitches, b, max_notes, max_span, cohesion_penalty):
    """Cost of splitting one onset's ascending ``pitches`` at boundary ``b``."""
    left = [p for p in pitches if p < b]
    right = [p for p in pitches if p >= b]
    cost = 0.0
    for hand in (left, right):
        if not hand:
            continue
        if len(hand) > max_notes:
            cost += FEAS_PENALTY
        if hand[-1] - hand[0] > max_span:
            cost += FEAS_PENALTY
    if left and right:                              # an actual split happened
        fits_one = (len(pitches) <= max_notes
                    and pitches[-1] - pitches[0] <= max_span)
        if fits_one:                                # ...but it need not have
            cost += cohesion_penalty
    return cost


def assign_layers_to_hands(layers,
                           max_notes_per_hand=5,
                           max_span_semitones=None,
                           smooth_weight=None,
                           cohesion_penalty=None,
                           seed_boundary=60.0):
    """Return a dict ``(layer_idx, note_idx_in_layer) -> "L" | "R"``.

    Every note of ``layers`` is labelled by the split-point DP described
    in the module docstring.  ``None`` takes the value in force:
    ``max_span_semitones`` is the absolute span of the 1-5 pair
    (:data:`src.costs.MAX_ABS`), the widest a hand reaches, and the stability
    and cohesion weights come from :mod:`src.params` (``smooth_split``,
    ``cohesion_split``).
    """
    from src import costs, params
    if max_span_semitones is None:
        max_span_semitones = costs.MAX_ABS[(1, 5)]
    if smooth_weight is None:
        smooth_weight = params.get("smooth_split")
    if cohesion_penalty is None:
        cohesion_penalty = params.get("cohesion_split")
    onsets = _onsets_from_layers(layers)
    if not onsets:
        return {}

    pitch_lists = [[p for p, _ni in notes] for _li, notes in onsets]
    all_pitches = [p for pl in pitch_lists for p in pl]
    lo, hi = min(all_pitches), max(all_pitches)
    # Half-integer candidates from just below the lowest pitch to just above the
    # highest, so "all right" (b <= lo) and "all left" (b > hi) are reachable.
    boundaries = [lo - 0.5 + i for i in range(hi - lo + 2)]

    def emit(t, b):
        return _emission(pitch_lists[t], b, max_notes_per_hand,
                         max_span_semitones, cohesion_penalty)

    # Forward pass. dp[k] = best cost of reaching this onset with boundaries[k];
    # back[t-1][k] = the previous onset's boundary index chosen to reach k here.
    dp = [emit(0, b) + smooth_weight * abs(b - seed_boundary) for b in boundaries]
    back = []
    for t in range(1, len(onsets)):
        new_dp = [0.0] * len(boundaries)
        choice = [0] * len(boundaries)
        for ki, b in enumerate(boundaries):
            best_c, best_j = None, 0
            for kj, bp in enumerate(boundaries):
                c = dp[kj] + smooth_weight * abs(b - bp)
                if best_c is None or c < best_c:
                    best_c, best_j = c, kj
            new_dp[ki] = best_c + emit(t, b)
            choice[ki] = best_j
        dp = new_dp
        back.append(choice)

    # Backtrack the optimal boundary at every onset.
    k = min(range(len(boundaries)), key=lambda i: dp[i])
    chosen = [0] * len(onsets)
    chosen[-1] = k
    for t in range(len(onsets) - 1, 0, -1):
        k = back[t - 1][k]
        chosen[t - 1] = k

    labels = {}
    for t, (layer_idx, notes) in enumerate(onsets):
        b = boundaries[chosen[t]]
        for pitch, note_idx in notes:
            labels[(layer_idx, note_idx)] = "L" if pitch < b else "R"
    return labels


def split_layers_by_hands(layers, hand_labels, hands):
    """Partition each layer's notes by hand label, for an arbitrary set of hands.

    ``hand_labels`` maps ``(layer_idx, note_idx) -> hand.name``. Returns a dict
    ``{hand.name: layers}``; layers with no notes for a hand are omitted from that
    hand's stream. Each hand's notes are sorted so the solver's ascending finger
    combinations map onto the thumb-side note: a right-side ("R") hand has the
    thumb on its lowest key (ascending), a left-side ("L") hand on its highest
    (descending). Keeps fingering generation consistent with ``chord_complexity``.
    """
    streams = {h.name: [] for h in hands}
    side_of = {h.name: h.side for h in hands}
    for layer_idx, layer in enumerate(layers):
        buckets = {h.name: [] for h in hands}
        for note_idx, (pitch, end) in enumerate(layer["notes"]):
            name = hand_labels.get((layer_idx, note_idx))
            if name in buckets:
                buckets[name].append((pitch, end))
        for name, notes in buckets.items():
            if not notes:
                continue
            notes.sort(key=lambda ne: ne[0], reverse=(side_of[name] == "L"))
            streams[name].append({"time": layer["time"], "notes": notes})
    return streams


def split_layers_by_hand(layers, hand_labels):
    """Two-hand convenience wrapper: return ``(lh_layers, rh_layers)``.

    Kept for callers that still expect the original "L"/"R" pair.
    """
    lh_layers = []
    rh_layers = []
    for layer_idx, layer in enumerate(layers):
        lh_notes = []
        rh_notes = []
        for note_idx, (pitch, end) in enumerate(layer["notes"]):
            hand = hand_labels.get((layer_idx, note_idx))
            if hand == "L":
                lh_notes.append((pitch, end))
            elif hand == "R":
                rh_notes.append((pitch, end))
        lh_notes.sort(key=lambda ne: ne[0], reverse=True)
        rh_notes.sort(key=lambda ne: ne[0])
        if lh_notes:
            lh_layers.append({"time": layer["time"], "notes": lh_notes})
        if rh_notes:
            rh_layers.append({"time": layer["time"], "notes": rh_notes})
    return lh_layers, rh_layers
