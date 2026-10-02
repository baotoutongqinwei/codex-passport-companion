#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CP_WIRE_HEADER 16
#define CP_WIRE_PATH_MAX 1536
#define CP_WIRE_BODY_MAX 8192
#define CP_WIRE_MAX (CP_WIRE_HEADER + CP_WIRE_PATH_MAX + CP_WIRE_BODY_MAX + 4)

// CPv1, request id u32, status u16 (0=request), path length u16,
// body length u32, path UTF-8, body bytes, IEEE CRC32. Integers are little endian.
typedef struct {
    uint8_t bytes[CP_WIRE_MAX];
    size_t used, expected;
} cp_wire_parser_t;
typedef struct {
    uint32_t id;
    uint16_t status, path_size;
    uint32_t body_size;
    const uint8_t *path, *body;
} cp_wire_frame_t;

uint32_t cp_wire_crc32(const uint8_t *data, size_t length);
size_t cp_wire_encode(uint8_t *out, size_t capacity, uint32_t id, uint16_t status,
                      const char *path, const void *body, size_t length);
// Returns true for one valid frame; pointers remain valid until the next byte.
// Invalid input is bounded and discarded. Callers apply their own timeout.
bool cp_wire_feed(cp_wire_parser_t *parser, uint8_t byte, cp_wire_frame_t *frame);
