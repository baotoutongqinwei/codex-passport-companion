#include "companion.h"
#include "companion_transport.h"
#include "companion_adpcm.h"
#include "companion_device.h"
#include "sdkconfig.h"
#include "bsp_audio.h"
#include "bsp_battery.h"
#include "cJSON.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/stream_buffer.h"
#include "freertos/task.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

static const char *TAG = "companion";
static cp_state_t s_state;
static cp_view_t s_incoming;
static SemaphoreHandle_t s_lock;
static QueueHandle_t s_commands, s_audio_jobs;
static StreamBufferHandle_t s_pcm;
static char s_response[8193];
static char s_thread[CP_ID_SIZE], s_cursor[CP_CURSOR_SIZE];
static int s_page = -1;
static unsigned s_selection_version;
static bool s_force, s_stop, s_capture_done = true, s_capture_error;
static bool s_audio_ready;

typedef enum { CMD_RECORD, CMD_SEND, CMD_CANCEL, CMD_READ } command_kind_t;
typedef struct { command_kind_t kind; char thread[CP_ID_SIZE], revision[33]; } command_t;
typedef struct { bool capture, cue; unsigned frequency; } audio_job_t;

static void lock(void) { xSemaphoreTake(s_lock, portMAX_DELAY); }
static void unlock(void) { xSemaphoreGive(s_lock); }

static void message(const char *text) {
    lock(); cp_utf8_copy(s_state.message, sizeof(s_state.message), text); unlock();
}

void cp_state_snapshot(cp_state_t *state) {
    lock(); *state = s_state; unlock();
}

void cp_select(const char *thread, const char *cursor, int page) {
    lock();
    if (s_state.mode == CP_IDLE) {
        cp_utf8_copy(s_thread, sizeof(s_thread), thread);
        cp_utf8_copy(s_cursor, sizeof(s_cursor), cursor);
        s_page = page; s_force = true; ++s_selection_version;
        s_state.message[0] = 0;
    }
    unlock();
}

void cp_record_start(void) {
    command_t command = { .kind = CMD_RECORD };
    lock();
    if (s_state.mode != CP_IDLE || !s_state.bridge || !s_thread[0]) { unlock(); return; }
    if (!cp_transport_audio_ready()) { unlock(); message("连接速率不足，请重新连接后录音"); return; }
    if (!s_state.view.asr_ready) { unlock(); message("请先在 Mac 安装语音模型"); return; }
    if (!s_audio_ready) { unlock(); message("麦克风初始化失败"); return; }
    strcpy(command.thread, s_thread);
    s_stop = false; s_capture_error = false;
    s_state.mode = CP_STARTING;
    s_state.recorded_ms = 0;
    s_state.input_level = 0;
    s_state.alert_until = 0;
    s_state.message[0] = 0;
    unlock();
    if (xQueueSend(s_commands, &command, 0) != pdTRUE) {
        lock(); s_state.mode = CP_IDLE; unlock(); message("操作繁忙，请稍后重试");
    }
}

void cp_record_stop(void) {
    lock();
    s_stop = true;
    if (s_state.mode == CP_RECORDING) s_state.mode = CP_FINISHING;
    unlock();
}

bool cp_mark_read(const char *thread, const char *revision) {
    command_t command = {.kind=CMD_READ};
    cp_utf8_copy(command.thread, sizeof(command.thread), thread);
    cp_utf8_copy(command.revision, sizeof(command.revision), revision);
    return xQueueSend(s_commands, &command, 0) == pdTRUE;
}

void cp_send_draft(void) {
    command_t command = { .kind = CMD_SEND };
    lock();
    if (s_state.mode != CP_REVIEW || strcmp(s_state.view.draft_state, "ready") != 0) { unlock(); return; }
    s_state.mode = CP_SENDING;
    unlock();
    if (xQueueSend(s_commands, &command, 0) != pdTRUE) {
        lock(); s_state.mode = CP_REVIEW; unlock();
        message("操作繁忙，请稍后重试");
    }
}

void cp_cancel(void) {
    cp_record_stop();
    command_t command = { .kind = CMD_CANCEL };
    if (xQueueSend(s_commands, &command, 0) != pdTRUE) message("操作繁忙，请稍后重试");
}

static cJSON *request(const char *path, const void *body, int length, bool audio) {
    int status=0;
    if (!cp_transport_request(path,body,length,audio,s_response,sizeof(s_response),&status)) {
        lock(); s_state.bridge=false; unlock();
        message("连接中断，请检查 Mac 桥接程序");
        return NULL;
    }
    cJSON *json=cJSON_Parse(s_response);
    if (!json || status!=200) {
        if (status==401) { lock(); s_state.bridge=false; unlock(); }
        cJSON *error=json ? cJSON_GetObjectItemCaseSensitive(json,"error") : NULL;
        message(cJSON_IsString(error) ? error->valuestring : "桥接服务响应异常");
        cJSON_Delete(json); return NULL;
    }
    lock();
    if (!s_state.bridge) s_state.message[0]=0;
    s_state.bridge=true;
    unlock();
    return json;
}

static cJSON *action(const char *kind, const char *key, const char *value, int chunks, const char *revision) {
    char id[33];
    snprintf(id, sizeof(id), "%08lx%08lx%08lx%08lx", (unsigned long)esp_random(),
             (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random());
    cJSON *json = cJSON_CreateObject();
    if (!json) return NULL;
    cJSON_AddStringToObject(json, "action", kind);
    cJSON_AddStringToObject(json, "request_id", id);
    if (key) cJSON_AddStringToObject(json, key, value);
    if (chunks >= 0) cJSON_AddNumberToObject(json, "chunks", chunks);
    if (revision) cJSON_AddStringToObject(json, "revision", revision);
    char *text = cJSON_PrintUnformatted(json);
    cJSON_Delete(json);
    if (!text) return NULL;
    cJSON *reply = request("/v1/action", text, strlen(text), false);
    free(text);
    return reply;
}

static void string(cJSON *root, const char *key, char *out, size_t capacity) {
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, key);
    cp_utf8_copy(out, capacity, cJSON_IsString(item) ? item->valuestring : "");
}

static int number(cJSON *root, const char *key, int fallback) {
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, key);
    return cJSON_IsNumber(item) ? item->valueint : fallback;
}

static int64_t timestamp(cJSON *root, const char *key) {
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, key);
    return cJSON_IsNumber(item) ? (int64_t)item->valuedouble : 0;
}

static void poll_state(void) {
    char thread[CP_ID_SIZE], cursor[CP_CURSOR_SIZE], encoded[CP_CURSOR_SIZE*3];
    int page; unsigned version;
    lock(); strcpy(thread, s_thread); strcpy(cursor, s_cursor); page = s_page; version = s_selection_version; unlock();
    if (!cp_url_encode(encoded, sizeof(encoded), cursor)) { message("对话列表分页标识过长"); return; }
    char path[1500];
    snprintf(path, sizeof(path), "/v1/state?thread=%s&cursor=%s&page=%d", thread, encoded, page);
    cJSON *json = request(path, NULL, 0, false);
    if (!json) return;
    cJSON *server_time = cJSON_GetObjectItemCaseSensitive(json, "now");
    if (cJSON_IsNumber(server_time) && server_time->valuedouble > 1700000000 &&
        server_time->valuedouble < 4102444800.0) {
        int64_t seconds = (int64_t)server_time->valuedouble;
        struct timeval synced = { .tv_sec = seconds,
            .tv_usec = (long)((server_time->valuedouble - seconds)*1000000) };
        if (settimeofday(&synced, NULL) == 0) {
            lock(); s_state.clock_synced = true; unlock();
        }
    }
    memset(&s_incoming, 0, sizeof(s_incoming));
    cJSON *threads = cJSON_GetObjectItemCaseSensitive(json, "threads");
    if (!cJSON_IsArray(threads)) { cJSON_Delete(json); message("对话数据格式错误"); return; }
    cJSON *item;
    cJSON_ArrayForEach(item, threads) {
        if (s_incoming.count >= CP_THREAD_COUNT) break;
        cp_thread_t *t = &s_incoming.threads[s_incoming.count++];
        string(item, "id", t->id, sizeof(t->id));
        string(item, "title", t->title, sizeof(t->title));
        string(item, "project", t->project, sizeof(t->project));
        string(item, "status", t->status, sizeof(t->status));
        t->unread = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(item, "unread"));
        t->queued = number(item, "queued", 0);
        if (t->queued < 0 || t->queued > 32) t->queued = 0;
    }
    string(json, "next", s_incoming.next, sizeof(s_incoming.next));
    string(json, "id", s_incoming.id, sizeof(s_incoming.id));
    string(json, "title", s_incoming.title, sizeof(s_incoming.title));
    string(json, "body", s_incoming.body, sizeof(s_incoming.body));
    string(json, "status", s_incoming.status, sizeof(s_incoming.status));
    string(json, "revision", s_incoming.revision, sizeof(s_incoming.revision));
    s_incoming.p1 = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(json, "p1"));
    s_incoming.unread = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(json, "unread"));
    s_incoming.page = number(json, "page", 0);
    s_incoming.pages = number(json, "pages", 1);
    s_incoming.asr_ready = cp_transport_audio_ready() && cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(json, "asr"));
    cJSON *quota = cJSON_GetObjectItemCaseSensitive(json, "quota");
    for (int i = 0; i < 2; ++i) {
        cJSON *window = cJSON_GetObjectItemCaseSensitive(quota, i ? "secondary" : "primary");
        s_incoming.remaining[i] = number(window, "remaining", -1);
        s_incoming.reset[i] = timestamp(window, "reset");
        s_incoming.windows[i] = number(window, "minutes", 0);
    }
    s_incoming.updated = timestamp(quota, "updated");
    string(quota, "credits", s_incoming.credits, sizeof(s_incoming.credits));
    cJSON *reset_credits = cJSON_GetObjectItemCaseSensitive(quota, "reset_credits");
    s_incoming.reset_credit_count = number(reset_credits, "available", -1);
    s_incoming.reset_credit_details_complete = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(reset_credits, "complete"));
    cJSON *expirations = cJSON_GetObjectItemCaseSensitive(reset_credits, "expirations");
    for (int i = 0; i < 2; ++i) {
        cJSON *expiry = cJSON_GetArrayItem(expirations, i);
        if (cJSON_IsNumber(expiry) && expiry->valuedouble > 0 && expiry->valuedouble <= 253402271999.0)
            s_incoming.reset_credit_expiry[i] = (int64_t)expiry->valuedouble;
    }
    cJSON *draft = cJSON_GetObjectItemCaseSensitive(json, "draft");
    string(draft, "id", s_incoming.draft_id, sizeof(s_incoming.draft_id));
    string(draft, "thread_id", s_incoming.draft_thread, sizeof(s_incoming.draft_thread));
    string(draft, "state", s_incoming.draft_state, sizeof(s_incoming.draft_state));
    string(draft, "text", s_incoming.draft, sizeof(s_incoming.draft));
    cJSON *alert = cJSON_GetObjectItemCaseSensitive(json, "alert");
    char alert_id[17], alert_title[100], alert_kind[16];
    string(alert, "id", alert_id, sizeof(alert_id));
    string(alert, "title", alert_title, sizeof(alert_title));
    string(alert, "kind", alert_kind, sizeof(alert_kind));
    bool sound = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(alert, "sound"));
    cJSON_Delete(json);
    lock();
    if (alert_id[0] && strcmp(alert_id, s_state.alert_id) && s_state.mode == CP_IDLE) {
        strcpy(s_state.alert_id, alert_id); strcpy(s_state.alert_title, alert_title);
        strcpy(s_state.alert_kind, alert_kind); s_state.alert_until = esp_timer_get_time()+6000000;
        if (sound && s_audio_ready) {
            audio_job_t job = {.frequency = !strcmp(alert_kind, "attention") ? 440 : 660};
            xQueueSend(s_audio_jobs, &job, 0);
        }
    }
    if (version == s_selection_version) {
        s_state.view = s_incoming;
        if (s_state.mode == CP_IDLE && s_incoming.draft_id[0]) {
            // Recover a pending confirmation after a card restart or reconnect.
            cp_utf8_copy(s_thread, sizeof(s_thread), s_incoming.draft_thread);
            s_cursor[0] = 0; s_page = -1; s_force = true; ++s_selection_version;
            s_state.mode = strcmp(s_incoming.draft_state, "transcribing") == 0 ? CP_TRANSCRIBING : CP_REVIEW;
        }
        if (s_state.mode == CP_TRANSCRIBING && strcmp(s_incoming.draft_state, "transcribing") != 0 && s_incoming.draft_id[0]) {
            s_state.mode = CP_REVIEW;
        }
        if (s_state.mode == CP_TRANSCRIBING && !s_incoming.draft_id[0]) {
            s_state.mode = CP_IDLE;
            cp_utf8_copy(s_state.message, sizeof(s_state.message), "语音会话已失效，请重新录音");
        }
    }
    unlock();
}

static void capture_task(void *arg) {
    (void)arg;
    int16_t samples[512];
    for (;;) {
        audio_job_t job;
        xQueueReceive(s_audio_jobs, &job, portMAX_DELAY);
        cp_mode_t expected = job.capture ? CP_READY : CP_IDLE;
        if (job.capture) { lock(); s_state.mode = CP_READY; unlock(); }
        if (job.cue || !job.capture) {
            // The same worker owns playback and capture: alerts cannot play over speech.
            for (unsigned start = 0; start < 1920; start += 160) {
                lock(); bool allowed = s_state.mode == expected && (!job.capture || !s_stop); unlock();
                if (!allowed) break;
                for (unsigned n = 0; n < 160; ++n)
                    samples[n] = cp_cue_sample(start+n, 1920, job.capture ? 880 : job.frequency);
                if (bsp_audio_write(samples, 320) != ESP_OK) break;
            }
        }
        if (!job.capture) continue;
        // Give READY a visible interval, then drain pre-start audio, including
        // any cue. Even a silent start can follow an earlier notification.
        vTaskDelay(pdMS_TO_TICKS(150));
        for (int i = 0; i < 6; ++i) {
            if (bsp_audio_read(samples, sizeof(samples)) != ESP_OK) break;
        }
        lock(); if (!s_stop) s_state.mode = CP_RECORDING; unlock();
        size_t bytes = 0;
        for (;;) {
            lock(); bool stop = s_stop; unlock();
            if (stop || bytes >= 16000U*2U*45U) break;
            size_t count = 16000U*2U*45U - bytes;
            if (count > sizeof(samples)) count = sizeof(samples);
            esp_err_t result = bsp_audio_read(samples, count);
            if (result != ESP_OK || xStreamBufferSend(s_pcm, samples, count, pdMS_TO_TICKS(20)) != count) {
                lock(); s_capture_error = true; unlock(); break;
            }
            bytes += count;
            unsigned level = cp_pcm_level(samples, count/2);
            lock();
            s_state.recorded_ms = (unsigned)(bytes*1000U/32000U);
            unsigned old = s_state.input_level;
            s_state.input_level = level > old ? (old*2+level*3)/5 : (old*4+level)/5;
            unlock();
        }
        lock(); s_capture_done = true; s_state.input_level = 0;
        if (s_state.mode == CP_RECORDING || s_state.mode == CP_READY) s_state.mode = CP_FINISHING;
        unlock();
    }
}

static void network_task(void *arg) {
    (void)arg;
    char record_id[CP_ID_SIZE] = "";
    unsigned seq = 0;
    _Alignas(int16_t) uint8_t chunk[2048];
#if CONFIG_PASSPORT_MODE_BLE
    uint8_t compressed[1030];
#endif
    int64_t last_poll = 0, last_battery = 0;
#if CONFIG_PASSPORT_MODE_USB || CONFIG_PASSPORT_MODE_BLE
    int64_t next_device = 0;
#endif
    bool cancel_pending = false;
    for (;;) {
        int64_t now = esp_timer_get_time();
        cp_transport_poll();
        bool wifi=cp_transport_connected();
        lock(); s_state.wifi=wifi; bool done=s_capture_done; bool failed=s_capture_error; unlock();
        if (!wifi) {
#if CONFIG_PASSPORT_MODE_USB || CONFIG_PASSPORT_MODE_BLE
            next_device = 0;
#endif
            if (record_id[0]) { lock(); s_stop = true; s_capture_error = true; unlock(); cancel_pending = true; }
        }
        command_t command;
        if (xQueueReceive(s_commands, &command, 0) == pdTRUE) {
            if (command.kind == CMD_CANCEL) {
                cancel_pending = true;
                lock(); s_stop = true; unlock();
            } else if (command.kind == CMD_READ) {
                if (wifi) cJSON_Delete(action("mark_read", "thread_id", command.thread, -1, command.revision));
            } else if (command.kind == CMD_RECORD) {
                cJSON *reply = wifi ? action("record_start", "thread_id", command.thread, -1, NULL) : NULL;
                if (reply) string(reply, "record_id", record_id, sizeof(record_id));
                bool cue = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(reply, "cue"));
                cJSON_Delete(reply);
                if (record_id[0]) {
                    xStreamBufferReset(s_pcm);
                    seq = 0;
                    lock(); s_capture_done = false; s_capture_error = false; unlock();
                    audio_job_t job = {.capture=true, .cue=cue};
                    if (xQueueSend(s_audio_jobs, &job, 0) != pdTRUE) {
                        lock(); s_capture_done = true; s_capture_error = true; unlock();
                    }
                    ESP_LOGI(TAG, "record heap=%lu largest=%lu", (unsigned long)esp_get_free_heap_size(),
                             (unsigned long)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
                } else { lock(); s_state.mode = CP_IDLE; unlock(); }
            } else if (command.kind == CMD_SEND) {
                char draft[CP_ID_SIZE];
                lock(); strcpy(draft, s_state.view.draft_id); s_state.mode = CP_SENDING; unlock();
                cJSON *reply = action("send", "draft_id", draft, -1, NULL);
                if (reply) {
                    cJSON_Delete(reply);
                    cJSON_Delete(action("cancel", NULL, NULL, -1, NULL));
                    lock(); s_state.mode = CP_IDLE; s_page = -1; s_force = true; unlock();
                } else {
                    lock(); s_state.mode = CP_REVIEW; unlock();
                    poll_state();
                }
            }
        }
        lock(); done = s_capture_done; failed = s_capture_error; unlock();
        if (cancel_pending && done) {
            if (wifi) cJSON_Delete(action("cancel", NULL, NULL, -1, NULL));
            xStreamBufferReset(s_pcm);
            record_id[0] = 0; cancel_pending = false;
            lock(); s_state.mode = CP_IDLE; s_state.view.draft_id[0] = 0; s_force = true; unlock();
        } else if (record_id[0]) {
            if (failed) {
                lock(); s_stop = true; unlock();
                cancel_pending = true;
                message("音频传输中断，请重新录音");
            } else if (wifi) {
                size_t n = xStreamBufferReceive(s_pcm, chunk, sizeof(chunk), pdMS_TO_TICKS(10));
                if (n) {
                    char path[128]; snprintf(path, sizeof(path), "/v1/audio/%s?seq=%u", record_id, seq);
#if CONFIG_PASSPORT_MODE_BLE
                    size_t packed=cp_adpcm_encode((const int16_t *)chunk,n/2,compressed,sizeof(compressed));
                    snprintf(path,sizeof(path),"/v1/audio-adpcm/%s?seq=%u",record_id,seq);
                    cJSON *reply=packed ? request(path,compressed,packed,true) : NULL;
#else
                    cJSON *reply = request(path, chunk, n, true);
#endif
                    if (!reply) { lock(); s_capture_error = true; s_stop = true; unlock(); }
                    else ++seq;
                    cJSON_Delete(reply);
                } else if (done) {
                    // Releasing during preparation is cancellation, not an ASR error.
                    if (!seq) { cancel_pending = true; continue; }
                    cJSON *reply = action("record_finish", "record_id", record_id, seq, NULL);
                    lock(); s_state.mode = reply ? CP_TRANSCRIBING : CP_IDLE; s_force = true; unlock();
                    if (!reply) cJSON_Delete(action("cancel", NULL, NULL, -1, NULL));
                    cJSON_Delete(reply);
                    record_id[0] = 0;
                }
            }
        } else if (wifi) {
            lock(); bool force = s_force; s_force = false; unlock();
            if (force || now - last_poll > 1500000) { poll_state(); last_poll = esp_timer_get_time(); }
#if CONFIG_PASSPORT_MODE_USB || CONFIG_PASSPORT_MODE_BLE
            lock(); bool idle = s_state.mode == CP_IDLE; unlock();
            if (idle && now >= next_device && uxQueueMessagesWaiting(s_commands) == 0) {
                char device[1536];
                int status = 0;
                if (cp_device_json(device, sizeof(device))) {
                    // Local USB/authenticated BLE only; never sent over Wi-Fi.
                    // Old helpers may reject this optional endpoint without UI errors.
                    cp_transport_request("/v1/device", device, strlen(device), false,
                                         s_response, sizeof(s_response), &status);
                }
                next_device = esp_timer_get_time() + (status == 200 ? 5000000 : 60000000);
            }
#endif
        }
        if (now - last_battery > 30000000) {
            int battery = bsp_battery_soc();
            lock(); s_state.battery = battery; unlock();
            ESP_LOGI(TAG, "heap=%lu minimum=%lu largest=%lu network_stack=%u",
                     (unsigned long)esp_get_free_heap_size(), (unsigned long)esp_get_minimum_free_heap_size(),
                     (unsigned long)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT),
                     (unsigned)uxTaskGetStackHighWaterMark(NULL));
            last_battery = now;
        }
        vTaskDelay(pdMS_TO_TICKS(record_id[0] ? 5 : 30));
    }
}

void cp_runtime_start(const cp_config_t *config) {
    s_lock = xSemaphoreCreateMutex();
    s_audio_jobs = xQueueCreate(2, sizeof(audio_job_t));
    s_commands = xQueueCreate(4, sizeof(command_t));
    s_pcm = xStreamBufferCreate(8192, 1024);
    ESP_ERROR_CHECK(s_lock && s_audio_jobs && s_commands && s_pcm ? ESP_OK : ESP_ERR_NO_MEM);
    s_state.battery = -1;
    s_state.view.remaining[0] = s_state.view.remaining[1] = -1;
#if CONFIG_PASSPORT_MODE_WIFI
    s_state.configured = config != NULL;
    if (!config) { message("首次使用请通过 USB 配置 Wi-Fi 和 Mac"); return; }
#else
    s_state.configured=true;
#endif
    s_state.battery=bsp_battery_soc();
    s_audio_ready=bsp_audio_init()==ESP_OK && bsp_audio_set_format(16000,16,1)==ESP_OK;
    if (s_audio_ready) bsp_audio_set_volume(30);
    esp_err_t result=cp_transport_start(config);
    if (result!=ESP_OK) { message("通信初始化失败，请重启设备"); return; }
    if (xTaskCreate(capture_task, "cp_audio", 4096, NULL, 6, NULL) != pdPASS ||
        xTaskCreate(network_task, "cp_network", 12288, NULL, 4, NULL) != pdPASS) {
        message("任务内存不足，请重启设备");
    }
}
