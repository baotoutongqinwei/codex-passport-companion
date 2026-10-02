#include "../../main/companion_offline_ui.c"
#include <stdlib.h>

static uint16_t pixels[240*320];
static _Alignas(16) uint16_t draw_buffer[240*40];
esp_err_t bsp_button_init(bsp_btn_cb_t cb, void *arg) { (void)cb; (void)arg; return ESP_OK; }
bool bsp_lvgl_lock(int timeout) { (void)timeout; return true; }
void bsp_lvgl_unlock(void) {}
void bsp_display_backlight(uint8_t percent) { (void)percent; }
int bsp_battery_soc(void) { return 86; }
static void flush(lv_display_t *display,const lv_area_t *area,uint8_t *data) {
    uint16_t *source=(uint16_t *)data;
    for (int y=area->y1;y<=area->y2;++y) for (int x=area->x1;x<=area->x2;++x) pixels[y*240+x]=*source++;
    lv_display_flush_ready(display);
}
static void screenshot(const char *dir,const char *name,int64_t now) {
    render_offline(now); lv_obj_update_layout(s_screen);
    assert(lv_obj_get_style_text_font(s_detail,0)==&passport_font_16);
    assert(lv_obj_get_height(s_footer)<=48);
    assert(lv_obj_get_y(s_footer)+lv_obj_get_height(s_footer)<=310);
    assert(lv_obj_get_height(s_value)<=24);
    lv_obj_invalidate(s_screen); lv_refr_now(NULL);
    char path[1024]; snprintf(path,sizeof(path),"%s/%s.ppm",dir,name);
    FILE *file=fopen(path,"wb"); assert(file); fprintf(file,"P6\n240 320\n255\n");
    for (int y=0;y<320;++y) for (int x=0;x<240;++x) {
        uint16_t value=pixels[y*240+x];
        int dx=x<30 ? 30-x : x>=210 ? x-209 : 0;
        int dy=y<30 ? 30-y : y>=290 ? y-289 : 0;
        if (dx*dx+dy*dy>900 && dx && dy) value=0;
        unsigned char rgb[]={(unsigned char)(((value>>11)&31)*255/31),
            (unsigned char)(((value>>5)&63)*255/63),(unsigned char)((value&31)*255/31)};
        fwrite(rgb,1,3,file);
    }
    fclose(file);
}
int main(int argc,char **argv) {
    assert(argc==2); lv_init();
    lv_display_t *display=lv_display_create(240,320);
    lv_display_set_buffers(display,draw_buffer,NULL,sizeof(draw_buffer),LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(display,flush);
    create_offline_ui(); s_soc=86;
    screenshot(argv[1],"10-offline-unset",0);
    assert(!strcmp(lv_label_get_text(s_clock),"--:--:--"));
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_CLICK},1000); assert(s_edit==1);
    for (int i=0;i<8;++i) offline_key((offline_key_t){BSP_BTN_UP,BSP_BTN_CLICK},1000);
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_CLICK},1000); assert(s_edit==2);
    for (int i=0;i<30;++i) offline_key((offline_key_t){BSP_BTN_UP,BSP_BTN_CLICK},1000);
    screenshot(argv[1],"11-offline-set",1000);
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_CLICK},1000);
    screenshot(argv[1],"12-offline-clock",2000);
    assert(!strcmp(lv_label_get_text(s_clock),"08:30:01"));
    offline_key((offline_key_t){BSP_BTN_DOWN,BSP_BTN_CLICK},2000); assert(s_page==1);
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_CLICK},2000);
    screenshot(argv[1],"13-offline-focus",62000);
    offline_key((offline_key_t){BSP_BTN_DOWN,BSP_BTN_CLICK},62000); assert(s_page==2);
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_CLICK},62000);
    screenshot(argv[1],"14-offline-stopwatch",75230);
    s_page=1;
    screenshot(argv[1],"15-offline-complete",1502000); assert(s_focus.complete);
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_CLICK},1502000);
    screenshot(argv[1],"16-offline-rest",1503000); assert(s_focus.rest);
    s_dark=true; s_page=2;
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_PRESS},1600000);
    offline_key((offline_key_t){BSP_BTN_OK,BSP_BTN_LONG},1600100);
    assert(s_watch.running); // Wake press must not reset the stopwatch.
    for (int i=0;i<500;++i) { s_page=i%3; render_offline(1600000+i*50); lv_refr_now(NULL); assert(lv_mem_test()==LV_RESULT_OK); }
    lv_mem_monitor_t memory; lv_mem_monitor(&memory);
    printf("Offline UI controls/rendering: PASS; LVGL used=%zu free=%zu\n",memory.total_size-memory.free_size,memory.free_size);
}
