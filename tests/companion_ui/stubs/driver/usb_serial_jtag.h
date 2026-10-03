#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
typedef unsigned TickType_t;
typedef struct { size_t rx_buffer_size, tx_buffer_size; } usb_serial_jtag_driver_config_t;
esp_err_t usb_serial_jtag_driver_install(const usb_serial_jtag_driver_config_t *config);
int usb_serial_jtag_read_bytes(void *buffer, size_t length, TickType_t timeout);
int usb_serial_jtag_write_bytes(const void *buffer, size_t length, TickType_t timeout);
