#include "companion_device.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

uint32_t cp_battery_color(int percent) {
    if (percent < 0 || percent > 100) return 0xAFBCCD;
    if (percent <= 20) return 0xFF6B6B;
    if (percent <= 50) return 0xFFD166;
    return 0x55E6B0;
}

void cp_device_text(const cp_device_info_t *d, int64_t now_us, char out[384]) {
    char battery[12]="--", voltage[16]="--", temperature[16]="--";
    char memory[32]="--", storage[32]="--", flash[16]="--";
    if (d->valid) {
        if (d->battery >= 0 && d->battery <= 100) snprintf(battery,sizeof(battery),"%d%%",d->battery);
        if (d->voltage > 0) snprintf(voltage,sizeof(voltage),"%.3f V",d->voltage/1000.0);
        if (d->has_temperature && isfinite(d->temperature))
            snprintf(temperature,sizeof(temperature),"%.1f C",d->temperature);
        if (d->heap_total && d->heap_free <= d->heap_total)
            snprintf(memory,sizeof(memory),"%lu/%lu KiB",(unsigned long)((d->heap_total-d->heap_free)/1024),
                     (unsigned long)(d->heap_total/1024));
        if (d->app_size && d->app_capacity && d->app_size <= d->app_capacity)
            snprintf(storage,sizeof(storage),"%.2f/%.2f MiB",d->app_size/1048576.0,d->app_capacity/1048576.0);
        if (d->flash_size) snprintf(flash,sizeof(flash),"%lu MiB",(unsigned long)(d->flash_size/1048576));
    }
    unsigned long long seconds=now_us > 0 ? (unsigned long long)(now_us/1000000) : 0;
    snprintf(out,384,"电量 %s / %s\n芯片温度 %s\n内存 %s\n存储 %s\n闪存 %s\n固件 %.20s\n运行 %02llu:%02llu:%02llu",
             battery,voltage,temperature,memory,storage,flash,d->valid ? d->version : "--",
             seconds/3600,seconds/60%60,seconds%60);
}

bool cp_device_diagnostic(const cp_device_info_t *d, const char *name, int64_t now_us, char out[384]) {
    if (!d->valid) {
        snprintf(out,384,"设备读数尚未就绪");
        return true;
    }
    long age = now_us >= d->sampled_us ? (long)((now_us-d->sampled_us)/1000000) : 0;
    if (!strcmp(name,"device")) {
        cp_device_text(d,now_us,out);
    } else if (!strcmp(name,"battery")) {
        char temperature[20]="--";
        char battery[12]="--", voltage[16]="--";
        if (d->battery >= 0 && d->battery <= 100) snprintf(battery,sizeof(battery),"%d%%",d->battery);
        if (d->voltage > 0) snprintf(voltage,sizeof(voltage),"%d mV",d->voltage);
        if (d->has_temperature && isfinite(d->temperature))
            snprintf(temperature,sizeof(temperature),"%.1f C",d->temperature);
        snprintf(out,384,"电量 %s\n电压 %s\n芯片温度 %s\n采样 %ld 秒前",
                 battery,voltage,temperature,age);
    } else if (!strcmp(name,"memory")) {
        snprintf(out,384,"内部堆总量 %lu KiB\n空闲 %lu KiB\n历史最少 %lu KiB\n最大连续块 %lu KiB\n任务 %lu\n采样 %ld 秒前",
                 (unsigned long)(d->heap_total/1024),(unsigned long)(d->heap_free/1024),
                 (unsigned long)(d->heap_min/1024),(unsigned long)(d->heap_largest/1024),
                 (unsigned long)d->tasks,age);
    } else if (!strcmp(name,"version")) {
        snprintf(out,384,"模式 %s\n固件 %s\nESP-IDF %s\nELF %.16s…\n运行 %llu 秒",
                 d->profile,d->version,d->idf,d->elf,
                 (unsigned long long)(now_us > 0 ? now_us/1000000 : 0));
    } else return false;
    return true;
}
