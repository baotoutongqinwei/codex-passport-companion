#pragma once
#include "companion_device.h"
#include "lvgl.h"

// One small bar and a terminal, with no font glyph or image allocation.
static inline lv_obj_t *cp_battery_icon_create(lv_obj_t *parent, int x, int y) {
    lv_obj_t *icon = lv_bar_create(parent);
    lv_obj_remove_style_all(icon);
    lv_obj_set_pos(icon, x, y);
    lv_obj_set_size(icon, 14, 10);
    lv_obj_set_style_border_width(icon, 1, 0);
    lv_obj_set_style_radius(icon, 2, 0);
    lv_obj_set_style_pad_all(icon, 2, 0);
    lv_obj_set_style_bg_opa(icon, LV_OPA_COVER, LV_PART_INDICATOR);
    lv_obj_add_flag(icon, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
    lv_obj_t *terminal = lv_obj_create(icon);
    lv_obj_remove_style_all(terminal);
    lv_obj_set_size(terminal, 2, 4);
    lv_obj_set_style_bg_opa(terminal, LV_OPA_COVER, 0);
    lv_obj_align_to(terminal, icon, LV_ALIGN_OUT_RIGHT_MID, 0, 0);
    lv_obj_remove_flag(terminal, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE);
    return icon;
}

static inline void cp_battery_icon_update(lv_obj_t *icon, lv_obj_t *label, int percent) {
    lv_color_t color = lv_color_hex(cp_battery_color(percent));
    lv_obj_set_style_text_color(label, color, 0);
    lv_obj_set_style_border_color(icon, color, 0);
    lv_obj_set_style_bg_color(icon, color, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(lv_obj_get_child(icon, 0), color, 0);
    lv_bar_set_value(icon, percent >= 0 && percent <= 100 ? percent : 0, LV_ANIM_OFF);
}
