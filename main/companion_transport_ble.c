#include "companion_transport.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "host/ble_hs.h"
#include "host/ble_gap.h"
#include "host/ble_sm.h"
#include "host/ble_store.h"
#include "host/util/util.h"
#include "nimble/nimble_port.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
#include <stdio.h>
#include <string.h>

// Custom service, with the low-byte-first UUID representation required by NimBLE.
#define UUID(n) BLE_UUID128_INIT(0x9e,0xca,0xdc,0x24,0x0e,0xe5,0xa9,0xe0,0x93,0xf3,0xa3,0xb5,n,0xf0,0x40,0x6e)
static const ble_uuid128_t service_uuid=UUID(1), rx_uuid=UUID(2), tx_uuid=UUID(3), info_uuid=UUID(4);
static uint16_t s_tx_handle;
static uint8_t s_addr_type;
static volatile uint16_t s_connection=BLE_HS_CONN_HANDLE_NONE;
static volatile bool s_secure, s_subscribed;
static volatile unsigned s_generation;
static volatile int s_passkey=-1;
static char s_name[24];
static struct ble_npl_event s_forget_event;
void ble_store_config_init(void);
static int gap_event(struct ble_gap_event *event, void *arg);

static bool authenticated(uint16_t connection) {
    struct ble_gap_conn_desc desc;
    return ble_gap_conn_find(connection,&desc)==0 && desc.sec_state.encrypted && desc.sec_state.authenticated;
}
static int access_characteristic(uint16_t connection, uint16_t handle,
                                  struct ble_gatt_access_ctxt *ctx, void *arg) {
    (void)handle; (void)arg;
    if (!authenticated(connection)) return BLE_ATT_ERR_INSUFFICIENT_AUTHEN;
    if (ctx->op==BLE_GATT_ACCESS_OP_READ_CHR) {
        return os_mbuf_append(ctx->om,"CPv1-IMA",8)==0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    if (ctx->op!=BLE_GATT_ACCESS_OP_WRITE_CHR || ble_uuid_cmp(ctx->chr->uuid,&rx_uuid.u))
        return BLE_ATT_ERR_UNLIKELY;
    uint8_t bytes[256];
    unsigned length=OS_MBUF_PKTLEN(ctx->om);
    if (length>sizeof(bytes) || os_mbuf_copydata(ctx->om,0,length,bytes)) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    cp_link_receive(bytes,length);
    return 0;
}
static const struct ble_gatt_svc_def services[]={
    {.type=BLE_GATT_SVC_TYPE_PRIMARY,.uuid=&service_uuid.u,
     .characteristics=(struct ble_gatt_chr_def[]) {
         {.uuid=&rx_uuid.u,.access_cb=access_characteristic,
          .flags=BLE_GATT_CHR_F_WRITE|BLE_GATT_CHR_F_WRITE_AUTHEN},
         {.uuid=&tx_uuid.u,.access_cb=access_characteristic,.val_handle=&s_tx_handle,
          .flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_READ_AUTHEN|BLE_GATT_CHR_F_NOTIFY},
         {.uuid=&info_uuid.u,.access_cb=access_characteristic,
          .flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_READ_AUTHEN},
         {0}
     }}, {0}
};

static int advertise(void) {
    struct ble_hs_adv_fields fields={0}, scan={0};
    fields.flags=BLE_HS_ADV_F_DISC_GEN|BLE_HS_ADV_F_BREDR_UNSUP;
    fields.uuids128=(ble_uuid128_t *)&service_uuid; fields.num_uuids128=1; fields.uuids128_is_complete=1;
    scan.name=(const uint8_t *)s_name; scan.name_len=strlen(s_name); scan.name_is_complete=1;
    int rc=ble_gap_adv_set_fields(&fields);
    if (!rc) rc=ble_gap_adv_rsp_set_fields(&scan);
    struct ble_gap_adv_params params={.conn_mode=BLE_GAP_CONN_MODE_UND,.disc_mode=BLE_GAP_DISC_MODE_GEN};
    if (!rc) rc=ble_gap_adv_start(s_addr_type,NULL,BLE_HS_FOREVER,&params,gap_event,NULL);
    return rc;
}
static void disconnected(void) {
    s_secure=s_subscribed=false; s_connection=BLE_HS_CONN_HANDLE_NONE;
    s_passkey=-1; ++s_generation;
    cp_link_disconnected();
}
static int gap_event(struct ble_gap_event *event, void *arg) {
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status) { advertise(); break; }
        s_connection=event->connect.conn_handle;
        // The authenticated INFO read from macOS initiates pairing if required.
        s_secure=authenticated(s_connection);
        struct ble_gap_upd_params params={.itvl_min=6,.itvl_max=12,.latency=0,.supervision_timeout=400};
        ble_gap_update_params(s_connection,&params);
        break;
    case BLE_GAP_EVENT_DISCONNECT:
        disconnected(); advertise(); break;
    case BLE_GAP_EVENT_ADV_COMPLETE:
        if (s_connection==BLE_HS_CONN_HANDLE_NONE) advertise();
        break;
    case BLE_GAP_EVENT_ENC_CHANGE:
        s_passkey=-1; s_secure=!event->enc_change.status && authenticated(event->enc_change.conn_handle);
        if (!s_secure) ble_gap_terminate(event->enc_change.conn_handle,BLE_ERR_REM_USER_CONN_TERM);
        break;
    case BLE_GAP_EVENT_SUBSCRIBE:
        if (event->subscribe.attr_handle==s_tx_handle) s_subscribed=event->subscribe.cur_notify;
        break;
    case BLE_GAP_EVENT_REPEAT_PAIRING:
        // Never silently discard a stored trust relationship to accept a new peer.
        return BLE_GAP_REPEAT_PAIRING_IGNORE;
    case BLE_GAP_EVENT_PASSKEY_ACTION: {
        if (event->passkey.params.action!=BLE_SM_IOACT_DISP) return BLE_HS_ENOTSUP;
        struct ble_sm_io io={.action=BLE_SM_IOACT_DISP,.passkey=esp_random()%1000000};
        s_passkey=(int)io.passkey;
        return ble_sm_inject_io(event->passkey.conn_handle,&io);
    }
    default: break;
    }
    return 0;
}
static void on_sync(void) {
    if (!ble_hs_util_ensure_addr(0) && !ble_hs_id_infer_auto(0,&s_addr_type)) advertise();
}
static void on_reset(int reason) { (void)reason; disconnected(); }
static void host_task(void *arg) { (void)arg; nimble_port_run(); vTaskDelete(NULL); }
static void forget_bonds(struct ble_npl_event *event) {
    (void)event;
    if (s_connection!=BLE_HS_CONN_HANDLE_NONE) ble_gap_terminate(s_connection,BLE_ERR_REM_USER_CONN_TERM);
    ble_store_clear();
}
void cp_transport_forget_bonds(void) {
    ble_npl_eventq_put(nimble_port_get_dflt_eventq(),&s_forget_event);
}

esp_err_t cp_transport_start(const cp_config_t *config) {
    (void)config;
    esp_err_t result=cp_link_init();
    if (result!=ESP_OK) return result;
    result=nimble_port_init();
    if (result!=ESP_OK) return result;
    uint8_t mac[6]; esp_read_mac(mac,ESP_MAC_BT);
    ble_npl_event_init(&s_forget_event,forget_bonds,NULL);
    snprintf(s_name,sizeof(s_name),"CodexCard-%02X%02X",mac[4],mac[5]);
    ble_svc_gap_init(); ble_svc_gatt_init();
    if (ble_svc_gap_device_name_set(s_name) || ble_gatts_count_cfg(services) || ble_gatts_add_svcs(services)) return ESP_FAIL;
    ble_hs_cfg.sync_cb=on_sync; ble_hs_cfg.reset_cb=on_reset;
    ble_hs_cfg.sm_io_cap=BLE_HS_IO_DISPLAY_ONLY;
    ble_hs_cfg.sm_bonding=1; ble_hs_cfg.sm_mitm=1; ble_hs_cfg.sm_sc=1;
    ble_hs_cfg.sm_our_key_dist=BLE_SM_PAIR_KEY_DIST_ENC|BLE_SM_PAIR_KEY_DIST_ID;
    ble_hs_cfg.sm_their_key_dist=BLE_SM_PAIR_KEY_DIST_ENC|BLE_SM_PAIR_KEY_DIST_ID;
    ble_store_config_init();
    return xTaskCreate(host_task,"cp_ble",4096,NULL,5,NULL)==pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
bool cp_transport_connected(void) { return s_secure && s_subscribed; }
void cp_transport_poll(void) {}
bool cp_transport_audio_ready(void) { return cp_transport_connected() && ble_att_mtu(s_connection)>=128; }
int cp_transport_passkey(void) { return s_passkey; }
const char *cp_transport_name(void) { return "蓝牙"; }
const char *cp_transport_help(void) { return "蓝牙版\n1. Mac 选择蓝牙模式\n2. 选择本卡片\n3. 输入屏幕上的配对码\n\n长按中键清除蓝牙配对\n然后在 Mac 忽略旧设备"; }
bool cp_link_write(const uint8_t *data, size_t size) {
    unsigned generation=s_generation;
    int64_t deadline=esp_timer_get_time()+5000000;
    while (size && esp_timer_get_time()<deadline) {
        if (!cp_transport_connected() || generation!=s_generation) return false;
        size_t chunk=ble_att_mtu(s_connection)-3;
        if (chunk>180) chunk=180;
        if (chunk>size) chunk=size;
        struct os_mbuf *packet=ble_hs_mbuf_from_flat(data,chunk);
        if (!packet) { vTaskDelay(pdMS_TO_TICKS(3)); continue; }
        // NimBLE consumes the mbuf on both success and failure.
        int rc=ble_gatts_notify_custom(s_connection,s_tx_handle,packet);
        if (rc==BLE_HS_ENOMEM || rc==BLE_HS_EAGAIN) { vTaskDelay(pdMS_TO_TICKS(3)); continue; }
        if (rc) return false;
        data+=chunk; size-=chunk;
    }
    return !size;
}
