#pragma once
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool valid, has_temperature, has_nvs, has_rssi;
    int battery, voltage, rssi, reset_reason;
    float temperature;
    uint32_t revision, cores, cpu_mhz, flash_size, psram_size;
    uint32_t heap_total, heap_free, heap_min, heap_largest;
    uint32_t app_size, app_capacity, nvs_used, nvs_free, nvs_total, tasks;
    int64_t sampled_us;
    char version[32], idf[32], elf[65], profile[8];
} cp_device_info_t;

// One UI worker owns hardware sampling, before acquiring the LVGL lock.
// Cache copies are synchronized; the physical transport only serializes them.
void cp_device_update(void);
void cp_device_snapshot(cp_device_info_t *info);
void cp_device_text(const cp_device_info_t *info, int64_t now_us, char out[384]);
// Shared status-bar color; invalid readings use a neutral gray.
uint32_t cp_battery_color(int percent);
// Read-only commands received through an existing authenticated card connection.
bool cp_device_diagnostic(const cp_device_info_t *info, const char *name, int64_t now_us, char out[384]);
// USB/BLE worker only; no network listener or Wi-Fi telemetry.
bool cp_device_json(char *out, size_t capacity);
