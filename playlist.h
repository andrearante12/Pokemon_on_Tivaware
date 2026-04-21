#ifndef PLAYLIST_H
#define PLAYLIST_H

#include "track1.h"
#include "track2.h"
#include "track3.h"
#include "track4.h"

static const note_t * const PLAYLIST[] = {
    SONG_track1,
    SONG_track2,
    SONG_track3,
    SONG_track4,
};
#define PLAYLIST_LEN 4

#endif /* PLAYLIST_H */
