#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CP_BATTERY_LOG_CAPACITY 192
#define CP_BATTERY_LOG_MAGIC 0x43504231u
#define CP_BATTERY_UPLOAD_COUNT 16

typedef struct {
    uint32_t sequence;
    uint32_t utc_s;       // Zero when no Mac clock sync has occurred this boot.
    uint32_t uptime_s;
    int16_t voltage_mv;   // -1 means the gauge read failed.
    int8_t percent;       // -1 means the gauge read failed.
    uint8_t flags;        // Reserved for later protocol versions.
} cp_battery_sample_t;

typedef struct {
    uint32_t magic;
    uint32_t log_id;
    uint32_t next_sequence;
    uint16_t count;
    uint16_t next_index;
    cp_battery_sample_t samples[CP_BATTERY_LOG_CAPACITY];
} cp_battery_log_t;

void cp_battery_log_init(cp_battery_log_t *log, uint32_t log_id);
bool cp_battery_log_valid(const cp_battery_log_t *log);
bool cp_battery_log_due(const cp_battery_log_t *log, uint32_t uptime_s, int percent);
void cp_battery_log_add(cp_battery_log_t *log, uint32_t utc_s, uint32_t uptime_s,
                        int percent, int voltage_mv);
bool cp_battery_log_at(const cp_battery_log_t *log, unsigned ordinal, cp_battery_sample_t *sample);
unsigned cp_battery_log_page(const cp_battery_log_t *log, uint32_t after,
                             cp_battery_sample_t out[CP_BATTERY_UPLOAD_COUNT]);
int cp_battery_log_packet(const cp_battery_sample_t *samples, unsigned count,
                          const char *identity, uint32_t log_id, bool healthy,
                          char *out, size_t capacity);
int cp_battery_log_line(const cp_battery_log_t *log, unsigned ordinal, char *out, size_t capacity);
