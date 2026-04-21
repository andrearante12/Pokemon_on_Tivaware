#!/usr/bin/env python3
"""
display.py — laptop-side serial renderer.

Usage:
  python display.py /dev/cu.usbmodem0001    # read from serial port
  python display.py --test                   # read commands from stdin
  python display.py --list                   # list available serial ports

Commands (newline-terminated):
  SHOW:<name>              display a single sprite fullscreen
  BATTLE:<player>:<enemy>  compose battle scene
  CLEAR                    clear the screen
  MSG:<text>               print a plain text line
"""

import sys
import argparse

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

import assets

BAUD            = 115200
PLAYER_V_OFFSET = 40    # rows from top where the player sprite begins
SPRITE_H_GAP    = 60    # horizontal chars between player right edge and enemy left edge
DEFAULT_PLAYER  = 'squirtle'
DEFAULT_ENEMY   = 'bulbasaur'


def clear_screen():
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# 5-row pixel font  (█ = filled, space = empty, each glyph is 5 chars wide)
# ---------------------------------------------------------------------------

_F = '█'

_FONT = {
    ' ': ['     ', '     ', '     ', '     ', '     '],
    'A': [' ███ ', '█   █', '█████', '█   █', '█   █'],
    'B': ['████ ', '█   █', '████ ', '█   █', '████ '],
    'C': [' ████', '█    ', '█    ', '█    ', ' ████'],
    'D': ['███  ', '█  █ ', '█   █', '█  █ ', '███  '],
    'E': ['█████', '█    ', '████ ', '█    ', '█████'],
    'F': ['█████', '█    ', '████ ', '█    ', '█    '],
    'G': [' ████', '█    ', '█  ██', '█   █', ' ████'],
    'H': ['█   █', '█   █', '█████', '█   █', '█   █'],
    'I': ['█████', '  █  ', '  █  ', '  █  ', '█████'],
    'J': ['█████', '    █', '    █', '█   █', ' ███ '],
    'K': ['█   █', '█  █ ', '███  ', '█  █ ', '█   █'],
    'L': ['█    ', '█    ', '█    ', '█    ', '█████'],
    'M': ['█   █', '██ ██', '█ █ █', '█   █', '█   █'],
    'N': ['█   █', '██  █', '█ █ █', '█  ██', '█   █'],
    'O': [' ███ ', '█   █', '█   █', '█   █', ' ███ '],
    'P': ['████ ', '█   █', '████ ', '█    ', '█    '],
    'Q': [' ███ ', '█   █', '█ █ █', '█  █ ', ' ██ █'],
    'R': ['████ ', '█   █', '████ ', '█  █ ', '█   █'],
    'S': [' ████', '█    ', ' ███ ', '    █', '████ '],
    'T': ['█████', '  █  ', '  █  ', '  █  ', '  █  '],
    'U': ['█   █', '█   █', '█   █', '█   █', ' ███ '],
    'V': ['█   █', '█   █', '█   █', ' █ █ ', '  █  '],
    'W': ['█   █', '█   █', '█ █ █', '██ ██', '█   █'],
    'X': ['█   █', ' █ █ ', '  █  ', ' █ █ ', '█   █'],
    'Y': ['█   █', ' █ █ ', '  █  ', '  █  ', '  █  '],
    'Z': ['█████', '   █ ', '  █  ', ' █   ', '█████'],
    '0': [' ███ ', '█  ██', '█ █ █', '██  █', ' ███ '],
    '1': [' ██  ', '  █  ', '  █  ', '  █  ', '█████'],
    '2': [' ███ ', '█   █', '  ██ ', ' █   ', '█████'],
    '3': ['████ ', '    █', ' ███ ', '    █', '████ '],
    '4': ['█   █', '█   █', '█████', '    █', '    █'],
    '5': ['█████', '█    ', '████ ', '    █', '████ '],
    '6': [' ███ ', '█    ', '████ ', '█   █', ' ███ '],
    '7': ['█████', '    █', '   █ ', '  █  ', '  █  '],
    '8': [' ███ ', '█   █', ' ███ ', '█   █', ' ███ '],
    '9': [' ███ ', '█   █', ' ████', '    █', ' ███ '],
    '!': ['  █  ', '  █  ', '  █  ', '     ', '  █  '],
    '?': [' ███ ', '█   █', '  ██ ', '     ', '  █  '],
    '/': ['    █', '   █ ', '  █  ', ' █   ', '█    '],
    '.': ['     ', '     ', '     ', ' ██  ', ' ██  '],
    '-': ['     ', '     ', '█████', '     ', '     '],
    '>': ['█    ', '██   ', '███  ', '██   ', '█    '],
    '\'': [' ██  ', ' █   ', '     ', '     ', '     '],
}

_UNKNOWN_GLYPH = ['     ', ' ███ ', ' █ █ ', ' ███ ', '     ']


def _render_text(text):
    """Render a string using the pixel font. Returns a list of 5 strings."""
    rows = ['', '', '', '', '']
    for i, ch in enumerate(text.upper()):
        glyph = _FONT.get(ch, _UNKNOWN_GLYPH)
        for r in range(5):
            rows[r] += glyph[r]
            if i < len(text) - 1:
                rows[r] += ' '  # 1-col gap between characters
    return rows


# ---------------------------------------------------------------------------
# Canvas helpers
# ---------------------------------------------------------------------------

def _tight(raw_lines):
    lines = list(raw_lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return lines
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    return [l[indent:] for l in lines]


def _stamp(canvas, sprite, row_offset, col_offset):
    for i, line in enumerate(sprite):
        r = row_offset + i
        if r >= len(canvas):
            break
        for j, ch in enumerate(line):
            c = col_offset + j
            if c < len(canvas[r]):
                canvas[r][c] = ch


# ---------------------------------------------------------------------------
# UI element builders
# ---------------------------------------------------------------------------

def _large_hp_bar(hp, max_hp, bar_w=72):
    filled = round(bar_w * hp / max_hp) if max_hp > 0 else 0
    empty  = bar_w - filled
    label  = _render_text('HP')
    bar    = [
        '+-' + '-' * bar_w + '-+',
        '| ' + '█' * filled + '░' * empty + ' |',
        '| ' + '█' * filled + '░' * empty + ' |',
        '| ' + '█' * filled + '░' * empty + ' |',
        '+-' + '-' * bar_w + '-+',
    ]
    return [l + '  ' + b for l, b in zip(label, bar)]


def _make_info_box(content_rows):
    # rows prefixed with '\r' are right-aligned; strip marker for width calc
    clean   = [r[1:] if r.startswith('\r') else r for r in content_rows]
    inner_w = max(len(r) for r in clean) + 2
    border  = '+' + '-' * (inner_w + 2) + '+'
    out     = [border]
    for raw, r in zip(content_rows, clean):
        justified = r.rjust(inner_w) if raw.startswith('\r') else r.ljust(inner_w)
        out.append('| ' + justified + ' |')
    out.append(border)
    return out


def _enemy_info(name, level, hp, max_hp):
    return _make_info_box(
        [''] +
        _render_text(f"{name.upper()}  LV{level}") +
        [''] +
        _large_hp_bar(hp, max_hp) +
        [''] +
        ['\r' + r for r in _render_text(f"{hp}/{max_hp}")] +
        ['']
    )


def _player_info(name, level, hp, max_hp):
    return _make_info_box(
        [''] +
        _render_text(f"{name.upper()}  LV{level}") +
        [''] +
        _large_hp_bar(hp, max_hp) +
        [''] +
        ['\r' + r for r in _render_text(f"{hp}/{max_hp}")] +
        ['']
    )


def _bottom_panel(player_name, moves, selected, canvas_w):
    half      = canvas_w // 2
    msg_inner = half - 4
    mov_inner = canvas_w - half - 4
    pad = '  '  # left indent inside box

    # --- message box content ---
    msg_rows = ['', '']
    for r in _render_text('WHAT WILL'):
        msg_rows.append(pad + r)
    msg_rows.append('')
    for r in _render_text(f"{player_name.upper()} DO?"):
        msg_rows.append(pad + r)
    msg_rows += ['', '']

    # --- moves box content (2 x 2 grid) ---
    mov_rows = ['', '']
    col_w = mov_inner // 2  # width allocated per column
    for row_i in range(2):
        l_idx  = row_i * 2
        r_idx  = row_i * 2 + 1
        l_move = moves[l_idx] if l_idx < len(moves) else ''
        r_move = moves[r_idx] if r_idx < len(moves) else ''
        l_pre  = '> ' if selected == l_idx else '  '
        r_pre  = '> ' if selected == r_idx else '  '
        left_rendered  = _render_text(l_pre + l_move)
        right_rendered = _render_text(r_pre + r_move)
        if row_i > 0:
            mov_rows.append('')
        for l, r in zip(left_rendered, right_rendered):
            mov_rows.append(pad + l.ljust(col_w) + r)
    mov_rows += ['', '']

    # --- build side-by-side boxes of equal height ---
    box_h = max(len(msg_rows), len(mov_rows)) + 2  # +2 borders

    def make_box(content, inner_w):
        b = '+' + '-' * (inner_w + 2) + '+'
        out = [b]
        for i in range(box_h - 2):
            text = content[i] if i < len(content) else ''
            out.append('| ' + text.ljust(inner_w)[:inner_w] + ' |')
        out.append(b)
        return out

    left  = make_box(msg_rows,  msg_inner)
    right = make_box(mov_rows, mov_inner)
    return [a + b for a, b in zip(left, right)]


# ---------------------------------------------------------------------------
# Scene composition
# ---------------------------------------------------------------------------

def compose_battle(player_name, enemy_name,
                   player_hp=20, player_max_hp=20, player_level=5,
                   enemy_hp=45,  enemy_max_hp=45,  enemy_level=5,
                   moves=None, selected=0):

    if moves is None:
        moves = ["FIGHT", "BAG", "POKEMON", "RUN"]

    player = _tight(assets.lines(player_name))
    enemy  = _tight(assets.lines(enemy_name))

    player_w  = max((len(l) for l in player), default=0)
    enemy_w   = max((len(l) for l in enemy),  default=0)
    enemy_col = player_w + SPRITE_H_GAP

    # Build info boxes first so we can measure their widths
    e_info = _enemy_info(enemy_name,   enemy_level,  enemy_hp,  enemy_max_hp)
    p_info = _player_info(player_name, player_level, player_hp, player_max_hp)
    p_info_w = max(len(l) for l in p_info)

    # Base canvas size (used to derive shift amounts)
    canvas_w_base = enemy_col + enemy_w + 4
    sprite_end    = PLAYER_V_OFFSET + len(player) + 2
    panel_base    = _bottom_panel(player_name, moves, selected, canvas_w_base)
    canvas_h_base = sprite_end + len(panel_base) + 1

    v_shift    = canvas_h_base // 5
    h_shift    = canvas_w_base * 2 // 5
    up_shift   = canvas_h_base // 8
    left_shift = canvas_w_base // 5

    extra_left  = canvas_w_base // 5
    extra_right = canvas_w_base // 6

    e_info_row = max(0, v_shift - up_shift)
    e_info_col = max(0, h_shift - left_shift - extra_left + extra_right - 18)
    p_info_row = max(0, PLAYER_V_OFFSET + 10 + v_shift - up_shift + canvas_h_base // 5 - 12)
    p_info_col = max(0, player_w + 10 + h_shift - left_shift - extra_left + extra_right)

    # Panel spans from e_info_col (left-aligned with bulbasaur HP box)
    # to enemy_col + enemy_w (right-aligned with bulbasaur sprite)
    panel_w  = enemy_col + enemy_w - e_info_col + 20
    panel    = _bottom_panel(player_name, moves, selected, panel_w)
    canvas_w = max(canvas_w_base, p_info_col + p_info_w + 2)
    canvas_h = sprite_end + len(panel) + 1

    canvas = [[' '] * canvas_w for _ in range(canvas_h)]

    # Sprites — squirtle left edge aligned with e_info_col
    _stamp(canvas, enemy,  10,              enemy_col)
    _stamp(canvas, player, PLAYER_V_OFFSET, e_info_col)

    # Info boxes at shifted positions
    _stamp(canvas, e_info, e_info_row, e_info_col)
    _stamp(canvas, p_info, p_info_row + 10, p_info_col)

    # Bottom panel — left edge at e_info_col, right edge at enemy right
    _stamp(canvas, panel, sprite_end, e_info_col - 10)

    return '\n'.join(''.join(row).rstrip() for row in canvas)


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

def handle_line(line):
    line = line.strip()
    if not line:
        return
    if line.startswith("BATTLE:"):
        parts = line[7:].split(':')
        if len(parts) >= 2:
            clear_screen()
            print(compose_battle(parts[0], parts[1]))
        else:
            print("Usage: BATTLE:<player>:<enemy>")
    elif line.startswith("SHOW:"):
        name = line[5:].strip()
        clear_screen()
        try:
            print(assets.load(name))
        except FileNotFoundError:
            print(f"[unknown sprite: '{name}']\nAvailable: {', '.join(assets.available())}")
    elif line == "CLEAR":
        clear_screen()
    elif line.startswith("MSG:"):
        print(line[4:].strip())
    else:
        print(f">> {line}")


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def run_serial(port, player=DEFAULT_PLAYER, enemy=DEFAULT_ENEMY):
    if not SERIAL_AVAILABLE:
        print("Error: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)
    print(f"Connecting to {port} at {BAUD} baud...")
    with serial.Serial(port, BAUD, timeout=1) as ser:
        clear_screen()
        print(compose_battle(player, enemy))
        while True:
            try:
                raw = ser.readline()
                if raw:
                    handle_line(raw.decode('utf-8', errors='replace'))
            except KeyboardInterrupt:
                print("\nDisconnected.")
                break


def run_stdin(player=DEFAULT_PLAYER, enemy=DEFAULT_ENEMY):
    clear_screen()
    print(compose_battle(player, enemy))
    print("\n[test mode — commands: BATTLE:<player>:<enemy>  SHOW:<name>  CLEAR]\n")
    try:
        for line in sys.stdin:
            handle_line(line)
    except KeyboardInterrupt:
        pass


def list_ports():
    if not SERIAL_AVAILABLE:
        print("Error: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
    for p in ports:
        print(f"  {p.device}  —  {p.description}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pokemon Battle serial display')
    parser.add_argument('port', nargs='?', help='Serial port, e.g. /dev/cu.usbmodem0001')
    parser.add_argument('--test',   action='store_true', help='Read commands from stdin')
    parser.add_argument('--list',   action='store_true', help='List available serial ports')
    parser.add_argument('--player', default=DEFAULT_PLAYER, help=f'Player sprite name (default: {DEFAULT_PLAYER})')
    parser.add_argument('--enemy',  default=DEFAULT_ENEMY,  help=f'Enemy sprite name  (default: {DEFAULT_ENEMY})')
    args = parser.parse_args()

    if args.list:
        list_ports()
    elif args.test:
        run_stdin(args.player, args.enemy)
    elif args.port:
        run_serial(args.port, args.player, args.enemy)
    else:
        parser.print_help()
        print(f"\nAvailable sprites: {', '.join(assets.available())}")
        sys.exit(1)
