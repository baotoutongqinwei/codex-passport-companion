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
#include <string.h>

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static cp_device_info_t s_cached;

void cp_device_snapshot(cp_device_info_t *info) {
    portENTER_CRITICAL(&s_lock);
    *info = s_cached;
    portEXIT_CRITICAL(&s_lock);
}

void cp_device_update(void) {
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
    cp_device_info_t d = {.valid=true, .app_size=app_size, .app_capacity=app_capacity};
    multi_heap_info_t heap;
    heap_caps_get_info(&heap, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    d.heap_total=heap.total_allocated_bytes+heap.total_free_bytes;
    d.heap_free=heap.total_free_bytes; d.heap_min=heap.minimum_free_bytes;
    d.heap_largest=heap.largest_free_block;
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    d.revision=chip.revision; d.cores=chip.cores; d.cpu_mhz=CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ;
    esp_flash_get_size(NULL, &d.flash_size);
    d.psram_size=heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    d.battery=bsp_battery_soc(); d.voltage=bsp_battery_mv();
    d.has_temperature=bsp_temperature_read(&d.temperature)==ESP_OK;
    nvs_stats_t nvs;
    d.has_nvs=nvs_get_stats("nvs", &nvs)==ESP_OK;
    if (d.has_nvs) { d.nvs_used=nvs.used_entries; d.nvs_free=nvs.free_entries; d.nvs_total=nvs.total_entries; }
#if CONFIG_PASSPORT_MODE_USB || CONFIG_PASSPORT_MODE_BLE
    d.has_rssi=cp_transport_rssi(&d.rssi);
#endif
    const esp_app_desc_t *app=esp_app_get_description();
    snprintf(d.version,sizeof(d.version),"%s",app->version);
    snprintf(d.idf,sizeof(d.idf),"%s",app->idf_ver);
    snprintf(d.profile,sizeof(d.profile),"%s",CP_PROFILE);
    for (unsigned i=0;i<32;++i) snprintf(d.elf+i*2,3,"%02x",app->app_elf_sha256[i]);
    d.reset_reason=esp_reset_reason(); d.tasks=uxTaskGetNumberOfTasks();
    d.sampled_us=esp_timer_get_time();
    portENTER_CRITICAL(&s_lock);
    s_cached=d;
    portEXIT_CRITICAL(&s_lock);
}

#if CONFIG_PASSPORT_MODE_USB || CONFIG_PASSPORT_MODE_BLE
bool cp_device_json(char *out, size_t capacity) {
    cp_device_info_t d;
    cp_device_snapshot(&d);
    if (!d.valid) return false;
    cJSON *root=cJSON_CreateObject();
    if (!root) return false;
#define NUM(key, value) cJSON_AddNumberToObject(root, key, value)
    NUM("schema",1);
    cJSON_AddStringToObject(root,"chip","ESP32-C3");
    cJSON_AddStringToObject(root,"profile",d.profile);
    cJSON_AddStringToObject(root,"firmware",d.version);
    cJSON_AddStringToObject(root,"elf_sha256",d.elf);
    cJSON_AddStringToObject(root,"idf",d.idf);
    NUM("revision",d.revision); NUM("cores",d.cores); NUM("cpu_mhz",d.cpu_mhz);
    NUM("flash_bytes",d.flash_size); NUM("psram_bytes",d.psram_size);
    NUM("display_width",BSP_LCD_W); NUM("display_height",BSP_LCD_H);
    NUM("uptime_s",esp_timer_get_time()/1000000); NUM("reset_reason",d.reset_reason);
    NUM("heap_total",d.heap_total); NUM("heap_free",d.heap_free);
    NUM("heap_min",d.heap_min); NUM("heap_largest",d.heap_largest);
    NUM("app_used",d.app_size); NUM("app_capacity",d.app_capacity);
    if (d.has_nvs) { NUM("nvs_used",d.nvs_used); NUM("nvs_free",d.nvs_free); NUM("nvs_total",d.nvs_total); }
    if (d.battery>=0) NUM("battery_pct",d.battery);
    if (d.voltage>=0) NUM("battery_mv",d.voltage);
    if (d.has_temperature) NUM("die_c",d.temperature);
    if (d.has_rssi) NUM("rssi_dbm",d.rssi);
    NUM("tasks",d.tasks); NUM("network_stack_min",uxTaskGetStackHighWaterMark(NULL));
#undef NUM
    bool ok=cJSON_PrintPreallocated(root,out,capacity,false);
    cJSON_Delete(root);
    return ok;
}
#endif
