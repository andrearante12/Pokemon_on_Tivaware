#ifndef PLAYLIST_H
#define PLAYLIST_H

#include <stdint.h>
#include "notes.h"
#include "track1.h"
#include "track2.h"
#include "track3.h"
#include "track4.h"

typedef struct {
    const uint8_t *seq;     /* (beat, len) byte pairs */
    uint32_t       len;     /* number of pairs        */
    uint32_t       tempo;   /* milliseconds per len   */
} track_t;

static const track_t PLAYLIST[] = {
    { track1, TRACK1_LEN, TRACK1_TEMPO },
    { track2, TRACK2_LEN, TRACK2_TEMPO },
    { track3, TRACK3_LEN, TRACK3_TEMPO },
    { track4, TRACK4_LEN, TRACK4_TEMPO },
};
#define PLAYLIST_LEN 4

#endif /* PLAYLIST_H */
