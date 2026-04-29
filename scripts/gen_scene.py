#!/usr/bin/env python3
"""
gen_scene.py — generates scene_data.h and scene_pos.h from the project's
battle scene definition.

Self-contained: includes asset loading, font rendering, layout composition,
and codegen. The only external dependency is font_small_block.py, which
must live alongside this script.

Run from anywhere:
    python3 final_project/scripts/gen_scene.py
"""

import sys
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from font_small_block import render as _render_block, ROWS as BLOCK_ROWS, COLS as BLOCK_COLS

ASSETS_DIR = os.path.join(PROJECT_DIR, 'assets')


# ── Asset loader (was assets.py) ────────────────────────────────────────────

def asset_lines(name):
    """Return the contents of assets/<name>.txt as a list of lines."""
    with open(os.path.join(ASSETS_DIR, f"{name}.txt"), encoding='utf-8') as f:
        return f.read().splitlines()


# ── Battle parameters ───────────────────────────────────────────────────────

PLAYER_NAME  = "squirtle"
ENEMY_NAME   = "bulbasaur"
PLAYER_HP    = 20
PLAYER_MAX   = 20
PLAYER_LEVEL = 5
ENEMY_HP     = 20
ENEMY_MAX    = 20
ENEMY_LEVEL  = 5
MOVES        = ["FIGHT", "BAG", "POKEMON", "RUN"]


# ── Layout constants (was in display.py) ────────────────────────────────────

PLAYER_V_OFFSET = 40    # rows from top where the player sprite begins
SPRITE_H_GAP    = 60    # horizontal chars between player right edge and enemy left edge


# ── Font rendering (was in display.py) ──────────────────────────────────────

def _render_text(text):
    """Render a string in the smblock pixel font. Returns BLOCK_ROWS strings."""
    return _render_block(text.upper())


# ── Canvas helpers (was in display.py) ──────────────────────────────────────

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


# ── UI element builders (was in display.py) ────────────────────────────────

def _large_hp_bar(hp, max_hp, bar_w=72):
    filled  = round(bar_w * hp / max_hp) if max_hp > 0 else 0
    empty   = bar_w - filled
    label   = _render_text('HP')
    label_w = len(label[0]) if label else 0
    bar = [
        '+-' + '-' * bar_w + '-+',
        '| ' + '█' * filled + '░' * empty + ' |',
        '| ' + '█' * filled + '░' * empty + ' |',
        '| ' + '█' * filled + '░' * empty + ' |',
        '+-' + '-' * bar_w + '-+',
    ]
    return [(label[i] if i < len(label) else ' ' * label_w) + '  ' + bar[i]
            for i in range(len(bar))]


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
    col_w = mov_inner // 2
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


# ── Scene composition (was compose_battle in display.py) ───────────────────

def compose_battle(player_name, enemy_name,
                   player_hp=20, player_max_hp=20, player_level=5,
                   enemy_hp=20,  enemy_max_hp=20,  enemy_level=5,
                   moves=None, selected=0):

    if moves is None:
        moves = ["FIGHT", "BAG", "POKEMON", "RUN"]

    player = _tight(asset_lines(player_name))
    enemy  = _tight(asset_lines(enemy_name))

    player_w  = max((len(l) for l in player), default=0)
    enemy_w   = max((len(l) for l in enemy),  default=0)
    enemy_col = player_w + SPRITE_H_GAP

    e_info = _enemy_info(enemy_name,   enemy_level,  enemy_hp,  enemy_max_hp)
    p_info = _player_info(player_name, player_level, player_hp, player_max_hp)
    p_info_w = max(len(l) for l in p_info)

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

    panel_w  = enemy_col + enemy_w - e_info_col + 20
    panel    = _bottom_panel(player_name, moves, selected, panel_w)
    canvas_w = max(canvas_w_base, p_info_col + p_info_w + 2)
    canvas_h = sprite_end + len(panel) + 1

    canvas = [[' '] * canvas_w for _ in range(canvas_h)]

    _stamp(canvas, enemy,  10,              enemy_col)
    _stamp(canvas, player, PLAYER_V_OFFSET, e_info_col)

    _stamp(canvas, e_info, e_info_row, e_info_col)
    _stamp(canvas, p_info, p_info_row + 10, p_info_col)

    _stamp(canvas, panel, sprite_end, e_info_col - 10)

    return '\n'.join(''.join(row).rstrip() for row in canvas)


# ── C-string-literal encoder ────────────────────────────────────────────────

def _encode_line(line):
    """Encode a Unicode string as the body of a C string literal (no outer
    quotes). Emits raw UTF-8 — relies on the C compiler accepting multi-byte
    characters in string literals (modern GCC/Clang/TI Clang all do)."""
    return line.replace('\\', '\\\\').replace('"', '\\"')


# ── Layout computation ──────────────────────────────────────────────────────

def compute_layout():
    """Replicate compose_battle() math and return exact position info."""
    player = _tight(asset_lines(PLAYER_NAME))
    enemy  = _tight(asset_lines(ENEMY_NAME))

    player_w  = max(len(l) for l in player)
    enemy_w   = max(len(l) for l in enemy)
    enemy_col = player_w + SPRITE_H_GAP

    e_info = _enemy_info(ENEMY_NAME, ENEMY_LEVEL, ENEMY_HP, ENEMY_MAX)
    p_info = _player_info(PLAYER_NAME, PLAYER_LEVEL, PLAYER_HP, PLAYER_MAX)

    canvas_w_base = enemy_col + enemy_w + 4
    sprite_end    = PLAYER_V_OFFSET + len(player) + 2

    panel_base    = _bottom_panel(PLAYER_NAME, MOVES, 0, canvas_w_base)
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
    p_stamp_row = p_info_row + 10

    panel_w  = enemy_col + enemy_w - e_info_col + 20

    half      = panel_w // 2
    msg_inner = half - 4
    mov_inner = panel_w - half - 4
    col_w     = mov_inner // 2

    panel_col = e_info_col - 10

    # HP bar content column within info box row:
    HP_LABEL_W = len(_render_text('HP')[0])
    hp_bar_col_in_box = 2 + HP_LABEL_W + 2 + 2

    info_inner_w = len(e_info[1]) - 4   # strip '| ' and ' |'

    move_box_left_col = panel_col + half

    # Move font rows within panel (0-indexed from panel top):
    #   row 0          : top border
    #   rows 1-2       : empty
    #   rows 3 .. 3+BR-1 : first move row (FIGHT/BAG)
    #   row 3+BR       : empty separator
    #   rows 4+BR ..   : second move row (POKEMON/RUN)
    MOVE_ROW_TOP_IN_PANEL    = 3
    MOVE_ROW_BOTTOM_IN_PANEL = 3 + BLOCK_ROWS + 1

    move_content_col_0 = move_box_left_col + 4
    move_content_col_1 = move_box_left_col + 4 + col_w

    DIALOG_ROW_IN_PANEL = 3
    dialog_col_0indexed = panel_col + 4

    return {
        'e_info_row'          : e_info_row,
        'e_info_col'          : e_info_col,
        'p_stamp_row'         : p_stamp_row,
        'p_info_col'          : p_info_col,
        'sprite_end'          : sprite_end,
        'enemy_col'           : enemy_col,
        'panel_col'           : panel_col,
        'panel_w'             : panel_w,
        'msg_inner'           : msg_inner,
        'col_w'               : col_w,
        'info_inner_w'        : info_inner_w,
        'hp_bar_col_in_box'   : hp_bar_col_in_box,
        'move_content_col_0'  : move_content_col_0,
        'move_content_col_1'  : move_content_col_1,
        'MOVE_ROW_TOP'        : MOVE_ROW_TOP_IN_PANEL,
        'MOVE_ROW_BOT'        : MOVE_ROW_BOTTOM_IN_PANEL,
        'DIALOG_ROW_IN_PANEL' : DIALOG_ROW_IN_PANEL,
        'dialog_col_0indexed' : dialog_col_0indexed,
    }


# ── scene_data.h  (full rendered scene) ─────────────────────────────────────

def emit_scene_header(outpath):
    scene = compose_battle(
        PLAYER_NAME, ENEMY_NAME,
        player_hp=PLAYER_HP, player_max_hp=PLAYER_MAX, player_level=PLAYER_LEVEL,
        enemy_hp=ENEMY_HP,   enemy_max_hp=ENEMY_MAX,   enemy_level=ENEMY_LEVEL,
        selected=0
    )
    rows = scene.split('\n')
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write('/* Auto-generated by gen_scene.py -- do not edit */\n')
        f.write('#ifndef SCENE_DATA_H\n')
        f.write('#define SCENE_DATA_H\n')
        f.write('static const char * const SCENE[] = {\n')
        for row in rows:
            f.write(f'    "{_encode_line(row)}",\n')
        f.write('    0\n')
        f.write('};\n')
        f.write('#endif /* SCENE_DATA_H */\n')
    print(f'Written {outpath}  ({len(rows)} rows)')


# ── scene_pos.h  (ANSI positions + dialog message blocks) ───────────────────

def emit_pos_header(lay, outpath):
    def ansi(r, c=None):
        if c is None:
            return r + 1
        return (r + 1, c + 1)

    e_r, e_c   = ansi(lay['e_info_row'], lay['e_info_col'])
    p_r, p_c   = ansi(lay['p_stamp_row'], lay['p_info_col'])
    se         = lay['sprite_end']
    iw         = lay['info_inner_w']
    hb_off     = lay['hp_bar_col_in_box']

    e_hp_bar_row = e_r + 4 + BLOCK_ROWS
    e_hp_bar_col = e_c + hb_off
    p_hp_bar_row = p_r + 4 + BLOCK_ROWS
    p_hp_bar_col = p_c + hb_off

    e_hp_num_row   = e_r + 9 + BLOCK_ROWS
    e_hp_num_right = e_c + 2 + iw
    p_hp_num_row   = p_r + 9 + BLOCK_ROWS
    p_hp_num_right = p_c + 2 + iw

    move0_row = ansi(se + lay['MOVE_ROW_TOP'])
    move1_row = move0_row
    move2_row = ansi(se + lay['MOVE_ROW_BOT'])
    move3_row = move2_row

    move0_col = ansi(lay['move_content_col_0'])
    move1_col = ansi(lay['move_content_col_1'])
    move2_col = move0_col
    move3_col = move1_col

    dialog_row = ansi(se + lay['DIALOG_ROW_IN_PANEL'])
    dialog_col = ansi(lay['dialog_col_0indexed'])

    e_sprite_row = ansi(10)
    e_sprite_col = ansi(lay['enemy_col'])
    p_sprite_row = ansi(PLAYER_V_OFFSET)
    p_sprite_col = ansi(lay['e_info_col'])

    lines = []
    def L(s=''):
        lines.append(s)

    L('/* Auto-generated by gen_scene.py -- do not edit */')
    L('#ifndef SCENE_POS_H')
    L('#define SCENE_POS_H')
    L()
    L('#define BAR_W 72   /* HP bar fill width in display cols */')
    L(f'#define INFO_INNER_W {iw}')
    L(f'#define BLOCK_ROWS   {BLOCK_ROWS}   /* pixel-font height (smblock) */')
    L()
    L('/* HP bar content rows (3 rows of filled/empty blocks) */')
    L(f'#define E_HP_BAR_ROW {e_hp_bar_row}')
    L(f'#define E_HP_BAR_COL {e_hp_bar_col}')
    L(f'#define P_HP_BAR_ROW {p_hp_bar_row}')
    L(f'#define P_HP_BAR_COL {p_hp_bar_col}')
    L()
    L('/* HP number text: BLOCK_ROWS-row pixel font, right-aligned */')
    L(f'#define E_HP_NUM_ROW   {e_hp_num_row}')
    L(f'#define E_HP_NUM_RIGHT {e_hp_num_right}  /* ANSI col of rightmost char */')
    L(f'#define P_HP_NUM_ROW   {p_hp_num_row}')
    L(f'#define P_HP_NUM_RIGHT {p_hp_num_right}')
    L()
    L('/* Move cursor positions (ANSI row/col of each move\'s top-left cursor glyph) */')
    L(f'#define MOVE0_ROW {move0_row}')
    L(f'#define MOVE0_COL {move0_col}')
    L(f'#define MOVE1_ROW {move1_row}')
    L(f'#define MOVE1_COL {move1_col}')
    L(f'#define MOVE2_ROW {move2_row}')
    L(f'#define MOVE2_COL {move2_col}')
    L(f'#define MOVE3_ROW {move3_row}')
    L(f'#define MOVE3_COL {move3_col}')
    L()
    L(f'/* Dialog content area (top-left of the {2*BLOCK_ROWS+1}-row writable text region) */')
    L(f'#define DIALOG_ROW  {dialog_row}')
    L(f'#define DIALOG_COL  {dialog_col}')
    L(f'#define DIALOG_ROWS {2*BLOCK_ROWS + 1}   /* {BLOCK_ROWS} + empty + {BLOCK_ROWS} */')
    L(f'#define DIALOG_W    {lay["msg_inner"]}   /* inner width to blank before writing */')
    L()
    L('/* Sprite top-left corners */')
    L(f'#define E_SPRITE_ROW {e_sprite_row}')
    L(f'#define E_SPRITE_COL {e_sprite_col}')
    L(f'#define P_SPRITE_ROW {p_sprite_row}')
    L(f'#define P_SPRITE_COL {p_sprite_col}')
    L()

    L('/* HP bar fill characters (UTF-8 bytes for block-element codepoints) */')
    L(r'#define BL_FULL  "\xe2\x96\x88"   /* full block */')
    L(r'#define BL_LIGHT "\xe2\x96\x91"   /* light shade */')
    L()

    L('/* Move-cursor glyph strips (BLOCK_ROWS rows; overlay the "  " prefix in MLBL_*) */')
    def emit_cursor(varname, text):
        rows = _render_text(text)
        L(f'static const char * const {varname}[BLOCK_ROWS] = {{')
        for r in rows:
            L(f'    "{_encode_line(r)}",')
        L('};')
        L()

    emit_cursor('CURSOR_SEL',   '> ')
    emit_cursor('CURSOR_EMPTY', '  ')

    HP_NUM_FIXED_W   = 5 * BLOCK_COLS
    e_hp_num_left    = e_hp_num_right - HP_NUM_FIXED_W + 1
    p_hp_num_left    = p_hp_num_right - HP_NUM_FIXED_W + 1

    L(f'/* Left edge of the fixed-width HP-number rendering ({HP_NUM_FIXED_W} display cols wide) */')
    L(f'#define E_HP_NUM_LEFT  {e_hp_num_left}')
    L(f'#define P_HP_NUM_LEFT  {p_hp_num_left}')
    L()

    def emit_hp_table(varname, max_hp):
        L(f'static const char * const {varname}[{max_hp + 1}][BLOCK_ROWS] = {{')
        for hp in range(max_hp + 1):
            text = f'{hp}/{max_hp}'.rjust(5)
            rows = _render_text(text)
            L(f'    /* hp = {hp} */ {{')
            for r in rows:
                L(f'        "{_encode_line(r)}",')
            L('    },')
        L('};')
        L()

    # When both sides share the same max HP, the per-side tables are byte
    # identical — emit a single underlying table and alias the per-side names
    # to it. If they ever diverge again, fall back to two real tables.
    if PLAYER_MAX == ENEMY_MAX:
        emit_hp_table('HP_STRINGS', PLAYER_MAX)
        L('#define E_HP_STRINGS HP_STRINGS')
        L('#define P_HP_STRINGS HP_STRINGS')
        L()
    else:
        emit_hp_table('E_HP_STRINGS', ENEMY_MAX)
        emit_hp_table('P_HP_STRINGS', PLAYER_MAX)

    def emit_dialog(varname, line1, line2=''):
        r1 = _render_text(line1)
        r2 = _render_text(line2) if line2 else [''] * BLOCK_ROWS
        rows = r1 + [''] + r2
        L(f'static const char * const {varname}[] = {{')
        for r in rows:
            encoded = _encode_line('  ' + r) if r else ''
            L(f'    "{encoded}",')
        L('    0')
        L('};')
        L()

    emit_dialog('DIALOG_IDLE',        'WHAT WILL',      'SQUIRTLE DO?')
    emit_dialog('DIALOG_CHOOSE',      'CHOOSE A',       'MOVE!')
    emit_dialog('DIALOG_SQURT_ATK',   'SQUIRTLE USED',  'WATER GUN!')
    emit_dialog('DIALOG_TAIL_WHIP',   'SQUIRTLE USED',  'TAIL WHIP!')
    emit_dialog('DIALOG_TACKLE',      'SQUIRTLE USED',  'TACKLE!')
    emit_dialog('DIALOG_GROWL',       'SQUIRTLE USED',  'GROWL!')
    emit_dialog('DIALOG_DEF_DROP',    'ENEMY DEF',      'FELL!')
    emit_dialog('DIALOG_ATK_DROP',    'ENEMY ATK',      'FELL!')
    emit_dialog('DIALOG_BULB_ATK',    'BULBASAUR USED', 'VINE WHIP!')
    emit_dialog('DIALOG_SQURT_FAINT', 'SQUIRTLE',       'FAINTED!')
    emit_dialog('DIALOG_BULB_FAINT',  'BULBASAUR',      'FAINTED!')
    emit_dialog('DIALOG_WIN',         'YOU WIN!',        '')
    emit_dialog('DIALOG_LOSE',        'YOU LOSE!',       '')

    col_w = lay['col_w']
    L(f'#define MOVE_LABEL_W {col_w}   /* display cols per move slot */')
    L()

    def emit_move_label(varname, text):
        rows = _render_text('  ' + text)
        L(f'static const char * const {varname}[] = {{')
        for r in rows:
            padded = r.ljust(col_w)
            L(f'    "{_encode_line(padded)}",')
        L('    0')
        L('};')
        L()

    emit_move_label('MLBL_FIGHT',     'FIGHT')
    emit_move_label('MLBL_BAG',       'BAG')
    emit_move_label('MLBL_POKEMON',   'POKEMON')
    emit_move_label('MLBL_RUN',       'RUN')
    emit_move_label('MLBL_WATER_GUN', 'WATER GUN')
    emit_move_label('MLBL_TAIL_WHIP', 'TAIL WHIP')
    emit_move_label('MLBL_TACKLE',    'TACKLE')
    emit_move_label('MLBL_GROWL',     'GROWL')

    L('#endif /* SCENE_POS_H */')

    with open(outpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'Written {outpath}')


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    emit_scene_header(os.path.join(PROJECT_DIR, 'scene_data.h'))
    lay = compute_layout()
    emit_pos_header(lay, os.path.join(PROJECT_DIR, 'scene_pos.h'))
    print('Done.')
