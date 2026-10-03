#pragma once
#include "companion_battery_log_model.h"
#include <stdbool.h>
#include <stdint.h>

bool cp_battery_log_start(void);
void cp_battery_log_set_epoch(int64_t epoch_ms, int64_t uptime_ms);
bool cp_battery_log_copy(cp_battery_log_t *out);
unsigned cp_battery_log_count(void);
bool cp_battery_log_healthy(void);
void cp_battery_log_set_busy(bool busy);
// Bounded upload page, serialized outside the shared-log critical section.
int cp_battery_log_json(uint32_t after, char *out, size_t capacity,
                        uint32_t *log_id, uint32_t *last_sequence);
