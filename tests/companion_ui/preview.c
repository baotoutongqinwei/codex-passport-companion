// Render the actual application with LVGL, its real bitmap font and 32 KB pool.
#include <time.h>
static time_t preview_now = 1700000000;
static time_t preview_time(time_t *out) {
    if (out) *out = preview_now;
    return preview_now;
}
#define time preview_time
#include "../../main/companion_ui.c"
#include <stdlib.h>

static uint16_t pixels[240*320];
static _Alignas(16) uint16_t draw_buffer[240*40];
static int starts, stops, sends, cancels, selected_page, reads;
static bool accept_read = true;
static char selected_thread[CP_ID_SIZE];
static int preview_passkey=-1;
const char *cp_transport_name(void) { return "USB"; }
const char *cp_transport_help(void) { return "USB 版\n\n连接 Mac 数据线\n启动 USB 模式\n\n无需 Wi-Fi 配置"; }
int cp_transport_passkey(void) { return preview_passkey; }
void cp_transport_forget_bonds(void) {}
esp_err_t bsp_button_init(bsp_btn_cb_t cb, void *arg) { (void)cb; (void)arg; return ESP_OK; }
bool bsp_lvgl_lock(int timeout) { (void)timeout; return true; }
void bsp_lvgl_unlock(void) {}
void bsp_display_backlight(uint8_t percent) { (void)percent; }
void cp_state_snapshot(cp_state_t *state) { (void)state; }
void cp_select(const char *thread, const char *cursor, int page) {
    (void)cursor; strcpy(selected_thread, thread); selected_page = page;
}
void cp_record_start(void) { ++starts; }
void cp_record_stop(void) { ++stops; }
void cp_send_draft(void) { ++sends; }
void cp_cancel(void) { ++cancels; }
bool cp_mark_read(const char *thread, const char *revision) {
    assert(!strcmp(thread, s_thread) && !strcmp(revision, s.view.revision));
    ++reads; return accept_read;
}

static void flush(lv_display_t *display, const lv_area_t *area, uint8_t *data) {
    uint16_t *source = (uint16_t *)data;
    for (int y = area->y1; y <= area->y2; ++y)
        for (int x = area->x1; x <= area->x2; ++x)
            pixels[y*240+x] = *source++;
    lv_display_flush_ready(display);
}

static void screenshot(const char *directory, const char *name, page_t page) {
    s_page = page;
    render();
    lv_obj_update_layout(s_screen);
    assert(lv_obj_get_height(s_footer) <= 44);
    assert(lv_obj_get_style_text_font(s_body, 0) == &passport_font_16);
    assert(!lv_obj_has_flag(s_clock, LV_OBJ_FLAG_HIDDEN));
    assert(lv_obj_get_x(s_clock) == 18 && lv_obj_get_y(s_clock) == 12);
    assert(lv_obj_get_height(s_clock) == 22);
    assert(lv_obj_get_x(s_clock) + lv_obj_get_width(s_clock) < lv_obj_get_x(s_battery));
    if (page == HOME && preview_passkey < 0) {
        assert(!lv_obj_has_flag(s_screen, LV_OBJ_FLAG_SCROLLABLE));
        assert(lv_obj_has_flag(s_scroll, LV_OBJ_FLAG_HIDDEN));
        lv_obj_t *rows[] = {s_status, s_quota, s_bar, s_auto_title, s_auto_date,
                           s_reset_title, s_reset_dates[0], s_reset_dates[1], s_footer};
        int previous_bottom = 0;
        for (size_t i = 0; i < sizeof(rows)/sizeof(rows[0]); ++i) {
            assert(!lv_obj_has_flag(rows[i], LV_OBJ_FLAG_HIDDEN));
            assert(lv_obj_get_y(rows[i]) >= previous_bottom);
            assert(lv_obj_get_height(rows[i]) <= 22);
            previous_bottom = lv_obj_get_y(rows[i]) + lv_obj_get_height(rows[i]);
        }
        assert(previous_bottom <= 311);
    }
    if (page == THREADS && preview_passkey < 0) {
        assert(lv_obj_has_flag(s_rows[3], LV_OBJ_FLAG_HIDDEN));
        for (int i=0; i<s.view.count; ++i) {
            assert(lv_obj_get_height(s_row_text[i]) <= 22);
            assert(lv_obj_get_height(s_row_status[i]) <= 22);
            assert(lv_obj_get_y(s_rows[i])+lv_obj_get_height(s_rows[i]) < 271);
        }
    }
    if (page == RECORD && preview_passkey < 0) {
        assert(lv_obj_get_height(s_body) <= 118);
        assert(lv_obj_get_height(s_level_text) <= 22);
        assert(!lv_obj_has_flag(s_meter, LV_OBJ_FLAG_HIDDEN));
    }
    lv_obj_invalidate(s_screen);
    lv_refr_now(NULL);
    char path[1024]; snprintf(path, sizeof(path), "%s/%s.ppm", directory, name);
    FILE *file = fopen(path, "wb"); assert(file);
    fprintf(file, "P6\n240 320\n255\n");
    for (int y = 0; y < 320; ++y) for (int x = 0; x < 240; ++x) {
        uint16_t value = pixels[y*240+x];
        // Match the BSP's rounded panel mask.
        int dx = x < 30 ? 30-x : x >= 210 ? x-209 : 0;
        int dy = y < 30 ? 30-y : y >= 290 ? y-289 : 0;
        if (dx*dx+dy*dy > 900 && dx && dy) value = 0;
        unsigned char rgb[] = {(unsigned char)(((value>>11)&31)*255/31),
                               (unsigned char)(((value>>5)&63)*255/63),
                               (unsigned char)((value&31)*255/31)};
        fwrite(rgb, 1, 3, file);
    }
    fclose(file);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    lv_init();
    lv_display_t *display = lv_display_create(240, 320);
    lv_display_set_buffers(display, draw_buffer, NULL, sizeof(draw_buffer), LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(display, flush);
    create_ui();
    render(); assert(strcmp(lv_label_get_text(s_clock), "--:--:--") == 0);
    s.clock_synced = true;
    render(); assert(strcmp(lv_label_get_text(s_clock), "06:13:20") == 0);
    ++preview_now;
    render(); assert(strcmp(lv_label_get_text(s_clock), "06:13:21") == 0);
    // A disconnected bridge must not stop the local clock after synchronization.
    s.bridge = false; ++preview_now;
    render(); assert(strcmp(lv_label_get_text(s_clock), "06:13:22") == 0);
    s.clock_synced = false;
    render(); assert(strcmp(lv_label_get_text(s_clock), "--:--:--") == 0);
    s.clock_synced = true;
    s.configured = s.wifi = s.bridge = true; s.battery = 86;
    preview_now = 1790910000;
    s.view.remaining[0] = 16; s.view.remaining[1] = -1;
    s.view.windows[0] = 10080; s.view.windows[1] = 0;
    s.view.updated = time(NULL); s.view.reset[0] = 1791165964;
    s.view.reset_credit_count = 4; s.view.reset_credit_details_complete = true;
    s.view.reset_credit_expiry[0] = 1791092503;
    s.view.reset_credit_expiry[1] = 1791174104;
    strcpy(s.view.credits, "--"); s.view.asr_ready = true;
    s.view.p1 = true;
    s.view.count = CP_THREAD_COUNT;
    const char *titles[] = {"完善代码并运行测试", "项目中的一个新想法", "检查固件内存使用", "修复网络连接问题"};
    for (int i = 0; i < CP_THREAD_COUNT; ++i) {
        strcpy(s.view.threads[i].title, titles[i]);
        snprintf(s.view.threads[i].id, CP_ID_SIZE, "thread-%d", i);
    }
    screenshot(argv[1], "01-quota", HOME);
    assert(strcmp(lv_label_get_text(s_quota), "7 天额度  剩余 16%") == 0);
    assert(strcmp(lv_label_get_text(s_auto_date), "2026-10-05 10:06") == 0);
    assert(strcmp(lv_label_get_text(s_reset_dates[0]), "2026-10-04 13:41") == 0);
    assert(strcmp(lv_label_get_text(s_reset_dates[1]), "2026-10-05 12:21") == 0);
    cp_view_t known = s.view;
    s.view.reset_credit_count = 1; s.view.reset_credit_expiry[1] = 0;
    screenshot(argv[1], "01a-quota-one", HOME);
    assert(!lv_label_get_text(s_reset_dates[1])[0]);
    s.view.reset_credit_count = 0; s.view.reset_credit_expiry[0] = 0;
    screenshot(argv[1], "01b-quota-none", HOME);
    assert(strcmp(lv_label_get_text(s_reset_dates[0]), "暂无可用重置机会") == 0);
    s.view.reset_credit_count = 4; s.view.reset_credit_details_complete = false;
    screenshot(argv[1], "01c-quota-no-details", HOME);
    assert(strcmp(lv_label_get_text(s_reset_dates[0]), "到期时间暂不可用") == 0);
    s.view.reset_credit_details_complete = true;
    render(); assert(strcmp(lv_label_get_text(s_reset_dates[0]), "无固定到期时间") == 0);
    s.view.reset_credit_count = -1; s.view.updated = 0; s.view.windows[0] = 0;
    screenshot(argv[1], "01d-quota-unknown", HOME);
    assert(strcmp(lv_label_get_text(s_quota), "7 天额度  未知") == 0);
    assert(strcmp(lv_label_get_text(s_auto_date), "--") == 0);
    assert(strcmp(lv_label_get_text(s_reset_dates[0]), "等待数据") == 0);
    s.view = known;
    s.view.updated = time(NULL)-91; s.view.reset[0] = time(NULL)-1;
    s.view.reset_credit_expiry[0] = time(NULL)-1;
    screenshot(argv[1], "01e-quota-expired", HOME);
    assert(strcmp(lv_label_get_text(s_status), "额度待刷新") == 0);
    assert(strcmp(lv_label_get_text(s_auto_date), "等待额度刷新") == 0);
    assert(strcmp(lv_label_get_text(s_reset_dates[0]), "已到期，等待刷新") == 0);
    s.view = known;
    handle((cp_key_t){BSP_BTN_DOWN, BSP_BTN_CLICK}); assert(s_page == HOME);
    handle((cp_key_t){BSP_BTN_UP, BSP_BTN_CLICK}); assert(s_page == HOME);
    handle((cp_key_t){BSP_BTN_DOWN, BSP_BTN_LONG}); assert(s_page == SETTINGS);
    handle((cp_key_t){BSP_BTN_OK, BSP_BTN_CLICK}); assert(s_page == HOME);
    handle((cp_key_t){BSP_BTN_OK, BSP_BTN_CLICK}); assert(s_page == THREADS);
    handle((cp_key_t){BSP_BTN_DOWN, BSP_BTN_CLICK}); assert(s_choice == 1);
    strcpy(s.view.threads[0].status,"active"); s.view.threads[0].queued=3;
    strcpy(s.view.threads[1].status,"needsDesktop"); s.view.threads[1].unread=true;
    strcpy(s.view.threads[2].status,"idle"); s.view.threads[2].unread=true;
    screenshot(argv[1], "02-threads", THREADS);
    handle((cp_key_t){BSP_BTN_OK, BSP_BTN_CLICK});
    assert(s_page == CHAT && strcmp(selected_thread, "thread-1") == 0 && selected_page == -1);
    strcpy(s.view.id, s_thread); strcpy(s.view.title, titles[1]);
    strcpy(s.view.status, "active"); s.view.pages = 6; s.view.page = 5;
    strcpy(s.view.body, "Codex\n我已经完成代码检查。\n发现两处连接异常，\n正在修复并运行测试。\n\n结果会继续同步到这里。");
    screenshot(argv[1], "03-chat", CHAT);
    strcpy(s.view.revision,"revision-1"); s.view.unread=true;
    s_dark=true; read_latest(); assert(reads==0); s_dark=false;
    s_page=HOME; read_latest(); assert(reads==0); s_page=CHAT;
    s.view.page=4; read_latest(); assert(reads==0); s.view.page=5;
    preview_passkey=123456; read_latest(); assert(reads==0); preview_passkey=-1;
    accept_read=false; read_latest(); assert(reads==1);
    accept_read=true; read_latest(); assert(reads==2);
    read_latest(); assert(reads==2);
    s_read_at-=5000000; read_latest(); assert(reads==3); // Lost receipt can retry.
    s.view.unread=false; s_read_at-=5000000; read_latest(); assert(reads==3);
    handle((cp_key_t){BSP_BTN_OK, BSP_BTN_LONG}); assert(starts == 1);
    handle((cp_key_t){BSP_BTN_OK, BSP_BTN_RELEASE}); assert(stops == 1);
    s.mode=CP_STARTING; screenshot(argv[1],"04a-preparing",RECORD);
    s.mode=CP_READY; screenshot(argv[1],"04b-ready",RECORD);
    s.mode = CP_RECORDING; s.recorded_ms = 5000;
    s.input_level=60;
    screenshot(argv[1], "04-record", RECORD);
    assert(lv_bar_get_value(s_meter)==60);
    s.input_level=0; screenshot(argv[1],"04c-quiet",RECORD);
    s.input_level=100; screenshot(argv[1],"04d-loud",RECORD);
    s.mode=CP_FINISHING; screenshot(argv[1],"04e-upload",RECORD);
    s.mode=CP_TRANSCRIBING; screenshot(argv[1],"04f-transcribing",REVIEW);
    s.mode = CP_REVIEW; strcpy(s.view.draft_state, "ready");
    strcpy(s.view.draft, "请帮我检查这个项目的代码，找出问题，并运行测试。");
    screenshot(argv[1], "05-confirm", REVIEW);
    handle((cp_key_t){BSP_BTN_OK, BSP_BTN_CLICK}); assert(sends == 1);
    handle((cp_key_t){BSP_BTN_UP, BSP_BTN_LONG}); assert(cancels == 1);
    s.mode = CP_IDLE;
    screenshot(argv[1], "06-setup", SETTINGS);
    preview_passkey=123456;
    screenshot(argv[1], "07-ble-pairing", HOME);
    assert(strstr(lv_label_get_text(s_body),"123456"));
    assert(!lv_obj_has_flag(s_scroll,LV_OBJ_FLAG_HIDDEN));
    preview_passkey=-1;
    strcpy(s.alert_title,"测试任务"); strcpy(s.alert_kind,"completed"); s.alert_until=2000000;
    screenshot(argv[1],"08-completed",HOME);
    assert(strstr(lv_label_get_text(s_status),"已完成"));
    strcpy(s.alert_kind,"attention"); screenshot(argv[1],"09-attention",THREADS);
    s.alert_until=0; render(); assert(!strstr(lv_label_get_text(s_status),"测试任务"));
    // Long transcript reflows and repeated page swaps must fit the same pool.
    for (int i = 0; i < 200; ++i) {
        s_page = REVIEW; s.mode = CP_REVIEW;
        for (int n = 0; n < 600; ++n) memcpy(s.view.draft+n*3, "测", 3);
        s.view.draft[1800] = 0;
        render(); lv_obj_update_layout(s_screen);
        assert(strlen(lv_label_get_text(s_body)) == 1800);
        lv_obj_scroll_to_y(s_scroll, i%2 ? 600 : 0, LV_ANIM_OFF);
        lv_refr_now(NULL);
        s_page = HOME; render(); lv_refr_now(NULL);
        assert(lv_mem_test() == LV_RESULT_OK);
    }
    lv_mem_monitor_t memory; lv_mem_monitor(&memory);
    printf("UI navigation and rendering: PASS; LVGL used=%zu free=%zu largest=%zu\n",
           memory.total_size-memory.free_size, memory.free_size, memory.free_biggest_size);
    return 0;
}
