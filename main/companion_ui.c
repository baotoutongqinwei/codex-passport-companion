#include "companion.h"
#include "companion_transport.h"
#include "bsp_button.h"
#include "bsp_display.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lvgl.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

LV_FONT_DECLARE(passport_font_16);
typedef enum { HOME, THREADS, CHAT, MENU, REVIEW, RECORD, SETTINGS } page_t;
typedef struct { bsp_btn_t id; bsp_btn_ev_t event; } cp_key_t;
static QueueHandle_t s_keys;
static cp_state_t s;
static page_t s_page = HOME;
static cp_mode_t s_previous_mode;
static int s_choice;
static char s_thread[CP_ID_SIZE], s_cursor[CP_CURSOR_SIZE];
static lv_obj_t *s_screen, *s_title, *s_status, *s_battery, *s_footer, *s_clock;
static lv_obj_t *s_rows[4], *s_row_text[4], *s_bar, *s_quota;
static lv_obj_t *s_auto_title, *s_auto_date, *s_reset_title, *s_reset_dates[2];
static lv_obj_t *s_scroll, *s_body;
static bool s_dark;
static int64_t s_last_key, s_ignore_until;

static void button(bsp_btn_t id, bsp_btn_ev_t event, void *arg) {
    (void)arg;
    cp_key_t key = {id, event};
    xQueueSend(s_keys, &key, 0);
}

static void text(lv_obj_t *label, const char *value) {
    if (strcmp(lv_label_get_text(label), value) != 0) lv_label_set_text(label, value);
}

static void visible(lv_obj_t *obj, bool show) {
    if (show) lv_obj_remove_flag(obj, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
}

static lv_obj_t *label(lv_obj_t *parent, int x, int y, int width, uint32_t color) {
    lv_obj_t *obj = lv_label_create(parent);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_width(obj, width);
    lv_obj_set_style_text_font(obj, &passport_font_16, 0);
    lv_obj_set_style_text_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_text_line_space(obj, 2, 0);
    lv_label_set_text(obj, "");
    return obj;
}

static void create_ui(void) {
    s_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(s_screen, lv_color_hex(0x0F1922), 0);
    lv_obj_set_style_pad_all(s_screen, 0, 0);
    lv_obj_remove_flag(s_screen, LV_OBJ_FLAG_SCROLLABLE);
    s_clock = label(s_screen, 18, 12, 84, 0x55E6B0);
    text(s_clock, "--:--:--");
    lv_obj_t *brand = label(s_screen, 109, 12, 60, 0xAFBCCD);
    text(brand, "CODEX");
    s_battery = label(s_screen, 178, 12, 48, 0xAFBCCD);
    s_title = label(s_screen, 18, 42, 206, 0xFFFFFF);
    lv_label_set_long_mode(s_title, LV_LABEL_LONG_DOT);
    s_status = label(s_screen, 18, 67, 206, 0xAFBCCD);
    lv_label_set_long_mode(s_status, LV_LABEL_LONG_DOT);
    for (int i = 0; i < 4; ++i) {
        s_rows[i] = lv_obj_create(s_screen);
        lv_obj_set_pos(s_rows[i], 12, 94+i*43);
        lv_obj_set_size(s_rows[i], 216, 39);
        lv_obj_set_style_radius(s_rows[i], 9, 0);
        lv_obj_set_style_border_width(s_rows[i], 0, 0);
        lv_obj_set_style_pad_all(s_rows[i], 0, 0);
        lv_obj_remove_flag(s_rows[i], LV_OBJ_FLAG_SCROLLABLE);
        s_row_text[i] = label(s_rows[i], 9, 8, 198, 0xFFFFFF);
        lv_label_set_long_mode(s_row_text[i], LV_LABEL_LONG_DOT);
    }
    s_quota = label(s_screen, 18, 100, 204, 0xFFFFFF);
    s_bar = lv_bar_create(s_screen);
    lv_obj_set_pos(s_bar, 18, 130);
    lv_obj_set_size(s_bar, 204, 9);
    lv_obj_set_style_bg_color(s_bar, lv_color_hex(0x263848), 0);
    lv_obj_set_style_bg_color(s_bar, lv_color_hex(0x55E6B0), LV_PART_INDICATOR);
    s_auto_title = label(s_screen, 18, 150, 204, 0xAFBCCD);
    text(s_auto_title, "自动重置 UTC+8");
    s_auto_date = label(s_screen, 18, 174, 204, 0xFFFFFF);
    s_reset_title = label(s_screen, 18, 206, 204, 0xAFBCCD);
    lv_label_set_long_mode(s_reset_title, LV_LABEL_LONG_DOT);
    for (int i = 0; i < 2; ++i)
        s_reset_dates[i] = label(s_screen, 18, 231+i*24, 204, 0xFFFFFF);
    s_scroll = lv_obj_create(s_screen);
    lv_obj_set_pos(s_scroll, 18, 94);
    lv_obj_set_size(s_scroll, 204, 176);
    lv_obj_set_style_bg_opa(s_scroll, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(s_scroll, 0, 0);
    lv_obj_set_style_pad_all(s_scroll, 0, 0);
    lv_obj_set_scroll_dir(s_scroll, LV_DIR_VER);
    s_body = label(s_scroll, 0, 0, 204, 0xF1F5FA);
    s_footer = label(s_screen, 24, 271, 192, 0xAFBCCD);
    lv_obj_set_style_text_line_space(s_footer, 0, 0);
    lv_obj_set_style_text_font(s_footer, &passport_font_16, 0);
    lv_screen_load(s_screen);
}

static const char *run_status(const char *status) {
    if (strcmp(status, "active") == 0) return "Codex 正在处理";
    if (strcmp(status, "needsDesktop") == 0) return "需在电脑处理权限";
    if (strcmp(status, "error") == 0) return "执行出错，请查看电脑";
    return "长按中键说话";
}

static void render(void) {
    char value[180];
    char clock[9];
    cp_clock_text(clock, (int64_t)time(NULL), s.clock_synced);
    text(s_clock, clock);
    if (s.battery >= 0) snprintf(value, sizeof(value), "%d%%", s.battery);
    else strcpy(value, "--");
    text(s_battery, value);
    char connecting[48]; snprintf(connecting,sizeof(connecting),"正在连接 %s",cp_transport_name());
    const char *status = !s.configured ? "等待 USB 配置" : !s.wifi ? connecting :
                         !s.bridge ? "等待 Mac 桥接服务" : "已连接 Mac";
    text(s_status, s.message[0] ? s.message : status);
    for (int i = 0; i < 4; ++i) {
        visible(s_rows[i], s_page == MENU || (s_page == THREADS && i < s.view.count));
        lv_obj_set_style_bg_color(s_rows[i], lv_color_hex(i == s_choice ? 0x2F6156 : 0x1B2A38), 0);
    }
    visible(s_quota, s_page == HOME);
    visible(s_bar, s_page == HOME);
    visible(s_auto_title, s_page == HOME);
    visible(s_auto_date, s_page == HOME);
    visible(s_reset_title, s_page == HOME);
    for (int i = 0; i < 2; ++i) visible(s_reset_dates[i], s_page == HOME);
    visible(s_scroll, s_page != HOME && s_page != MENU && s_page != THREADS);
    lv_obj_set_y(s_footer, s_page == HOME ? 289 : 271);
    if (s_page == HOME) {
        text(s_title, "额度概览");
        int weekly = cp_weekly_window(&s.view);
        int remaining = weekly >= 0 ? s.view.remaining[weekly] : -1;
        if (remaining < 0) strcpy(value, "7 天额度  未知");
        else snprintf(value, sizeof(value), "7 天额度  剩余 %d%%", remaining);
        text(s_quota, value);
        lv_bar_set_value(s_bar, remaining < 0 ? 0 : remaining, LV_ANIM_OFF);
        int64_t now = (int64_t)time(NULL);
        int64_t reset = weekly >= 0 ? s.view.reset[weekly] : 0;
        char date[17];
        cp_date_text(date, reset);
        text(s_auto_date, reset > 0 && s.clock_synced && reset <= now ? "等待额度刷新" : date);
        if (!s.view.updated || s.view.reset_credit_count < 0) strcpy(value, "重置机会到期时间");
        else if (!s.view.reset_credit_details_complete && s.view.reset_credit_count > 0)
            strcpy(value, "重置到期（详情不全）");
        else snprintf(value, sizeof(value), "重置到期  可用 %d 次", s.view.reset_credit_count);
        text(s_reset_title, value);
        for (int i = 0; i < 2; ++i) {
            int64_t expiry = s.view.reset_credit_expiry[i];
            cp_date_text(date, expiry);
            const char *expiry_text = expiry > 0 ?
                (s.clock_synced && expiry <= now ? "已到期，等待刷新" : date) : "";
            if (!i && !expiry) expiry_text = !s.view.updated || s.view.reset_credit_count < 0 ? "等待数据" :
                s.view.reset_credit_count == 0 ? "暂无可用重置机会" :
                !s.view.reset_credit_details_complete ? "到期时间暂不可用" : "无固定到期时间";
            text(s_reset_dates[i], expiry_text);
        }
        if (s.bridge && !s.message[0] && (!s.view.updated || now-s.view.updated > 90))
            text(s_status, "额度待刷新");
        text(s_footer, "中键对话 / 长按下连接");
    } else if (s_page == THREADS) {
        text(s_title, s.view.count ? "选择对话" : "暂无可用对话");
        for (int i = 0; i < s.view.count; ++i) text(s_row_text[i], s.view.threads[i].title);
        text(s_footer, "上下选择 / 中键打开\n长按下翻页 / 长按上返回");
    } else if (s_page == MENU) {
        static const char *items[] = {"最新回复", "切换对话", "额度概览", "返回对话"};
        text(s_title, "对话操作");
        for (int i = 0; i < 4; ++i) text(s_row_text[i], items[i]);
        text(s_footer, "上下选择 / 中键确认");
    } else if (s_page == CHAT) {
        bool matched = strcmp(s.view.id, s_thread) == 0;
        text(s_title, matched ? s.view.title : "正在打开对话");
        if (!s.message[0] && s.bridge) text(s_status, matched ? run_status(s.view.status) : "正在同步");
        text(s_body, matched ? s.view.body : "请稍候");
        snprintf(value, sizeof(value), "%d/%d 页 | 中键菜单\n长按中键说话，松开识别", matched ? s.view.page+1 : 0, matched ? s.view.pages : 0);
        text(s_footer, value);
    } else if (s_page == RECORD) {
        text(s_title, s.mode == CP_STARTING ? "准备录音" : "正在聆听");
        snprintf(value, sizeof(value), "\n\n%u / 45 秒\n\n松开中键结束\n识别后确认发送", s.recorded_ms/1000);
        text(s_body, value);
        text(s_footer, "请靠近卡片麦克风");
    } else if (s_page == REVIEW) {
        text(s_title, s.mode == CP_TRANSCRIBING ? "本机识别中" : s.mode == CP_SENDING ? "正在发送" : "确认语音内容");
        text(s_body, s.mode == CP_TRANSCRIBING ? "正在 Mac 离线识别\n请稍候，不会自动发送" : s.view.draft);
        bool ready = strcmp(s.view.draft_state, "ready") == 0;
        text(s_footer, s.mode == CP_SENDING ? "正在等待 Mac 确认\n请勿重复发送" : ready ? "中键发送 / 上下滚动\n长按上取消" : "长按上取消并返回");
    } else {
        text(s_title, "连接你的 Mac");
        text(s_body, cp_transport_help());
        text(s_footer, "中键返回额度页\n一分钟无操作自动熄屏");
    }
    int passkey=cp_transport_passkey();
    if (passkey>=0) {
        for (int i=0;i<4;++i) visible(s_rows[i],false);
        visible(s_bar,false); visible(s_quota,false);
        visible(s_auto_title,false); visible(s_auto_date,false); visible(s_reset_title,false);
        for (int i=0;i<2;++i) visible(s_reset_dates[i],false);
        visible(s_scroll,true);
        lv_obj_set_y(s_footer,271);
        text(s_title,"蓝牙安全配对"); text(s_status,"在 Mac 输入以下配对码");
        snprintf(value,sizeof(value),"\n\n     %06d\n\n仅在自己的 Mac 确认",passkey);
        text(s_body,value); text(s_footer,"等待 Mac 确认");
    }
}

static void open_threads(void) {
    s_cursor[0] = 0; s_choice = 0; s_page = THREADS;
    cp_select(s_thread, s_cursor, -1);
}

static void handle(cp_key_t key) {
    int64_t now = esp_timer_get_time();
    if (key.id == BSP_BTN_OK && key.event == BSP_BTN_RELEASE) cp_record_stop();
    if (s_dark) {
        s_dark = false; bsp_display_backlight(75); s_ignore_until = now+700000;
    }
    s_last_key = now;
    if (now < s_ignore_until) return;
    if (cp_transport_passkey()>=0) return;
    if (s.mode == CP_SENDING) return;
    if (key.event == BSP_BTN_LONG) {
        if (key.id == BSP_BTN_UP) {
            if (s.mode != CP_IDLE) cp_cancel();
            s_page = s_thread[0] && (s_page == REVIEW || s_page == RECORD) ? CHAT : HOME;
        } else if (key.id == BSP_BTN_DOWN && s_page == THREADS && s.view.next[0]) {
            cp_utf8_copy(s_cursor, sizeof(s_cursor), s.view.next); s_choice = 0;
            cp_select(s_thread, s_cursor, -1);
        } else if (key.id == BSP_BTN_DOWN && s_page == CHAT) cp_select(s_thread, s_cursor, -1);
        else if (key.id == BSP_BTN_DOWN && s_page == HOME) s_page = SETTINGS;
        else if (key.id == BSP_BTN_OK && s_page == CHAT) cp_record_start();
        else if (key.id == BSP_BTN_OK && s_page == SETTINGS) cp_transport_forget_bonds();
        return;
    }
    if (key.event != BSP_BTN_CLICK) return;
    if (s_page == HOME) {
        if (key.id == BSP_BTN_OK) open_threads();
    } else if (s_page == THREADS || s_page == MENU) {
        int count = s_page == MENU ? 4 : s.view.count;
        if (!count) return;
        if (key.id == BSP_BTN_UP) s_choice = (s_choice+count-1)%count;
        if (key.id == BSP_BTN_DOWN) s_choice = (s_choice+1)%count;
        if (key.id == BSP_BTN_OK) {
            if (s_page == THREADS) {
                cp_utf8_copy(s_thread, sizeof(s_thread), s.view.threads[s_choice].id);
                cp_select(s_thread, s_cursor, -1); s_page = CHAT;
            } else if (s_choice == 1) open_threads();
            else if (s_choice == 2) s_page = HOME;
            else { s_page = CHAT; if (s_choice == 0) cp_select(s_thread, s_cursor, -1); }
            lv_obj_scroll_to_y(s_scroll, 0, LV_ANIM_OFF);
        }
    } else if (s_page == CHAT) {
        if (key.id == BSP_BTN_OK) { s_page = MENU; s_choice = 0; }
        else if (strcmp(s.view.id, s_thread) == 0) {
            int page = s.view.page + (key.id == BSP_BTN_UP ? -1 : 1);
            if (page < 0) page = 0;
            cp_select(s_thread, s_cursor, cp_clamp_page(page, s.view.pages));
            lv_obj_scroll_to_y(s_scroll, 0, LV_ANIM_OFF);
        }
    } else if (s_page == SETTINGS) {
        if (key.id == BSP_BTN_OK) s_page = HOME;
        else lv_obj_scroll_by(s_scroll, 0, key.id == BSP_BTN_UP ? 100 : -100, LV_ANIM_OFF);
    } else if (s_page == REVIEW) {
        if (key.id == BSP_BTN_OK && s.mode == CP_REVIEW && strcmp(s.view.draft_state, "ready") == 0) cp_send_draft();
        else if (key.id != BSP_BTN_OK) lv_obj_scroll_by(s_scroll, 0, key.id == BSP_BTN_UP ? 100 : -100, LV_ANIM_OFF);
    }
}

void cp_ui_run(void) {
    s_keys = xQueueCreate(16, sizeof(cp_key_t));
    ESP_ERROR_CHECK(s_keys ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(bsp_button_init(button, NULL));
    while (!bsp_lvgl_lock(1000)) vTaskDelay(pdMS_TO_TICKS(20));
    create_ui();
    bsp_lvgl_unlock();
    bsp_display_backlight(75);
    s_last_key = esp_timer_get_time();
    int64_t rendered = 0;
    for (;;) {
        cp_state_snapshot(&s);
        int64_t now = esp_timer_get_time();
        if (cp_transport_passkey()>=0) {
            s_last_key=now;
            if (s_dark) { s_dark=false; bsp_display_backlight(75); }
        }
        if (s.mode != s_previous_mode) {
            if (s.mode == CP_STARTING || s.mode == CP_RECORDING) s_page = RECORD;
            else if (s.mode != CP_IDLE) {
                s_page = REVIEW;
                if (s.view.draft_thread[0]) cp_utf8_copy(s_thread, sizeof(s_thread), s.view.draft_thread);
            }
            else if (s_previous_mode != CP_IDLE) s_page = CHAT;
            s_previous_mode = s.mode;
        }
        if (bsp_lvgl_lock(50)) {
            cp_key_t key;
            while (xQueueReceive(s_keys, &key, 0) == pdTRUE) handle(key);
            if (now-rendered > 250000) { render(); rendered = now; }
            bsp_lvgl_unlock();
        }
        if (!s_dark && s.mode == CP_IDLE && now-s_last_key > 60000000) { bsp_display_backlight(0); s_dark = true; }
        vTaskDelay(pdMS_TO_TICKS(40));
    }
}
