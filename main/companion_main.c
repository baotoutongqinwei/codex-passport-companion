#include "companion.h"
#include "bsp_i2c.h"
#include "bsp_display.h"
#include "bsp_battery.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdlib.h>
#include "sdkconfig.h"
#if CONFIG_PASSPORT_MODE_OFFLINE
void cp_offline_run(void);
#endif

void app_main(void) {
    // Do not erase existing NVS when initialization fails.
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(bsp_i2c_init());
    ESP_ERROR_CHECK(bsp_display_init());
    ESP_ERROR_CHECK(bsp_lvgl_init() ? ESP_OK : ESP_FAIL);
    if (bsp_battery_init() != ESP_OK) ESP_LOGW("companion", "Battery unavailable");
#if CONFIG_PASSPORT_MODE_OFFLINE
    cp_offline_run();
#else
#if CONFIG_PASSPORT_MODE_WIFI
    cp_config_t *config = calloc(1, sizeof(*config));
    ESP_ERROR_CHECK(config ? ESP_OK : ESP_ERR_NO_MEM);
    bool configured = cp_config_load(config) == ESP_OK;
    cp_runtime_start(configured ? config : NULL);
    free(config);
    ESP_ERROR_CHECK(xTaskCreate(cp_config_task, "cp_setup", 4096, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
#else
    cp_runtime_start(NULL);
#endif
    cp_ui_run();
#endif
}
