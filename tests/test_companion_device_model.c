#include "companion_device.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    assert(cp_battery_color(-1)==0xAFBCCD && cp_battery_color(101)==0xAFBCCD);
    assert(cp_battery_color(0)==0xFF6B6B && cp_battery_color(20)==0xFF6B6B);
    assert(cp_battery_color(21)==0xFFD166 && cp_battery_color(50)==0xFFD166);
    assert(cp_battery_color(51)==0x55E6B0 && cp_battery_color(100)==0x55E6B0);
    char text[384];
    cp_device_info_t d={0};
    cp_device_text(&d,0,text);
    assert(strstr(text,"电量 -- / --"));
    assert(strstr(text,"芯片温度 --"));
    assert(strstr(text,"内存 --"));
    assert(strstr(text,"固件 --"));
    d=(cp_device_info_t){.valid=true,.battery=0,.voltage=3600,.has_temperature=true,.temperature=30.5f,
        .heap_total=204800,.heap_free=51200,.app_size=2621440,.app_capacity=8323072,.flash_size=8388608};
    strcpy(d.version,"0.9.0");
    cp_device_text(&d,90061000000LL,text);
    assert(strstr(text,"电量 0% / 3.600 V"));
    assert(strstr(text,"芯片温度 30.5 C"));
    assert(strstr(text,"内存 150/200 KiB"));
    assert(strstr(text,"存储 2.50/7.94 MiB"));
    assert(strstr(text,"闪存 8 MiB"));
    assert(strstr(text,"固件 0.9.0"));
    assert(strstr(text,"运行 25:01:01"));
    int lines=1; for (const char *p=text;*p;++p) lines+=*p=='\n';
    assert(lines==7);
    d.battery=-1; d.voltage=-1; d.temperature=NAN;
    d.heap_free=d.heap_total+1; d.app_size=d.app_capacity+1;
    cp_device_text(&d,0,text);
    assert(strstr(text,"电量 -- / --"));
    assert(strstr(text,"芯片温度 --"));
    assert(strstr(text,"内存 --"));
    assert(strstr(text,"存储 --"));
    assert(cp_device_diagnostic(&d,"battery",10000000,text));
    assert(strstr(text,"电量 --"));
    assert(strstr(text,"芯片温度 --"));
    assert(cp_device_diagnostic(&d,"memory",10000000,text));
    assert(strstr(text,"内部堆总量 200 KiB"));
    assert(cp_device_diagnostic(&d,"version",10000000,text));
    assert(strstr(text,"固件 0.9.0"));
    assert(!cp_device_diagnostic(&d,"erase",10000000,text));
    puts("Card device measurements and formatting: PASS");
}
