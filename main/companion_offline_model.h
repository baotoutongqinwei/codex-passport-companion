#pragma once
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    bool running, complete, rest;
    int64_t started_ms, accumulated_ms;
    unsigned cycles;
} cp_focus_t;
typedef struct { bool running; int64_t started_ms, accumulated_ms; } cp_stopwatch_t;
void cp_focus_toggle(cp_focus_t *focus, int64_t now_ms);
int64_t cp_focus_remaining(cp_focus_t *focus, int64_t now_ms);
void cp_stopwatch_toggle(cp_stopwatch_t *watch, int64_t now_ms);
int64_t cp_stopwatch_elapsed(const cp_stopwatch_t *watch, int64_t now_ms);
void cp_offline_clock(char out[9], int seconds, int64_t since_ms, int64_t now_ms);
