#include "companion_transport.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include <string.h>
#include <stdio.h>
#include <sys/time.h>
static cp_config_t s_config;
static esp_http_client_handle_t s_http;
static char *s_response;
static size_t s_capacity, s_response_size;
static bool s_response_overflow;
static volatile bool s_connected;
static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *event) {
    (void)arg;
    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        s_connected = true;
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        s_connected = false;
        const wifi_event_sta_disconnected_t *reason=event;
        ESP_LOGW("cp_wifi", "Wi-Fi disconnect reason=%u", reason->reason);
    }
}

static esp_err_t wifi_start(void) {
    esp_err_t result = esp_netif_init();
    if (result != ESP_OK) return result;
    result = esp_event_loop_create_default();
    if (result != ESP_OK) return result;
    if (!esp_netif_create_default_wifi_sta()) return ESP_ERR_NO_MEM;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    if ((result = esp_wifi_init(&init)) != ESP_OK) return result;
    if ((result = esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED, wifi_event, NULL)) != ESP_OK) return result;
    if ((result = esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL)) != ESP_OK) return result;
    wifi_config_t config = {0};
    memcpy(config.sta.ssid, s_config.ssid, strlen(s_config.ssid));
    memcpy(config.sta.password, s_config.password, strlen(s_config.password));
    config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    if ((result = esp_wifi_set_storage(WIFI_STORAGE_RAM)) != ESP_OK) return result;
    if ((result = esp_wifi_set_mode(WIFI_MODE_STA)) != ESP_OK) return result;
    if ((result = esp_wifi_set_config(WIFI_IF_STA, &config)) != ESP_OK) return result;
    if ((result = esp_wifi_start()) != ESP_OK) return result;
    esp_wifi_set_ps(WIFI_PS_NONE);
    return esp_wifi_connect();
}

static esp_err_t http_event(esp_http_client_event_t *event) {
    if (event->event_id == HTTP_EVENT_ON_DATA && event->data_len > 0) {
        if (s_response_size + (size_t)event->data_len >= s_capacity) {
            s_response_overflow = true;
            return ESP_FAIL;
        }
        memcpy(s_response + s_response_size, event->data, event->data_len);
        s_response_size += event->data_len;
    }
    return ESP_OK;
}


bool cp_transport_request(const char *path, const void *body, size_t length, bool audio, char *out, size_t capacity, int *status) {
    char url[1800];
    int n = snprintf(url, sizeof(url), "%s%s", s_config.url, path);
    if (n < 0 || (size_t)n >= sizeof(url) || !s_http) return false;
    s_response=out; s_capacity=capacity; s_response_size=0; s_response_overflow=false;
    esp_http_client_set_url(s_http, url);
    esp_http_client_set_method(s_http, body ? HTTP_METHOD_POST : HTTP_METHOD_GET);
    esp_http_client_set_header(s_http, "Content-Type", audio ? "application/octet-stream" : "application/json");
    esp_http_client_set_post_field(s_http, body, body ? length : 0);
    esp_err_t result = esp_http_client_perform(s_http);
    // The caller owns body; never leave a stale pointer attached to the client.
    esp_http_client_set_post_field(s_http, NULL, 0);
    if (result != ESP_OK || s_response_overflow) {
        esp_http_client_close(s_http);
        return false;
    }
    s_response[s_response_size] = 0;
    *status=esp_http_client_get_status_code(s_http);
    return true;
}

esp_err_t cp_transport_start(const cp_config_t *config) {
    if (!config) return ESP_ERR_INVALID_ARG;
    s_config = *config;
    struct timeval time = { .tv_sec = config->epoch };
    settimeofday(&time, NULL);
    esp_http_client_config_t http = {
        .url = s_config.url, .cert_pem = s_config.cert, .event_handler = http_event,
        .timeout_ms = 30000, .buffer_size = 1024, .buffer_size_tx = 1024,
        .keep_alive_enable = true,
    };
    s_http = esp_http_client_init(&http);
    if (!s_http) return ESP_ERR_NO_MEM;
    char auth[80]; snprintf(auth, sizeof(auth), "Bearer %s", s_config.token);
    esp_http_client_set_header(s_http, "Authorization", auth);
    return wifi_start();
}

bool cp_transport_connected(void) { return s_connected; }
void cp_transport_poll(void) {
    static int64_t last;
    int64_t now=esp_timer_get_time();
    if (!s_connected && now-last>5000000) { esp_wifi_connect(); last=now; }
}
bool cp_transport_audio_ready(void) { return true; }
int cp_transport_passkey(void) { return -1; }
void cp_transport_forget_bonds(void) {}
const char *cp_transport_name(void) { return "Wi-Fi"; }
const char *cp_transport_help(void) { return "Wi-Fi 版\n\n1. Mac 启动桥接程序\n\n2. USB 配置 Wi-Fi\n\n3. 卡片与 Mac 同网"; }
