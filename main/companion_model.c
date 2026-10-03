#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include "companion_model.h"
#include <string.h>
#include <ctype.h>
#include <stdio.h>
#include <time.h>

bool cp_telemetry_allowed(cp_mode_t mode) {
    return mode == CP_IDLE || mode == CP_REVIEW || mode == CP_TRANSCRIBING;
}

bool cp_screen_should_dim(cp_mode_t mode, int64_t inactive_us) {
    return (mode == CP_IDLE || mode == CP_REVIEW) && inactive_us >= 60000000;
}

size_t cp_utf8_copy(char *out, size_t capacity, const char *text) {
    if (!capacity) return 0;
    size_t used = 0;
    const unsigned char *p = (const unsigned char *)(text ? text : "");
    while (*p) {
        size_t n = *p < 0x80 ? 1 : (*p >= 0xC2 && *p <= 0xDF ? 2 :
                   (*p >= 0xE0 && *p <= 0xEF ? 3 : (*p >= 0xF0 && *p <= 0xF4 ? 4 : 0)));
        bool valid = n != 0;
        for (size_t i = 1; valid && i < n; ++i) if (!p[i] || (p[i] & 0xC0) != 0x80) valid = false;
        if (valid && n == 3 && ((*p == 0xE0 && p[1] < 0xA0) || (*p == 0xED && p[1] >= 0xA0))) valid = false;
        if (valid && n == 4 && ((*p == 0xF0 && p[1] < 0x90) || (*p == 0xF4 && p[1] >= 0x90))) valid = false;
        if (!valid) {
            if (used + 1 >= capacity) break;
            out[used++] = '?'; ++p; continue;
        }
        if (used + n >= capacity) break;
        memcpy(out + used, p, n); used += n; p += n;
    }
    out[used] = 0;
    return used;
}

bool cp_url_encode(char *out, size_t capacity, const char *text) {
    static const char hex[] = "0123456789ABCDEF";
    size_t n = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        bool safe = (*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
                    (*p >= '0' && *p <= '9') || strchr("-._~", *p);
        size_t needed = safe ? 1 : 3;
        if (n + needed >= capacity) { if (capacity) out[0] = 0; return false; }
        if (safe) out[n++] = (char)*p;
        else { out[n++] = '%'; out[n++] = hex[*p >> 4]; out[n++] = hex[*p & 15]; }
    }
    if (n >= capacity) return false;
    out[n] = 0;
    return true;
}

bool cp_valid_url(const char *url) {
    if (strncmp(url, "https://", 8) != 0 || strlen(url) >= 120) return false;
    const char *host = url + 8;
    if (!*host) return false;
    for (const char *p = host; *p; ++p) {
        if (!(isalnum((unsigned char)*p) || *p == '.' || *p == '-' || *p == ':')) return false;
    }
    return true;
}

int cp_clamp_page(int page, int count) {
    if (count <= 0) return 0;
    if (page < 0) return count - 1;
    return page >= count ? count - 1 : page;
}

void cp_clock_text(char out[9], int64_t unix_seconds, bool synced) {
    if (!synced || unix_seconds < 0) {
        strcpy(out, "--:--:--");
        return;
    }
    int seconds = (int)((unix_seconds % 86400 + 8*3600) % 86400);
    snprintf(out, 9, "%02d:%02d:%02d", seconds/3600, seconds/60%60, seconds%60);
}

int cp_weekly_window(const cp_view_t *view) {
    for (int i = 0; i < 2; ++i) if (view->windows[i] == 7*24*60) return i;
    return -1;
}

void cp_date_text(char out[17], int64_t unix_seconds) {
    strcpy(out, "--");
    if (unix_seconds <= 0 || unix_seconds > 253402271999LL) return;
    time_t shifted = (time_t)(unix_seconds + 8*3600);
    struct tm date;
    if (!gmtime_r(&shifted, &date) || !strftime(out, 17, "%Y-%m-%d %H:%M", &date)) strcpy(out, "--");
}

unsigned cp_pcm_level(const int16_t *samples, size_t count) {
    if (!count || count > 2048) return 0;
    int32_t sum = 0;
    for (size_t i = 0; i < count; ++i) sum += samples[i];
    int32_t mean = sum / (int32_t)count;
    uint32_t amplitude = 0;
    for (size_t i = 0; i < count; ++i) {
        int32_t delta = (int32_t)samples[i] - mean;
        amplitude += (uint32_t)(delta < 0 ? -delta : delta);
    }
    amplitude /= count;
    static const unsigned thresholds[] = {32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384};
    unsigned level = 0;
    for (unsigned i = 0; i < 10; ++i) if (amplitude >= thresholds[i]) level = (i+1)*10;
    return level;
}

int16_t cp_cue_sample(unsigned sample, unsigned count, unsigned frequency) {
    static const int16_t sine[] = {0, 627, 1159, 1514, 1638, 1514, 1159, 627,
                                   0, -627, -1159, -1514, -1638, -1514, -1159, -627};
    if (sample >= count || !frequency || frequency > 2000) return 0;
    unsigned fade = sample < 160 ? sample : count-1-sample < 160 ? count-1-sample : 160;
    return (int16_t)(sine[(sample*frequency/1000)%16] * (int)fade / 160);
}
