#ifndef MUSIC_NOTES_H
#define MUSIC_NOTES_H

typedef struct { uint32_t freq_hz; uint32_t dur_ms; } note_t;

/* Placeholder melody — replace by running:
 *   python3 midi_to_c.py battle.mid > music_notes.h
 *
 * Simple ascending/descending scale for hardware testing.
 */
static const note_t SONG[] = {
    { 262, 200},  /* C4  */
    { 294, 200},  /* D4  */
    { 330, 200},  /* E4  */
    { 349, 200},  /* F4  */
    { 392, 200},  /* G4  */
    { 440, 200},  /* A4  */
    { 494, 200},  /* B4  */
    { 523, 400},  /* C5  */
    {   0, 200},  /* rest */
    { 523, 200},  /* C5  */
    { 494, 200},  /* B4  */
    { 440, 200},  /* A4  */
    { 392, 200},  /* G4  */
    { 349, 200},  /* F4  */
    { 330, 200},  /* E4  */
    { 294, 200},  /* D4  */
    { 262, 400},  /* C4  */
    {   0, 400},  /* rest */
    {0, 0}        /* sentinel: loops */
};

#endif /* MUSIC_NOTES_H */
