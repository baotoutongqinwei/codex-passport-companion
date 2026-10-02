#include "companion_transport.h"
#include "driver/usb_serial_jtag.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"

static void receive_task(void *arg) {
    (void)arg;
    uint8_t bytes[256];
    for (;;) {
        int n=usb_serial_jtag_read_bytes(bytes,sizeof(bytes),pdMS_TO_TICKS(100));
        if (n>0) cp_link_receive(bytes,n);
    }
}
esp_err_t cp_transport_start(const cp_config_t *config) {
    (void)config;
    esp_err_t result=cp_link_init();
    if (result!=ESP_OK) return result;
    usb_serial_jtag_driver_config_t settings={.rx_buffer_size=4096,.tx_buffer_size=4096};
    result=usb_serial_jtag_driver_install(&settings);
    if (result!=ESP_OK) return result;
    return xTaskCreate(receive_task,"cp_usb_rx",3072,NULL,4,NULL)==pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
bool cp_link_write(const uint8_t *data, size_t size) {
    int64_t deadline=esp_timer_get_time()+3000000;
    while (size && esp_timer_get_time()<deadline) {
        int n=usb_serial_jtag_write_bytes(data,size,pdMS_TO_TICKS(100));
        if (n>0) { data+=n; size-=n; }
    }
    return size==0;
}
bool cp_transport_connected(void) { return true; }
void cp_transport_poll(void) {}
bool cp_transport_audio_ready(void) { return true; }
int cp_transport_passkey(void) { return -1; }
void cp_transport_forget_bonds(void) {}
const char *cp_transport_name(void) { return "USB"; }
const char *cp_transport_help(void) { return "USB 串口版\n\n1. 数据线连接 Mac\n\n2. Mac 选择 USB 模式\n\n使用时保持连接"; }
