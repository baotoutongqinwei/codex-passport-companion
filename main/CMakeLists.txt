set(app_sources "companion_main.c" "../assets/fonts/passport_font_16.c")
if(CONFIG_PASSPORT_MODE_OFFLINE)
    list(APPEND app_sources "companion_offline_model.c" "companion_offline_ui.c")
else()
    list(APPEND app_sources "companion_model.c" "companion_runtime.c" "companion_ui.c")
    if(CONFIG_PASSPORT_MODE_USB)
        list(APPEND app_sources "companion_transport_usb.c" "companion_link.c" "companion_wire.c" "companion_device.c")
    elseif(CONFIG_PASSPORT_MODE_BLE)
        list(APPEND app_sources "companion_transport_ble.c" "companion_link.c" "companion_wire.c" "companion_adpcm.c" "companion_device.c")
    else()
        list(APPEND app_sources "companion_config.c" "companion_transport_wifi.c")
    endif()
endif()
idf_component_register(
    SRCS ${app_sources}
    INCLUDE_DIRS "."
    REQUIRES bsp esp_event esp_hw_support esp_netif esp_timer esp_wifi nvs_flash
             esp_http_client json esp_driver_usb_serial_jtag bt app_update bootloader_support spi_flash
)
target_link_libraries(${COMPONENT_LIB} INTERFACE "-u cp_firmware_identity")
