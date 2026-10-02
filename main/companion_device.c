#include "companion_device.h"
#include "companion_build.h"
#include "companion_transport.h"
#include "bsp_battery.h"
#include "bsp_temperature.h"
#include "bsp_pins.h"
#include "cJSON.h"
#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_image_format.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>

bool cp_device_json(char *out, size_t capacity) {
    static uint32_t app_size, app_capacity;
    static bool inspected;
    if (!inspected) {
        const esp_partition_t *partition = esp_ota_get_running_partition();
        if (partition) {
            app_capacity = partition->size;
            esp_partition_pos_t position = {.offset=partition->address, .size=partition->size};
            esp_image_metadata_t metadata;
            if (esp_image_get_metadata(&position, &metadata) == ESP_OK) app_size = metadata.image_len;
        }
        inspected = true;
    }
    multi_heap_info_t heap;
    heap_caps_get_info(&heap, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    uint32_t flash_size = 0;
    esp_flash_get_size(NULL, &flash_size);
    int battery = bsp_battery_soc(), voltage = bsp_battery_mv(), rssi;
    float temperature;
    bool has_temperature = bsp_temperature_read(&temperature) == ESP_OK;
    nvs_stats_t nvs;
    bool has_nvs = nvs_get_stats("nvs", &nvs) == ESP_OK;
    const esp_app_desc_t *app = esp_app_get_description();
    char elf[65];
    for (unsigned i=0; i<32; ++i) snprintf(elf+i*2, 3, "%02x", app->app_elf_sha256[i]);
    cJSON *root = cJSON_CreateObject();
    if (!root) return false;
#define NUM(key, value) cJSON_AddNumberToObject(root, key, value)
    NUM("schema", 1);
    cJSON_AddStringToObject(root, "chip", "ESP32-C3");
    cJSON_AddStringToObject(root, "profile", CP_PROFILE);
    cJSON_AddStringToObject(root, "firmware", app->version);
    cJSON_AddStringToObject(root, "elf_sha256", elf);
    cJSON_AddStringToObject(root, "idf", app->idf_ver);
    NUM("revision", chip.revision); NUM("cores", chip.cores);
    NUM("cpu_mhz", CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ);
    NUM("flash_bytes", flash_size);
    NUM("psram_bytes", heap_caps_get_total_size(MALLOC_CAP_SPIRAM));
    NUM("display_width", BSP_LCD_W); NUM("display_height", BSP_LCD_H);
    NUM("uptime_s", esp_timer_get_time()/1000000);
    NUM("reset_reason", esp_reset_reason());
    NUM("heap_total", heap.total_allocated_bytes + heap.total_free_bytes);
    NUM("heap_free", heap.total_free_bytes);
    NUM("heap_min", heap.minimum_free_bytes);
    NUM("heap_largest", heap.largest_free_block);
    NUM("app_used", app_size); NUM("app_capacity", app_capacity);
    if (has_nvs) {
        NUM("nvs_used", nvs.used_entries); NUM("nvs_free", nvs.free_entries);
        NUM("nvs_total", nvs.total_entries);
    }
    if (battery >= 0) NUM("battery_pct", battery);
    if (voltage >= 0) NUM("battery_mv", voltage);
    if (has_temperature) NUM("die_c", temperature);
    if (cp_transport_rssi(&rssi)) NUM("rssi_dbm", rssi);
    NUM("tasks", uxTaskGetNumberOfTasks());
    NUM("network_stack_min", uxTaskGetStackHighWaterMark(NULL));
#undef NUM
    bool ok = cJSON_PrintPreallocated(root, out, capacity, false);
    cJSON_Delete(root);
    return ok;
}
