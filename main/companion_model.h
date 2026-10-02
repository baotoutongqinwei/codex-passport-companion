#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CP_THREAD_COUNT 3
#define CP_ID_SIZE 65
#define CP_BODY_SIZE 1804
#define CP_CURSOR_SIZE 385

typedef struct {
    char id[CP_ID_SIZE];
    char title[100];
    char project[64];
    char status[24];
    bool unread;
    int queued;
} cp_thread_t;

typedef struct {
    cp_thread_t threads[CP_THREAD_COUNT];
    int count;
    char next[CP_CURSOR_SIZE];
    char id[CP_ID_SIZE];
    char title[100];
    char body[CP_BODY_SIZE];
    char status[24];
    int page, pages;
    int remaining[2];
    int64_t reset[2];
    int windows[2];
    char credits[25];
    int reset_credit_count;
    bool reset_credit_details_complete;
    int64_t reset_credit_expiry[2];
    int64_t updated;
    char draft_id[CP_ID_SIZE];
    char draft_thread[CP_ID_SIZE];
    char draft_state[24];
    char draft[CP_BODY_SIZE];
    bool asr_ready;
    bool p1;
    bool unread;
    char revision[33];
} cp_view_t;

// Copies whole UTF-8 sequences only, replacing malformed bytes with '?'.
size_t cp_utf8_copy(char *out, size_t capacity, const char *text);
// UTF-8 URI encoding with a strict output bound. False means no request is sent.
bool cp_url_encode(char *out, size_t capacity, const char *text);
bool cp_valid_url(const char *url);
int cp_clamp_page(int page, int count);
// Fixed UTC+8, 24-hour HH:MM:SS; no dependence on the Mac's timezone or DST.
void cp_clock_text(char out[9], int64_t unix_seconds, bool synced);
// Only a genuine seven-day window is used on the quota home page.
int cp_weekly_window(const cp_view_t *view);
// Fixed UTC+8 calendar date and 24-hour time, or "--" if unavailable.
void cp_date_text(char out[17], int64_t unix_seconds);
// Relative microphone activity, not a calibrated sound-pressure reading.
unsigned cp_pcm_level(const int16_t *samples, size_t count);
// Quiet synthesized cue with a short fade, 16 kHz mono. No audio asset allocation.
int16_t cp_cue_sample(unsigned sample, unsigned count, unsigned frequency);
