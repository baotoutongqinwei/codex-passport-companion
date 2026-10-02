#include "bsp_temperature.h"
#include "driver/temperature_sensor.h"

esp_err_t bsp_temperature_read(float *celsius) {
    static temperature_sensor_handle_t sensor;
    if (!celsius) return ESP_ERR_INVALID_ARG;
    if (!sensor) {
        temperature_sensor_config_t config = TEMPERATURE_SENSOR_CONFIG_DEFAULT(10, 80);
        esp_err_t result = temperature_sensor_install(&config, &sensor);
        if (result != ESP_OK) return result;
    }
    esp_err_t result = temperature_sensor_enable(sensor);
    if (result != ESP_OK) return result;
    result = temperature_sensor_get_celsius(sensor, celsius);
    esp_err_t stopped = temperature_sensor_disable(sensor);
    return result != ESP_OK ? result : stopped;
}
