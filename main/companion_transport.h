#pragma once
#include "companion.h"
#include <stddef.h>
#include <stdint.h>

esp_err_t cp_transport_start(const cp_config_t *config);
bool cp_transport_connected(void);
void cp_transport_poll(void);
bool cp_transport_audio_ready(void);
bool cp_transport_rssi(int *dbm); // Physical transports only; false for USB.
// Only the runtime worker calls request; implementations own framing and I/O.
bool cp_transport_request(const char *path, const void *body, size_t size,
                          bool audio, char *out, size_t capacity, int *status);
const char *cp_transport_name(void);
const char *cp_transport_help(void);
int cp_transport_passkey(void); // -1 except during authenticated BLE pairing.
void cp_transport_forget_bonds(void); // Physical long press in BLE settings only.

// The framed USB/BLE implementations share one bounded request engine.
esp_err_t cp_link_init(void);
void cp_link_receive(const uint8_t *data, size_t size);
void cp_link_disconnected(void);
bool cp_link_write(const uint8_t *data, size_t size);
