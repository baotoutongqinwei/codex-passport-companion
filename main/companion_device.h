#pragma once
#include <stddef.h>
#include <stdbool.h>
// USB/BLE worker only while idle; no network listener or Wi-Fi telemetry.
bool cp_device_json(char *out, size_t capacity);
