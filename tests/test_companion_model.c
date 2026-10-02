#include "companion_model.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    char out[32];
    assert(cp_utf8_copy(out, 5, "中中文") == 3 && strcmp(out, "中") == 0);
    assert(cp_utf8_copy(out, 7, "中中文") == 6 && strcmp(out, "中中") == 0);
    assert(cp_utf8_copy(out, 1, "abc") == 0 && out[0] == 0);
    assert(cp_utf8_copy(out, 0, "abc") == 0);
    cp_utf8_copy(out, sizeof(out), "\xED\xA0\x80"); assert(strcmp(out, "???") == 0);
    cp_utf8_copy(out, sizeof(out), "\xF0\x80\x80\x80"); assert(strcmp(out, "????") == 0);
    cp_utf8_copy(out, sizeof(out), "\xE4\xB8"); assert(strcmp(out, "??") == 0);
    cp_utf8_copy(out, sizeof(out), "A😀中"); assert(strcmp(out, "A😀中") == 0);
    assert(cp_url_encode(out, sizeof(out), "a+/=&?中"));
    assert(strcmp(out, "a%2B%2F%3D%26%3F%E4%B8%AD") == 0);
    assert(!cp_url_encode(out, 4, "++") && !out[0]);
    assert(!cp_url_encode(out, 0, ""));
    assert(cp_valid_url("https://192.168.1.3:8765"));
    assert(!cp_valid_url("http://192.168.1.3:8765"));
    assert(!cp_valid_url("https://"));
    assert(!cp_valid_url("https://host/a?token=x"));
    assert(!cp_valid_url("https://host\nHeader:bad"));
    assert(cp_clamp_page(-1, 4) == 3 && cp_clamp_page(20, 4) == 3);
    assert(cp_clamp_page(1, 4) == 1 && cp_clamp_page(0, 0) == 0);
    cp_clock_text(out, 0, false); assert(strcmp(out, "--:--:--") == 0);
    cp_clock_text(out, -1, true); assert(strcmp(out, "--:--:--") == 0);
    cp_clock_text(out, 45, true); assert(strcmp(out, "08:00:45") == 0);
    cp_clock_text(out, 16*3600-1, true); assert(strcmp(out, "23:59:59") == 0);
    cp_clock_text(out, 16*3600, true); assert(strcmp(out, "00:00:00") == 0);
    cp_clock_text(out, 86400+16*3600+5*60+9, true); assert(strcmp(out, "00:05:09") == 0);
    cp_clock_text(out, INT64_MAX, true); assert(strlen(out) == 8);
    cp_view_t view = {0};
    assert(cp_weekly_window(&view) == -1);
    view.windows[0] = 300; view.windows[1] = 10080;
    assert(cp_weekly_window(&view) == 1);
    view.windows[0] = 10080; view.windows[1] = 0;
    assert(cp_weekly_window(&view) == 0);
    view.windows[0] = 10081;
    assert(cp_weekly_window(&view) == -1);
    cp_date_text(out, 1704038399); assert(strcmp(out, "2023-12-31 23:59") == 0);
    cp_date_text(out, 1704038400); assert(strcmp(out, "2024-01-01 00:00") == 0);
    cp_date_text(out, 1709222399); assert(strcmp(out, "2024-02-29 23:59") == 0);
    cp_date_text(out, 1709222400); assert(strcmp(out, "2024-03-01 00:00") == 0);
    cp_date_text(out, 253402271999LL); assert(strcmp(out, "9999-12-31 23:59") == 0);
    cp_date_text(out, 0); assert(strcmp(out, "--") == 0);
    cp_date_text(out, -1); assert(strcmp(out, "--") == 0);
    cp_date_text(out, INT64_MAX); assert(strcmp(out, "--") == 0);
    puts("Companion UTF-8, URL, pagination, weekly quota and UTC+8 date/clock tests: PASS");
}
