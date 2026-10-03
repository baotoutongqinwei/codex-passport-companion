#include "companion_battery_log_model.h"
#include "companion_model.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    cp_battery_log_t log;
    cp_battery_log_init(&log,42);
    assert(cp_battery_log_valid(&log) && sizeof(log)==3088);
    assert(cp_battery_log_due(&log,1,95));
    cp_battery_log_add(&log,1791000000,1,95,4120);
    assert(!cp_battery_log_due(&log,60,95));
    assert(cp_battery_log_due(&log,61,92)); // Abrupt three-point drop.
    assert(cp_battery_log_due(&log,301,95));
    cp_battery_log_add(&log,1791000300,301,9,3700);
    assert(!cp_battery_log_due(&log,350,9));
    assert(cp_battery_log_due(&log,361,9)); // One-minute low-battery sampling.
    for (int i=0;i<CP_BATTERY_LOG_CAPACITY+9;i++)
        cp_battery_log_add(&log,1791000400+i,400+i,8,3600);
    assert(log.count==CP_BATTERY_LOG_CAPACITY);
    cp_battery_sample_t first,last;
    assert(cp_battery_log_at(&log,0,&first));
    assert(cp_battery_log_at(&log,log.count-1,&last));
    assert(last.sequence-first.sequence==CP_BATTERY_LOG_CAPACITY-1);
    assert(!cp_battery_log_at(&log,log.count,&last));
    char line[96];
    assert(cp_battery_log_line(&log,0,line,sizeof(line))>0);
    assert(strstr(line,"CPBAT1:D,")==line);
    assert(cp_battery_log_line(&log,0,line,5)==-1);
    cp_battery_sample_t page[CP_BATTERY_UPLOAD_COUNT];
    uint32_t cursor=0;
    unsigned total=0, count;
    while ((count=cp_battery_log_page(&log,cursor,page))>0) {
        assert(count<=16 && page[0].sequence>cursor);
        char packet[1536];
        assert(cp_battery_log_packet(page,count,"AA:BB:CC:DD:EE:FF",log.log_id,true,packet,sizeof(packet))>0);
        assert(strstr(packet,"\"storage_ok\":true"));
        assert(strstr(packet,"\"samples\":[["));
        assert(cp_battery_log_packet(page,count,"AA:BB:CC:DD:EE:FF",log.log_id,true,packet,20)==-1);
        assert(cp_battery_log_packet(page,count,"invalid",log.log_id,true,packet,sizeof(packet))==-1);
        total+=count; cursor=page[count-1].sequence;
    }
    assert(total==192 && cursor==last.sequence);
    assert(cp_battery_log_page(&log,cursor,page)==0);
    // A reconnect/restart replays the retained ring, including its oldest entry.
    assert(cp_battery_log_page(&log,0,page)==16 && page[0].sequence==first.sequence);
    log.magic=0;
    assert(!cp_battery_log_valid(&log));
    // A retained draft and screen-off still produce the usual five-minute log.
    cp_battery_log_init(&log,43);
    unsigned dark_samples=0;
    for (uint32_t seconds=0;seconds<=3600;seconds+=30) {
        if (cp_telemetry_allowed(CP_REVIEW) && cp_battery_log_due(&log,seconds,80)) {
            cp_battery_log_add(&log,1791000000+seconds,seconds,80,4000);
            if (cp_screen_should_dim(CP_REVIEW,(int64_t)seconds*1000000)) ++dark_samples;
        }
    }
    assert(log.count==13 && dark_samples==12);
    assert(cp_battery_log_at(&log,12,&last) && last.uptime_s==3600);
    puts("Battery log ring, interval and export: PASS");
}
