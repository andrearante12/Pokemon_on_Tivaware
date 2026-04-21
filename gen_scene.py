#!/usr/bin/env python3
"""
gen_scene.py — generates scene_data.h and scene_pos.h from the Python battle scene.
Run from final_project/ directory:
    python3 gen_scene.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from display import (PLAYER_V_OFFSET, SPRITE_H_GAP,
                     _tight, _render_text, _enemy_info, _player_info, _bottom_panel,
                     compose_battle)
import assets

# ── Battle parameters (fixed for Phase 1 display) ───────────────────────────
PLAYER_NAME  = "squirtle"
ENEMY_NAME   = "bulbasaur"
PLAYER_HP    = 20
PLAYER_MAX   = 20
PLAYER_LEVEL = 5
ENEMY_HP     = 45
ENEMY_MAX    = 45
ENEMY_LEVEL  = 5
MOVES        = ["FIGHT", "BAG", "POKEMON", "RUN"]


# ── Encoding helper (from convert_sprites.py) ────────────────────────────────
def _encode_line(line):
    """Encode a Unicode string as the body of a C string literal (no outer quotes)."""
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


# ── Layout computation ────────────────────────────────────────────────────────
def compute_layout():
    """Replicate compose_battle() math and return exact position info."""
    player = _tight(assets.lines(PLAYER_NAME))
    enemy  = _tight(assets.lines(ENEMY_NAME))

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
    panel    = _bottom_panel(PLAYER_NAME, MOVES, 0, panel_w)

    half      = panel_w // 2
    msg_inner = half - 4
    mov_inner = panel_w - half - 4
    col_w     = mov_inner // 2

    panel_col = e_info_col - 10

    # Info box structure (rows within box, 0-indexed):
    #   0        : top border
    #   1        : empty
    #   2–6      : name+level pixel font (5 rows)
    #   7        : empty
    #   8        : HP bar top border
    #   9–11     : HP bar content (3 rows of █/░)
    #   12       : HP bar bottom border
    #   13       : empty
    #   14–18    : HP number pixel font (5 rows, right-aligned)
    #   19       : empty
    #   20       : bottom border

    # HP bar content column within info box row:
    #   '| ' (2) + HP label (11 = H5+gap1+P5) + '  ' (2) + '| ' (2) = 17 from box left
    HP_LABEL_W = len(_render_text('HP')[0])   # = 11
    hp_bar_col_in_box = 2 + HP_LABEL_W + 2 + 2   # = 17

    # Info inner width (from box content)
    info_inner_w = len(e_info[1]) - 4   # strip '| ' and ' |'

    # Move box (right half of panel):
    # The left box occupies 'half' display cols (border+inner+border = msg_inner+4 = half).
    # Move box starts at panel_col + half.
    # Move box content: '| '(2) + pad '  '(2) = 4 offset from move box left edge.
    move_box_left_col = panel_col + half   # 0-indexed column where move box starts

    # Move font rows within panel (0-indexed from panel top):
    #   Panel row 0 : top border
    #   Panel rows 1-2 : empty (mov_rows[0], mov_rows[1])
    #   Panel rows 3-7 : first move row font (FIGHT/BAG)
    #   Panel row 8   : empty
    #   Panel rows 9-13: second move row font (POKEMON/RUN)
    #   Panel rows 14-15: empty
    #   Panel row 16  : bottom border
    MOVE_ROW_TOP_IN_PANEL    = 3   # top of FIGHT/BAG font rows
    MOVE_ROW_BOTTOM_IN_PANEL = 9   # top of POKEMON/RUN font rows

    # Column offsets within moves box for each column (0-indexed):
    # '| '(2) + pad '  '(2) = 4 offset from move box left
    move_content_col_0 = move_box_left_col + 4             # left column (FIGHT, POKEMON)
    move_content_col_1 = move_box_left_col + 4 + col_w     # right column (BAG, RUN)

    # Dialog content start within panel (0-indexed from panel top):
    # Panel row 0: border, rows 1-2: empty → first text at row 3
    DIALOG_ROW_IN_PANEL = 3
    # Column: panel_col + '| '(2) + pad '  '(2) = panel_col + 4
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
    # Convert 0-indexed canvas positions to ANSI 1-indexed
    def ansi(r, c=None):
        if c is None:
            return r + 1
        return (r + 1, c + 1)

    e_r, e_c   = ansi(lay['e_info_row'], lay['e_info_col'])
    p_r, p_c   = ansi(lay['p_stamp_row'], lay['p_info_col'])
    se         = lay['sprite_end']
    iw         = lay['info_inner_w']
    hb_off     = lay['hp_bar_col_in_box']

    # HP bar content: info box rows 9-11 (0-indexed), col = box_left + hp_bar_col_in_box
    e_hp_bar_row = e_r + 9    # ANSI
    e_hp_bar_col = e_c + hb_off
    p_hp_bar_row = p_r + 9
    p_hp_bar_col = p_c + hb_off

    # HP number: info box rows 14-18, right-aligned — right edge = box_left+2+inner_w
    e_hp_num_row   = e_r + 14
    e_hp_num_right = e_c + 2 + iw     # ANSI col of last number char
    p_hp_num_row   = p_r + 14
    p_hp_num_right = p_c + 2 + iw

    # Move cursors: ANSI row/col of each move's top-left cursor glyph
    move0_row = ansi(se + lay['MOVE_ROW_TOP'])
    move1_row = move0_row
    move2_row = ansi(se + lay['MOVE_ROW_BOT'])
    move3_row = move2_row

    move0_col = ansi(lay['move_content_col_0'])
    move1_col = ansi(lay['move_content_col_1'])
    move2_col = move0_col
    move3_col = move1_col

    # Dialog content area
    dialog_row = ansi(se + lay['DIALOG_ROW_IN_PANEL'])
    dialog_col = ansi(lay['dialog_col_0indexed'])

    # Sprite corners
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
    L()
    L('/* HP bar content rows (3 rows of filled/empty blocks) */')
    L(f'#define E_HP_BAR_ROW {e_hp_bar_row}')
    L(f'#define E_HP_BAR_COL {e_hp_bar_col}')
    L(f'#define P_HP_BAR_ROW {p_hp_bar_row}')
    L(f'#define P_HP_BAR_COL {p_hp_bar_col}')
    L()
    L('/* HP number text: 5-row pixel font, right-aligned */')
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
    L('/* Dialog content area (top-left of the 11-row writable text region) */')
    L(f'#define DIALOG_ROW  {dialog_row}')
    L(f'#define DIALOG_COL  {dialog_col}')
    L(f'#define DIALOG_ROWS 11   /* 5 + empty + 5 */')
    L(f'#define DIALOG_W    {lay["msg_inner"]}   /* inner width to blank before writing */')
    L()
    L('/* Sprite top-left corners */')
    L(f'#define E_SPRITE_ROW {e_sprite_row}')
    L(f'#define E_SPRITE_COL {e_sprite_col}')
    L(f'#define P_SPRITE_ROW {p_sprite_row}')
    L(f'#define P_SPRITE_COL {p_sprite_col}')
    L()

    # Pre-render dialog message blocks (11 rows each: 5 + empty + 5)
    def emit_dialog(varname, line1, line2=''):
        r1 = _render_text(line1)
        r2 = _render_text(line2) if line2 else [''] * 5
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

    # Move label arrays: each slot's full 5-row text, padded to col_w so writing
    # one label always blanks whatever was there before (even a wider label).
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


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    emit_scene_header(os.path.join(base, 'scene_data.h'))
    lay = compute_layout()
    emit_pos_header(lay, os.path.join(base, 'scene_pos.h'))
    print('Done.')
