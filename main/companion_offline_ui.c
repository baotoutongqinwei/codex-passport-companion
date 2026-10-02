#include "companion_offline_model.h"
#include "bsp_display.h"
#include "bsp_battery.h"
#include "bsp_button.h"
#include "esp_timer.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lvgl.h"
#include <stdio.h>
#include <string.h>

LV_FONT_DECLARE(passport_font_16);
typedef struct { bsp_btn_t id; bsp_btn_ev_t event; } offline_key_t;
static QueueHandle_t s_keys;
static lv_obj_t *s_screen, *s_clock, *s_battery, *s_title, *s_value, *s_detail, *s_footer;
static cp_focus_t s_focus;
static cp_stopwatch_t s_watch;
static int s_page, s_edit, s_hour, s_minute, s_seconds=-1, s_soc=-1;
static int64_t s_clock_start, s_last_key, s_ignore_until;
static bool s_dark;

static lv_obj_t *label(int x,int y,int width,uint32_t color) {
    lv_obj_t *obj=lv_label_create(s_screen);
    lv_obj_set_pos(obj,x,y); lv_obj_set_width(obj,width);
    lv_obj_set_style_text_font(obj,&passport_font_16,0);
    lv_obj_set_style_text_color(obj,lv_color_hex(color),0);
    return obj;
}
static void create_offline_ui(void) {
    s_screen=lv_obj_create(NULL);
    lv_obj_set_style_bg_color(s_screen,lv_color_hex(0x111B27),0);
    lv_obj_set_style_pad_all(s_screen,0,0); lv_obj_remove_flag(s_screen,LV_OBJ_FLAG_SCROLLABLE);
    s_clock=label(18,12,108,0x83E6C7);
    s_battery=label(174,12,48,0xBFCADA); lv_obj_set_style_text_align(s_battery,LV_TEXT_ALIGN_RIGHT,0);
    s_title=label(20,62,200,0xBFCADA);
    s_value=label(20,112,200,0xFFFFFF);
    lv_obj_set_style_text_align(s_value,LV_TEXT_ALIGN_CENTER,0);
    s_detail=label(20,164,200,0x83E6C7);
    s_footer=label(18,254,204,0xBFCADA);
    lv_screen_load(s_screen);
}
static void render_offline(int64_t now) {
    char text[160], clock[9];
    cp_offline_clock(clock,s_seconds,s_clock_start,now);
    lv_label_set_text(s_clock,clock);
    if (s_soc>=0) snprintf(text,sizeof(text),"%d%%",s_soc); else strcpy(text,"--");
    lv_label_set_text(s_battery,text);
    if (s_edit) {
        lv_label_set_text(s_title,s_edit==1 ? "设置 UTC+8 小时" : "设置 UTC+8 分钟");
        snprintf(text,sizeof(text),"%02d : %02d",s_hour,s_minute); lv_label_set_text(s_value,text);
        lv_label_set_text(s_detail,"24 小时制\n完全断电后需重新校时");
        lv_label_set_text(s_footer,"上下调整 / 中键确认\n长按上取消");
    } else if (s_page==0) {
        lv_label_set_text(s_title,"离线时钟  /  UTC+8"); lv_label_set_text(s_value,clock);
        lv_label_set_text(s_detail,s_seconds<0 ? "按中键设置当前时间\n无需电脑或网络" : "本机时钟正在运行\n上下切换工具");
        lv_label_set_text(s_footer,"中键校时\n上下切换番茄钟和秒表");
    } else if (s_page==1) {
        int64_t left=cp_focus_remaining(&s_focus,now);
        unsigned seconds=(unsigned)((left+999)/1000);
        lv_label_set_text(s_title,s_focus.rest ? "番茄钟  /  休息 5 分钟" : "番茄钟  /  专注 25 分钟");
        snprintf(text,sizeof(text),"%02u : %02u",seconds/60,seconds%60); lv_label_set_text(s_value,text);
        snprintf(text,sizeof(text),"%s\n已完成 %u 轮",s_focus.complete ? "本阶段结束 / 中键继续" : s_focus.running ? "进行中" : "已暂停 / 中键开始",s_focus.cycles);
        lv_label_set_text(s_detail,text); lv_label_set_text(s_footer,"中键开始或暂停\n长按中键重置 / 上下切换");
    } else {
        uint64_t centis=(uint64_t)cp_stopwatch_elapsed(&s_watch,now)/10;
        lv_label_set_text(s_title,"秒表");
        snprintf(text,sizeof(text),"%02llu:%02llu:%02llu.%02llu",(unsigned long long)(centis/360000),
                 (unsigned long long)(centis/6000%60),(unsigned long long)(centis/100%60),(unsigned long long)(centis%100));
        lv_label_set_text(s_value,text);
        lv_label_set_text(s_detail,s_watch.running ? "计时中\n切换页面仍继续" : "已暂停\n中键开始或继续");
        lv_label_set_text(s_footer,"中键开始或暂停\n长按中键清零 / 上下切换");
    }
}
static void offline_key(offline_key_t key,int64_t now) {
    if (key.event==BSP_BTN_RELEASE) return;
    s_last_key=now;
    if (s_dark) { s_dark=false; s_ignore_until=now+700; bsp_display_backlight(75); }
    if (now<s_ignore_until) return;
    if (key.event==BSP_BTN_LONG) {
        if (key.id==BSP_BTN_UP && s_edit) s_edit=0;
        else if (key.id==BSP_BTN_OK && !s_edit) {
            if (s_page==1) memset(&s_focus,0,sizeof(s_focus));
            if (s_page==2) memset(&s_watch,0,sizeof(s_watch));
        }
        return;
    }
    if (key.event!=BSP_BTN_CLICK) return;
    if (s_edit) {
        if (key.id==BSP_BTN_OK) {
            if (s_edit==1) s_edit=2;
            else { s_seconds=s_hour*3600+s_minute*60; s_clock_start=now; s_edit=0; }
        } else {
            int delta=key.id==BSP_BTN_UP ? 1 : -1;
            if (s_edit==1) s_hour=(s_hour+delta+24)%24;
            else s_minute=(s_minute+delta+60)%60;
        }
    } else if (key.id!=BSP_BTN_OK) s_page=(s_page+(key.id==BSP_BTN_DOWN ? 1 : 2))%3;
    else if (s_page==1) cp_focus_toggle(&s_focus,now);
    else if (s_page==2) cp_stopwatch_toggle(&s_watch,now);
    else {
        int64_t seconds=s_seconds<0 ? 0 : (s_seconds+(now-s_clock_start)/1000)%86400;
        s_hour=seconds/3600; s_minute=seconds/60%60; s_edit=1;
    }
}
static void button(bsp_btn_t id,bsp_btn_ev_t event,void *arg) {
    (void)arg; offline_key_t key={id,event}; xQueueSend(s_keys,&key,0);
}
void cp_offline_run(void) {
    s_keys=xQueueCreate(12,sizeof(offline_key_t)); ESP_ERROR_CHECK(s_keys ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(bsp_button_init(button,NULL));
    while (!bsp_lvgl_lock(1000)) vTaskDelay(pdMS_TO_TICKS(20));
    create_offline_ui(); bsp_lvgl_unlock(); bsp_display_backlight(75);
    s_last_key=esp_timer_get_time()/1000; int64_t last_battery=-30000;
    for (;;) {
        int64_t now=esp_timer_get_time()/1000;
        if (now-last_battery>=30000) { s_soc=bsp_battery_soc(); last_battery=now; }
        bool was_complete=s_focus.complete;
        cp_focus_remaining(&s_focus,now);
        if (!was_complete && s_focus.complete) { s_dark=false; s_last_key=now; bsp_display_backlight(75); }
        if (bsp_lvgl_lock(50)) {
            offline_key_t key;
            while (xQueueReceive(s_keys,&key,0)==pdTRUE) offline_key(key,now);
            render_offline(now); bsp_lvgl_unlock();
        }
        if (!s_dark && now-s_last_key>60000) { s_dark=true; bsp_display_backlight(0); }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
