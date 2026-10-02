#pragma once
#include <stddef.h>
#include <stdint.h>
// Independent IMA block: sample count u16, predictor i16, initial index u8,
// reserved zero u8, then low-nibble-first codes (includes code for each sample).
// Independent blocks keep packet loss from corrupting later recordings.
size_t cp_adpcm_encode(const int16_t *samples, size_t count, uint8_t *out, size_t capacity);
