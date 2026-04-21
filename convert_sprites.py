#!/usr/bin/env python3
"""
convert_sprites.py — reads assets/*.txt, outputs C string array literals.
Run from the final_project/ directory. Redirect stdout into a .c or .h file.

Usage:  python3 convert_sprites.py > sprites_data.c
"""
import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')


def _encode_line(line):
    """Encode a Unicode string as the body of a C string literal (no outer quotes).
    Non-ASCII bytes are written as \\xNN; if the next char is an ASCII hex digit
    a string-concat break ('" "') is inserted to avoid accidental hex overflow."""
    result = []
    raw = line.encode('utf-8')
    i = 0
    while i < len(raw):
        b = raw[i]
        if b == ord('"'):
            result.append('\\"')
        elif b == ord('\\'):
            result.append('\\\\')
        elif 32 <= b < 127:
            result.append(chr(b))
        else:
            result.append(f'\\x{b:02x}')
            if i + 1 < len(raw) and raw[i + 1] < 128:
                nc = chr(raw[i + 1])
                if nc in '0123456789abcdefABCDEF':
                    result.append('" "')
        i += 1
    return ''.join(result)


def convert(name):
    path = os.path.join(ASSETS_DIR, f'{name}.txt')
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n\r') for l in f.readlines()]

    # strip leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    # strip common left indent
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    lines = [l[indent:].rstrip() for l in lines]

    print(f'static const char *{name}[] = {{')
    for line in lines:
        print(f'    "{_encode_line(line)}",')
    print('    0')
    print('};')
    print()


if __name__ == '__main__':
    for f in sorted(os.listdir(ASSETS_DIR)):
        if f.endswith('.txt'):
            convert(f[:-4])
