#include "companion_battery_log.h"
#include "companion_device.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"
#include <string.h>
#include <stdio.h>

static const char *TAG="cp_battery_log";
static cp_battery_log_t s_log;
static portMUX_TYPE s_lock=portMUX_INITIALIZER_UNLOCKED;
static nvs_handle_t s_nvs;
static TaskHandle_t s_task;
static int64_t s_epoch_offset_ms;
static bool s_clock_known, s_ready, s_storage_ok=true, s_force_sample, s_busy;
static char s_identity[18];

void cp_battery_log_set_epoch(int64_t epoch_ms, int64_t uptime_ms) {
    portENTER_CRITICAL(&s_lock);
    bool first=!s_clock_known;
    s_epoch_offset_ms=epoch_ms-uptime_ms;
    s_clock_known=true;
    s_force_sample|=first;
    portEXIT_CRITICAL(&s_lock);
    if (first && s_task) xTaskNotifyGive(s_task);
}

void cp_battery_log_set_busy(bool busy) {
    portENTER_CRITICAL(&s_lock);
    s_busy=busy;
    portEXIT_CRITICAL(&s_lock);
}

int cp_battery_log_json(uint32_t after, char *out, size_t capacity,
                        uint32_t *log_id, uint32_t *last_sequence) {
    cp_battery_sample_t samples[CP_BATTERY_UPLOAD_COUNT];
    portENTER_CRITICAL(&s_lock);
    bool ready=s_ready, healthy=s_storage_ok;
    *log_id=s_log.log_id;
    unsigned count=cp_battery_log_page(&s_log,after,samples);
    portEXIT_CRITICAL(&s_lock);
    if (!ready) return -1;
    *last_sequence=count ? samples[count-1].sequence : 0;
    return cp_battery_log_packet(samples,count,s_identity,*log_id,healthy,out,capacity);
}

bool cp_battery_log_copy(cp_battery_log_t *out) {
    if (!s_ready) return false;
    portENTER_CRITICAL(&s_lock);
    memcpy(out,&s_log,sizeof(*out));
    portEXIT_CRITICAL(&s_lock);
    return true;
}

unsigned cp_battery_log_count(void) {
    if (!s_ready) return 0;
    portENTER_CRITICAL(&s_lock);
    unsigned count=s_log.count;
    portEXIT_CRITICAL(&s_lock);
    return count;
}

bool cp_battery_log_healthy(void) {
    portENTER_CRITICAL(&s_lock);
    bool healthy=s_ready && s_storage_ok;
    portEXIT_CRITICAL(&s_lock);
    return healthy;
}

static void battery_log_task(void *unused) {
    (void)unused;
    bool dirty=false, warned=false;
    vTaskDelay(pdMS_TO_TICKS(1000));
    for (;;) {
        portENTER_CRITICAL(&s_lock);
        bool busy=s_busy;
        portEXIT_CRITICAL(&s_lock);
        if (busy) { ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(1000)); continue; }
        cp_device_info_t device;
        cp_device_snapshot(&device);
        uint32_t uptime_s=(uint32_t)(esp_timer_get_time()/1000000);
        if (device.valid && esp_timer_get_time()-device.sampled_us<=35000000) {
            int64_t offset;
            bool clock_known;
            portENTER_CRITICAL(&s_lock);
            offset=s_epoch_offset_ms;
            clock_known=s_clock_known;
            bool due=s_force_sample || cp_battery_log_due(&s_log,uptime_s,device.battery);
            if (due) {
                int64_t utc=offset+device.sampled_us/1000;
                cp_battery_log_add(&s_log,clock_known && utc>=1700000000000LL &&
                                   utc<4102444800000LL ? (uint32_t)(utc/1000) : 0,
                                   (uint32_t)(device.sampled_us/1000000),device.battery,device.voltage);
                s_force_sample=false;
                dirty=true;
            }
            portEXIT_CRITICAL(&s_lock);
        }
        if (dirty) {
            esp_err_t result=nvs_set_blob(s_nvs,"samples",&s_log,sizeof(s_log));
            if (result==ESP_OK) result=nvs_commit(s_nvs);
            portENTER_CRITICAL(&s_lock);
            s_storage_ok=result==ESP_OK;
            portEXIT_CRITICAL(&s_lock);
            if (result==ESP_OK) {
                dirty=false; warned=false;
            } else if (!warned) {
                ESP_LOGW(TAG,"电量记录写入失败: %s",esp_err_to_name(result));
                warned=true;
            }
        }
        ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(30000));
    }
}

bool cp_battery_log_start(void) {
    if (s_ready) return true;
    uint8_t mac[6];
    if (esp_efuse_mac_get_default(mac)!=ESP_OK) return false;
    snprintf(s_identity,sizeof(s_identity),"%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    esp_err_t result=nvs_open("cp_battery",NVS_READWRITE,&s_nvs);
    if (result!=ESP_OK) {
        ESP_LOGW(TAG,"无法打开电量日志: %s",esp_err_to_name(result));
        return false;
    }
    size_t size=sizeof(s_log);
    result=nvs_get_blob(s_nvs,"samples",&s_log,&size);
    if (result!=ESP_OK || size!=sizeof(s_log) || !cp_battery_log_valid(&s_log)) {
        cp_battery_log_init(&s_log,esp_random());
    }
    s_force_sample=true;
    s_ready=true;
    if (xTaskCreate(battery_log_task,"cp_battery_log",4096,NULL,2,&s_task)!=pdPASS) {
        s_ready=false;
        nvs_close(s_nvs);
        ESP_LOGW(TAG,"电量记录任务启动失败");
        return false;
    }
    return true;
}
