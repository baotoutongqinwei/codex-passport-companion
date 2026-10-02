#include "companion_transport.h"
#include "companion_wire.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_random.h"
#include <stdlib.h>
#include <string.h>

static cp_wire_parser_t s_parser;
static SemaphoreHandle_t s_mutex, s_reply;
static uint32_t s_sequence, s_expected;
static char *s_output;
static size_t s_capacity;
static int s_status;
static bool s_ok;

esp_err_t cp_link_init(void) {
    s_mutex=xSemaphoreCreateMutex(); s_reply=xSemaphoreCreateBinary();
    s_sequence=esp_random();
    return s_mutex && s_reply ? ESP_OK : ESP_ERR_NO_MEM;
}
void cp_link_disconnected(void) {
    xSemaphoreTake(s_mutex,portMAX_DELAY);
    s_ok=false; s_parser.used=s_parser.expected=0;
    if (s_expected) xSemaphoreGive(s_reply);
    xSemaphoreGive(s_mutex);
}
void cp_link_receive(const uint8_t *data, size_t size) {
    xSemaphoreTake(s_mutex,portMAX_DELAY);
    for (size_t i=0; i<size; ++i) {
        cp_wire_frame_t frame;
        if (cp_wire_feed(&s_parser,data[i],&frame) && s_expected &&
            frame.id==s_expected && frame.status>=200 && frame.status<=599 &&
            frame.path_size==0 && frame.body_size<s_capacity) {
            memcpy(s_output,frame.body,frame.body_size); s_output[frame.body_size]=0;
            s_status=frame.status; s_ok=true;
            xSemaphoreGive(s_reply);
        }
    }
    xSemaphoreGive(s_mutex);
}
bool cp_transport_request(const char *path, const void *body, size_t size,
                          bool audio, char *out, size_t capacity, int *status) {
    (void)audio;
    if (!cp_transport_connected() || size>4096 || strlen(path)>CP_WIRE_PATH_MAX) return false;
    size_t capacity_tx=CP_WIRE_HEADER+strlen(path)+size+4;
    uint8_t *tx=malloc(capacity_tx);
    if (!tx) return false;
    xSemaphoreTake(s_mutex,portMAX_DELAY);
    xSemaphoreTake(s_reply,0);
    if (++s_sequence==0) ++s_sequence;
    s_expected=s_sequence; s_output=out; s_capacity=capacity; s_ok=false;
    s_parser.used=s_parser.expected=0;
    size_t n=cp_wire_encode(tx,capacity_tx,s_expected,0,path,body,size);
    xSemaphoreGive(s_mutex);
    bool sent=n && cp_link_write(tx,n);
    free(tx);
    if (sent) xSemaphoreTake(s_reply,pdMS_TO_TICKS(30000));
    xSemaphoreTake(s_mutex,portMAX_DELAY);
    bool ok=sent && s_ok;
    *status=s_status; s_expected=0; s_output=NULL; s_capacity=0;
    xSemaphoreGive(s_mutex);
    return ok;
}
