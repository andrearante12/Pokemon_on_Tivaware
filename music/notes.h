#ifndef NOTES_H
#define NOTES_H

#include <stdint.h>

#define Fcpu 40000000

/* Musical note → index into notes[].  S = silence (rest). */
#define S    0
#define C4   1
#define Db4  2
#define D4   3
#define Eb4  4
#define E4   5
#define F4   6
#define Gb4  7
#define G4   8
#define Ab4  9
#define A4  10
#define Bb4 11
#define B4  12
#define C5  13
#define Db5 14
#define D5  15
#define Eb5 16
#define E5  17
#define F5  18
#define Gb5 19
#define G5  20
#define Ab5 21
#define A5  22
#define Bb5 23
#define B5  24
#define C6  25
#define Db6 26
#define D6  27
#define Eb6 28
#define E6  29
#define F6  30
#define Gb6 31
#define G6  32
#define Ab6 33
#define A6  34
#define Bb6 35
#define B6  36
#define C7  37
#define Gb7 38
#define G7  39
#define A7  40
#define B7  41
#define C8  42

#define C   C5
#define Db  Db5
#define D   D5
#define Eb  Eb5
#define E   E5
#define F   F5
#define Gb  Gb5
#define G   G5
#define A   A5
#define Bb  Bb5
#define B   B5

/* Half-period reload values for Fcpu = 40 MHz (matches the example). */
static const uint32_t notes[] = {
    76336, 72202, 68027, 64309, 60606, 57307, 54054, 51020,
    48193, 45455, 42918, 40486, 38241, 36101, 34072, 32154,
    30349, 28634, 27027, 25511, 24079, 22727, 21452, 20248,
    19111, 18039, 17026, 16071, 15169, 14317, 13514, 12755,
    12039, 11364, 10726, 10124, 9556, 9019, 8513, 8035,
    7584, 7159
};

#endif /* NOTES_H */
