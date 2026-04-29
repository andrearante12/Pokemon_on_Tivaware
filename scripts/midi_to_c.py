#!/usr/bin/env python3
"""
midi_to_c.py  <file.mid>
Converts a MIDI file to a C note_t array named after the file.
Redirect stdout into a .h file of the same name.

Usage:
    pip install mido
    python3 midi_to_c.py track1.mid > track1.h
    python3 midi_to_c.py track2.mid > track2.h

Notes:
  - Monophonic: when multiple notes sound simultaneously, the highest pitch wins.
  - {0,0} sentinel at end signals end-of-track to the ISR playlist.
"""

import sys, os

try:
    import mido
except ImportError:
    print("ERROR: mido not installed. Run: pip install mido", file=sys.stderr)
    sys.exit(1)

MIDI_FREQ = [round(440.0 * 2 ** ((n - 69) / 12.0)) for n in range(128)]
MIN_DUR_MS = 20


def convert(path):
    name  = os.path.splitext(os.path.basename(path))[0]   # e.g. "track1"
    guard = f"SONG_{name.upper()}_H"
    array = f"SONG_{name}"

    mid = mido.MidiFile(path)
    abs_s = 0.0
    active = {}
    completed = []

    for msg in mid:
        abs_s += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            active[msg.note] = abs_s
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in active:
                completed.append((active.pop(msg.note), abs_s, msg.note))

    if not completed:
        print("ERROR: no notes found in MIDI file.", file=sys.stderr)
        sys.exit(1)

    completed.sort(key=lambda e: e[0])

    times = sorted({t for s, e, _ in completed for t in (s, e)})
    segments = []
    for i in range(len(times) - 1):
        t0, t1 = times[i], times[i + 1]
        best = None
        for start, end, note in completed:
            if start <= t0 and end >= t1:
                if best is None or note > best:
                    best = note
        segments.append((t0, t1, best))

    pairs = []
    for t0, t1, note in segments:
        dur_ms = max(MIN_DUR_MS, round((t1 - t0) * 1000))
        freq   = MIDI_FREQ[note] if note is not None else 0
        if pairs and pairs[-1][0] == freq:
            pairs[-1] = (freq, pairs[-1][1] + dur_ms)
        else:
            pairs.append((freq, dur_ms))

    print(f"#ifndef {guard}")
    print(f"#define {guard}")
    print()
    print("#ifndef NOTE_T_DEFINED")
    print("#define NOTE_T_DEFINED")
    print("typedef struct { uint32_t freq_hz; uint32_t dur_ms; } note_t;")
    print("#endif")
    print()
    print(f"/* {len(pairs)} entries from {path} */")
    print(f"static const note_t {array}[] = {{")
    for freq, dur in pairs:
        print(f"    {{{freq:5d}, {dur:5d}}},")
    print("    {0, 0}")
    print("};")
    print()
    print(f"#endif /* {guard} */")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <file.mid> > trackN.h", file=sys.stderr)
        sys.exit(1)
    convert(sys.argv[1])
