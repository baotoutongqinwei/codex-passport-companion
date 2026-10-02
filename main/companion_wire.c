#include "companion_wire.h"
#include <string.h>

static uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }
static uint32_t u32(const uint8_t *p) { return (uint32_t)u16(p) | ((uint32_t)u16(p+2) << 16); }
static void put16(uint8_t *p, uint16_t n) { p[0] = n; p[1] = n >> 8; }
static void put32(uint8_t *p, uint32_t n) { put16(p, n); put16(p+2, n >> 16); }

uint32_t cp_wire_crc32(const uint8_t *data, size_t length) {
    uint32_t crc = UINT32_MAX;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ (0xedb88320U & (0U-(crc & 1U)));
    }
    return ~crc;
}

size_t cp_wire_encode(uint8_t *out, size_t capacity, uint32_t id, uint16_t status,
                      const char *path, const void *body, size_t length) {
    size_t plen = path ? strlen(path) : 0;
    size_t total = CP_WIRE_HEADER + plen + length + 4;
    if (plen > CP_WIRE_PATH_MAX || length > CP_WIRE_BODY_MAX || total > capacity ||
        (!body && length) || (status && plen)) return 0;
    memcpy(out, "CPv1", 4); put32(out+4, id); put16(out+8, status);
    put16(out+10, plen); put32(out+12, length);
    if (plen) memcpy(out+16, path, plen);
    if (length) memcpy(out+16+plen, body, length);
    put32(out+total-4, cp_wire_crc32(out, total-4));
    return total;
}

bool cp_wire_feed(cp_wire_parser_t *p, uint8_t byte, cp_wire_frame_t *frame) {
    if (p->expected && p->used == p->expected) p->used = p->expected = 0;
    if (p->used < 4 && byte != (uint8_t)"CPv1"[p->used]) {
        p->used = byte == 'C' ? 1 : 0;
        p->bytes[0] = 'C'; p->expected = 0;
        return false;
    }
    p->bytes[p->used++] = byte;
    if (p->used == CP_WIRE_HEADER) {
        size_t path = u16(p->bytes+10), body = u32(p->bytes+12);
        if (path > CP_WIRE_PATH_MAX || body > CP_WIRE_BODY_MAX ||
            (u16(p->bytes+8) && path)) { p->used = p->expected = 0; return false; }
        p->expected = CP_WIRE_HEADER + path + body + 4;
    }
    if (!p->expected || p->used < p->expected) return false;
    if (u32(p->bytes+p->used-4) != cp_wire_crc32(p->bytes, p->used-4)) {
        p->used = p->expected = 0; return false;
    }
    *frame = (cp_wire_frame_t) { .id=u32(p->bytes+4), .status=u16(p->bytes+8),
        .path_size=u16(p->bytes+10), .body_size=u32(p->bytes+12), .path=p->bytes+16 };
    frame->body = frame->path + frame->path_size;
    return true;
}
