#pragma once
#include "esp_err.h"
// Optional die temperature, not ambient/battery temperature. One task owns this
// blocking API; never call under the LVGL lock or in an ISR. Lazy installation;
// the sensor is enabled only for each reading. Errors mean unavailable.
esp_err_t bsp_temperature_read(float *celsius);
