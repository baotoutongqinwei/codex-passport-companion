#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <assert.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_ERROR_CHECK(x) assert((x) == ESP_OK)
typedef void *esp_lcd_panel_handle_t;
typedef void *esp_lcd_panel_io_handle_t;
typedef void *QueueHandle_t;
#define pdTRUE 1
#define pdMS_TO_TICKS(x) (x)
static inline void *xQueueCreate(unsigned a, unsigned b) { (void)a; (void)b; return (void *)1; }
static inline int xQueueSend(void *q, const void *v, int t) { (void)q; (void)v; (void)t; return 1; }
static inline int xQueueReceive(void *q, void *v, int t) { (void)q; (void)v; (void)t; return 0; }
static inline void vTaskDelay(unsigned t) { (void)t; }
static inline int64_t esp_timer_get_time(void) { return 1000000; }
