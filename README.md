# ECE3525 Final Project — Pokémon Battle Game

## Running

1. Flash the board via CCS
2. Open a terminal and connect to the serial port:
   ```
   screen /dev/cu.usbmodem0E23C99F1 115200

   or 

   
   ls /dev/cu.usbmodem*
   screen -X -S 54468.ttys000.Andres-Air quit && screen /dev/cu.usbmodem0E23C99F1 115200                                                                                                                             

   ```
3. Press the **RESET** button on the board to start the game

To exit screen: `Ctrl+A` then `K`

## Troubleshooting: port busy / old sessions
If `screen` says the port is busy, a previous session is still holding it. List and kill all old sessions:
```
screen -list
screen -X -S <session-name> quit
```

## Build-time scripts

All Python build tooling lives in `scripts/`. Run from the project root:

```
python3 scripts/gen_scene.py             # regenerate scene_data.h + scene_pos.h
python3 scripts/convert_sprites.py > sprites.h   # regenerate sprite arrays
python3 scripts/midi_to_c.py music/trackN.mid > music/trackN.h
```

`scripts/font_small_block.py` is the smblock pixel font used by `gen_scene.py`;
running it directly prints a self-test of every defined glyph.

## Music
Tracks are stored in `music/`. To convert a new MIDI file:
```
pip install mido
python3 scripts/midi_to_c.py music/trackN.mid > music/trackN.h
```
Update `music/playlist.h` to include the new track.

## Producing a `.bin` for flash programming

CCS only emits a `.out` by default. To produce a standalone `Debug/final_project.bin`:

1. In CCS, right-click the project → **Properties**
2. **Build → Steps → Post-build steps** → paste:
   ```
   "${CCS_INSTALL_ROOT}/utils/tiobj2bin/tiobj2bin" "${BuildArtifactFileName}" "${BuildArtifactFileBaseName}.bin" "${CG_TOOL_ROOT}/bin/armofd" "${CG_TOOL_ROOT}/bin/armhex" "${CCS_INSTALL_ROOT}/utils/tiobj2bin/mkhex4bin"
   ```
3. Apply, then **Project → Rebuild Project**
4. `Debug/final_project.bin` should now exist

## Flashing the `.bin` on macOS (UniFlash)

LM Flash Programmer is Windows-only. On macOS, use TI **UniFlash** (the cross-platform replacement):

1. Download from https://www.ti.com/tool/UNIFLASH
2. Open UniFlash → New Configuration → Device: **TM4C123GH6PM**, Connection: **Stellaris In-Circuit Debug Interface** → Start
3. Browse to `Debug/final_project.bin`, click **Load Image**
4. Press RESET on the board — the program runs standalone (no CCS attached)
