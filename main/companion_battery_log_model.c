#include "companion_battery_log_model.h"
#include <stdio.h>
#include <string.h>

_Static_assert(sizeof(cp_battery_sample_t)==16, "Battery samples must stay compact");
_Static_assert(sizeof(cp_battery_log_t)==16+16*CP_BATTERY_LOG_CAPACITY, "NVS blob size changed");

void cp_battery_log_init(cp_battery_log_t *log, uint32_t log_id) {
    memset(log,0,sizeof(*log));
    log->magic=CP_BATTERY_LOG_MAGIC;
    log->log_id=log_id ? log_id : 1;
    log->next_sequence=1;
}

bool cp_battery_log_valid(const cp_battery_log_t *log) {
    return log->magic==CP_BATTERY_LOG_MAGIC && log->log_id && log->next_sequence &&
           log->count<=CP_BATTERY_LOG_CAPACITY && log->next_index<CP_BATTERY_LOG_CAPACITY;
}

bool cp_battery_log_at(const cp_battery_log_t *log, unsigned ordinal, cp_battery_sample_t *sample) {
    if (!cp_battery_log_valid(log) || ordinal>=log->count) return false;
    unsigned oldest=(log->next_index+CP_BATTERY_LOG_CAPACITY-log->count)%CP_BATTERY_LOG_CAPACITY;
    *sample=log->samples[(oldest+ordinal)%CP_BATTERY_LOG_CAPACITY];
    return true;
}

bool cp_battery_log_due(const cp_battery_log_t *log, uint32_t uptime_s, int percent) {
    cp_battery_sample_t last;
    if (!cp_battery_log_at(log,log->count ? log->count-1 : 0,&last)) return true;
    // A new boot has a lower uptime. Record its first valid reading promptly.
    if (uptime_s<last.uptime_s) return true;
    uint32_t elapsed=uptime_s-last.uptime_s;
    if (elapsed>=300) return true;
    if (percent>=0 && percent<=10 && elapsed>=60) return true;
    return percent>=0 && last.percent>=0 && last.percent-percent>=3 && elapsed>=30;
}

void cp_battery_log_add(cp_battery_log_t *log, uint32_t utc_s, uint32_t uptime_s,
                        int percent, int voltage_mv) {
    cp_battery_sample_t sample={.sequence=log->next_sequence++, .utc_s=utc_s,
                                .uptime_s=uptime_s,
                                .voltage_mv=voltage_mv>=2500 && voltage_mv<=5500 ? voltage_mv : -1,
                                .percent=percent>=0 && percent<=100 ? percent : -1};
    log->samples[log->next_index]=sample;
    log->next_index=(log->next_index+1)%CP_BATTERY_LOG_CAPACITY;
    if (log->count<CP_BATTERY_LOG_CAPACITY) ++log->count;
}

int cp_battery_log_line(const cp_battery_log_t *log, unsigned ordinal, char *out, size_t capacity) {
    cp_battery_sample_t sample;
    if (!cp_battery_log_at(log,ordinal,&sample)) return -1;
    int used=snprintf(out,capacity,"CPBAT1:D,%lu,%lu,%lu,%d,%d\n",
                      (unsigned long)sample.sequence,(unsigned long)sample.utc_s,
                      (unsigned long)sample.uptime_s,sample.percent,sample.voltage_mv);
    return used>=0 && (size_t)used<capacity ? used : -1;
}

unsigned cp_battery_log_page(const cp_battery_log_t *log, uint32_t after,
                             cp_battery_sample_t out[CP_BATTERY_UPLOAD_COUNT]) {
    unsigned count=0;
    if (!cp_battery_log_valid(log)) return 0;
    for (unsigned i=0; i<log->count && count<CP_BATTERY_UPLOAD_COUNT; ++i) {
        cp_battery_sample_t sample;
        if (cp_battery_log_at(log,i,&sample) && sample.sequence>after) out[count++]=sample;
    }
    return count;
}

int cp_battery_log_packet(const cp_battery_sample_t *samples, unsigned count,
                          const char *identity, uint32_t log_id, bool healthy,
                          char *out, size_t capacity) {
    if (count>CP_BATTERY_UPLOAD_COUNT || strlen(identity)!=17) return -1;
    // The factory MAC is the same stable identifier exposed by USB serial.
    for (unsigned i=0;i<17;++i) {
        char c=identity[i];
        if (i%3==2 ? c!=':' : !((c>='0' && c<='9') || (c>='A' && c<='F'))) return -1;
    }
    int used=snprintf(out,capacity,"{\"card_serial\":\"%s\",\"log_id\":%lu,\"storage_ok\":%s,\"samples\":[",
                      identity,(unsigned long)log_id,healthy ? "true" : "false");
    if (used<0 || (size_t)used>=capacity) return -1;
    for (unsigned i=0;i<count;++i) {
        const cp_battery_sample_t *s=&samples[i];
        int n=snprintf(out+used,capacity-used,"%s[%lu,%lu,%lu,%d,%d]",i ? "," : "",
                       (unsigned long)s->sequence,(unsigned long)s->utc_s,
                       (unsigned long)s->uptime_s,s->percent,s->voltage_mv);
        if (n<0 || (size_t)n>=capacity-used) return -1;
        used+=n;
    }
    if ((size_t)used+3>capacity) return -1;
    memcpy(out+used,"]}",3);
    return used+2;
}
