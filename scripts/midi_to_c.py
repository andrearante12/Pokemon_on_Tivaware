#!/usr/bin/env python3
"""midi_to_c.py <file.mid>  -- emits a (beat, len) byte array on stdout.

Output format matches the course's `twinkle` example:
   #define <NAME>_LEN   <pair-count>
   #define <NAME>_TEMPO <ms-per-len-unit>
   static const uint8_t <name>[] = {
       C5,  6,   S, 1,   D5, 5,  ...
   };
where each (beat, len) pair encodes one note (or rest if beat == S == 0).
beat is the symbolic name index defined in music/notes.h; duration is
`len * TEMPO` milliseconds.
"""

import sys, os, mido

# MIDI note number -> example's symbolic name (1-based index into notes[]).
# Covers C4 (MIDI 60) through C8 (MIDI 108). Out-of-range notes become 'S'.
MIDI_NAMES = {
    60:'C4', 61:'Db4', 62:'D4', 63:'Eb4', 64:'E4', 65:'F4', 66:'Gb4', 67:'G4',
    68:'Ab4', 69:'A4', 70:'Bb4', 71:'B4', 72:'C5', 73:'Db5', 74:'D5', 75:'Eb5',
    76:'E5', 77:'F5', 78:'Gb5', 79:'G5', 80:'Ab5', 81:'A5', 82:'Bb5', 83:'B5',
    84:'C6', 85:'Db6', 86:'D6', 87:'Eb6', 88:'E6', 89:'F6', 90:'Gb6', 91:'G6',
    92:'Ab6', 93:'A6', 94:'Bb6', 95:'B6', 96:'C7', 102:'Gb7', 103:'G7',
    105:'A7', 107:'B7', 108:'C8',
}

# How many milliseconds one `len` unit represents. Notes get rounded to this grid.
TEMPO_MS = 20
MIN_DUR_MS = TEMPO_MS    # collapse anything below one TEMPO unit


def beat_for_pitch(pitch):
    """MIDI note number → example symbolic name, or 'S' for unsupported."""
    if pitch is None:
        return 'S'
    return MIDI_NAMES.get(pitch, 'S')


name = os.path.splitext(os.path.basename(sys.argv[1]))[0]   # e.g. "track1"

# ── Step 1: parse MIDI events into (start, end, pitch) triples ──────────────
t, active, raw_notes = 0.0, {}, []
for msg in mido.MidiFile(sys.argv[1]):
    t += msg.time
    if msg.type == 'note_on' and msg.velocity:
        active[msg.note] = t
    elif msg.type in ('note_off', 'note_on') and msg.note in active:
        raw_notes.append((active.pop(msg.note), t, msg.note))

# ── Step 2: slice timeline; pick highest pitch per slice (chord → melody) ──
times = sorted({x for s, e, _ in raw_notes for x in (s, e)})
slices = []
for t0, t1 in zip(times, times[1:]):
    best = max((n for s, e, n in raw_notes if s <= t0 and e >= t1), default=None)
    dur_ms = max(MIN_DUR_MS, round((t1 - t0) * 1000))
    slices.append((best, dur_ms))

# ── Step 3: coalesce consecutive same-pitch slices ──────────────────────────
coalesced = []
for pitch, dur_ms in slices:
    if coalesced and coalesced[-1][0] == pitch:
        coalesced[-1] = (pitch, coalesced[-1][1] + dur_ms)
    else:
        coalesced.append((pitch, dur_ms))

# ── Step 4: emit (beat, len) byte pairs in the example's format ─────────────
out_pairs = []
for pitch, dur_ms in coalesced:
    beat = beat_for_pitch(pitch)
    units = max(1, round(dur_ms / TEMPO_MS))
    while units > 255:
        out_pairs.append((beat, 255))
        units -= 255
    out_pairs.append((beat, units))

NAME = name.upper()
print(f"#define {NAME}_LEN   {len(out_pairs)}")
print(f"#define {NAME}_TEMPO {TEMPO_MS}")
print()
print(f"static const uint8_t {name}[] = {{")
for beat, length in out_pairs:
    print(f"    {beat:>4}, {length:3d},")
print("};")
