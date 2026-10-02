#include "companion.h"
#include "cJSON.h"
#include "nvs.h"
#include "esp_system.h"
#include "driver/usb_serial_jtag.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static bool field(cJSON *root, const char *key, char *out, size_t capacity) {
    cJSON *value = cJSON_GetObjectItemCaseSensitive(root, key);
    if (!cJSON_IsString(value) || strlen(value->valuestring) >= capacity) return false;
    strcpy(out, value->valuestring);
    return true;
}

esp_err_t cp_config_load(cp_config_t *config) {
    nvs_handle_t handle;
    esp_err_t result = nvs_open("codex_passport", NVS_READONLY, &handle);
    if (result != ESP_OK) return result;
    size_t length = sizeof(*config);
    result = nvs_get_blob(handle, "config_v1", config, &length);
    nvs_close(handle);
    if (result != ESP_OK || length != sizeof(*config)) return ESP_ERR_NOT_FOUND;
    // Reject malformed or unterminated saved data before using it in TLS/Wi-Fi.
    if (!memchr(config->ssid, 0, sizeof(config->ssid)) ||
        !memchr(config->password, 0, sizeof(config->password)) ||
        !memchr(config->url, 0, sizeof(config->url)) ||
        !memchr(config->token, 0, sizeof(config->token)) ||
        !memchr(config->cert, 0, sizeof(config->cert)) || !cp_valid_url(config->url)) return ESP_ERR_INVALID_ARG;
    return ESP_OK;
}

static bool save_config(const char *line) {
    cJSON *root = cJSON_Parse(line);
    if (!root) return false;
    cp_config_t *config = calloc(1, sizeof(*config));
    cJSON *cmd = cJSON_GetObjectItemCaseSensitive(root, "cmd");
    cJSON *epoch = cJSON_GetObjectItemCaseSensitive(root, "epoch");
    bool valid = config && cJSON_IsString(cmd) && strcmp(cmd->valuestring, "configure") == 0 &&
        field(root, "ssid", config->ssid, sizeof(config->ssid)) && config->ssid[0] &&
        field(root, "password", config->password, sizeof(config->password)) && strlen(config->password) >= 8 &&
        field(root, "url", config->url, sizeof(config->url)) && cp_valid_url(config->url) &&
        field(root, "token", config->token, sizeof(config->token)) && strlen(config->token) == 64 &&
        field(root, "cert", config->cert, sizeof(config->cert)) &&
        strstr(config->cert, "-----BEGIN CERTIFICATE-----") &&
        cJSON_IsNumber(epoch) && epoch->valuedouble > 1700000000;
    if (valid) {
        config->epoch = (int64_t)epoch->valuedouble;
        nvs_handle_t handle;
        esp_err_t result = nvs_open("codex_passport", NVS_READWRITE, &handle);
        if (result == ESP_OK) {
            result = nvs_set_blob(handle, "config_v1", config, sizeof(*config));
            if (result == ESP_OK) result = nvs_commit(handle);
            nvs_close(handle);
        }
        valid = result == ESP_OK;
    }
    if (config) { memset(config, 0, sizeof(*config)); free(config); }
    cJSON_Delete(root);
    return valid;
}

void cp_config_task(void *arg) {
    (void)arg;
    usb_serial_jtag_driver_config_t options = { .rx_buffer_size = 1024, .tx_buffer_size = 1024 };
    if (usb_serial_jtag_driver_install(&options) != ESP_OK) { vTaskDelete(NULL); return; }
    char *line = malloc(4096);
    if (!line) { vTaskDelete(NULL); return; }
    size_t used = 0;
    bool overflow = false;
    for (;;) {
        char byte;
        if (usb_serial_jtag_read_bytes(&byte, 1, pdMS_TO_TICKS(100)) != 1) continue;
        if (byte == '\n') {
            line[used] = 0;
            bool ok = !overflow && save_config(line);
            memset(line, 0, 4096);
            used = 0; overflow = false;
            const char *answer = ok ? "{\"configured\":true}\n" : "{\"configured\":false}\n";
            usb_serial_jtag_write_bytes(answer, strlen(answer), pdMS_TO_TICKS(1000));
            if (ok) { vTaskDelay(pdMS_TO_TICKS(600)); esp_restart(); }
        } else if (byte != '\r') {
            if (used < 4095 && !overflow) line[used++] = byte;
            else overflow = true;
        }
    }
}
