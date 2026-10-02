#pragma once
#include "sdkconfig.h"
#if CONFIG_PASSPORT_MODE_BLE
#define CP_PROFILE "ble"
#elif CONFIG_PASSPORT_MODE_USB
#define CP_PROFILE "usb"
#elif CONFIG_PASSPORT_MODE_OFFLINE
#define CP_PROFILE "offline"
#else
#define CP_PROFILE "wifi"
#endif
// Kept by the linker even when USB firmware disables logging.
#define CP_FIRMWARE_ID "CPFW1:" CP_PROFILE
extern const char cp_firmware_identity[];
