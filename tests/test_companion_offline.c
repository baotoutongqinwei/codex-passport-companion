#include "companion_offline_model.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    char clock[9];
    cp_offline_clock(clock,-1,0,10000); assert(!strcmp(clock,"--:--:--"));
    cp_offline_clock(clock,86399,1000,2000); assert(!strcmp(clock,"00:00:00"));
    cp_offline_clock(clock,0,0,864001000); assert(!strcmp(clock,"00:00:01"));
    cp_offline_clock(clock,3600,2000,1000); assert(!strcmp(clock,"01:00:00"));
    int seconds; int64_t since, epoch;
    assert(cp_offline_usb_time("CPCLK1:1704067199500",&epoch,&seconds,&since,1000));
    assert(epoch==1704067199500LL && seconds==28799 && since==500);
    cp_offline_clock(clock,seconds,since,1500); assert(!strcmp(clock,"08:00:00"));
    assert(!cp_offline_usb_time("CPCLK1:170406719950x",&epoch,&seconds,&since,1000));
    assert(!cp_offline_usb_time("CPCLK1:0000000000000",&epoch,&seconds,&since,1000));
    cp_focus_t f={0};
    assert(cp_focus_remaining(&f,9000000)==1500000);
    cp_focus_toggle(&f,1000); assert(f.running);
    cp_focus_toggle(&f,101000); assert(!f.running);
    assert(cp_focus_remaining(&f,999000)==1400000);
    cp_focus_toggle(&f,1000000);
    assert(cp_focus_remaining(&f,2399999)==1);
    assert(cp_focus_remaining(&f,2400000)==0 && f.complete && f.cycles==1 && !f.running);
    assert(cp_focus_remaining(&f,9999999)==0 && f.cycles==1);
    cp_focus_toggle(&f,10000000); assert(f.rest && f.running && !f.complete);
    assert(cp_focus_remaining(&f,10300000)==0 && f.cycles==1);
    cp_focus_toggle(&f,10400000); assert(!f.rest && f.running);
    assert(cp_focus_remaining(&f,11900000)==0 && f.cycles==2);
    cp_stopwatch_t w={0};
    cp_stopwatch_toggle(&w,1000);
    assert(cp_stopwatch_elapsed(&w,1123)==123);
    cp_stopwatch_toggle(&w,1123);
    assert(cp_stopwatch_elapsed(&w,99999)==123);
    cp_stopwatch_toggle(&w,100000);
    assert(cp_stopwatch_elapsed(&w,86400100000LL)==86400000123LL);
    puts("Offline clock, focus and stopwatch: PASS");
}
