#pragma once
#include "companion_model.h"
#include "esp_err.h"

typedef struct {
    char ssid[33], password[65], url[128], token[65], cert[2048];
    int64_t epoch;
} cp_config_t;

typedef enum { CP_IDLE, CP_STARTING, CP_RECORDING, CP_TRANSCRIBING, CP_REVIEW, CP_SENDING } cp_mode_t;

typedef struct {
    cp_view_t view;
    bool configured, wifi, bridge, clock_synced;
    int battery;
    cp_mode_t mode;
    unsigned recorded_ms;
    char message[180];
} cp_state_t;

// The app owns all tasks for its lifetime. No UI screen pointers leave the UI module.
esp_err_t cp_config_load(cp_config_t *config);
void cp_config_task(void *arg);
void cp_runtime_start(const cp_config_t *config);
void cp_state_snapshot(cp_state_t *state);
void cp_select(const char *thread, const char *cursor, int page);
void cp_record_start(void);
void cp_record_stop(void);
void cp_send_draft(void);
void cp_cancel(void);
void cp_ui_run(void);
