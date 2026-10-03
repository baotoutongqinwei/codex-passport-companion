#include "companion_offline_model.h"
#include <stdio.h>
#include <string.h>

static int64_t elapsed(int64_t start, int64_t now) { return now > start ? now-start : 0; }
int64_t cp_focus_remaining(cp_focus_t *f, int64_t now) {
    int64_t duration = (f->rest ? 5 : 25)*60*1000;
    int64_t used = f->accumulated_ms + (f->running ? elapsed(f->started_ms,now) : 0);
    if (used >= duration) {
        if (!f->complete && !f->rest) ++f->cycles;
        f->complete=true; f->running=false; f->accumulated_ms=duration;
        return 0;
    }
    return duration-used;
}
void cp_focus_toggle(cp_focus_t *f, int64_t now) {
    cp_focus_remaining(f,now);
    if (f->complete) {
        f->rest=!f->rest; f->complete=false; f->accumulated_ms=0;
    }
    if (f->running) f->accumulated_ms+=elapsed(f->started_ms,now);
    else f->started_ms=now;
    f->running=!f->running;
}
int64_t cp_stopwatch_elapsed(const cp_stopwatch_t *w, int64_t now) {
    return w->accumulated_ms+(w->running ? elapsed(w->started_ms,now) : 0);
}
void cp_stopwatch_toggle(cp_stopwatch_t *w, int64_t now) {
    if (w->running) w->accumulated_ms+=elapsed(w->started_ms,now);
    else w->started_ms=now;
    w->running=!w->running;
}
void cp_offline_clock(char out[9], int seconds, int64_t since, int64_t now) {
    if (seconds < 0) { snprintf(out,9,"--:--:--"); return; }
    unsigned total=(unsigned)(((uint64_t)seconds+(uint64_t)elapsed(since,now)/1000)%86400);
    snprintf(out,9,"%02u:%02u:%02u",total/3600,total/60%60,total%60);
}

bool cp_offline_usb_time(const char *line, int64_t *epoch_ms, int *seconds, int64_t *since_ms, int64_t now_ms) {
    // A fixed 13-digit Unix millisecond timestamp avoids accepting arbitrary
    // serial-console input as a clock command. 2023-11 through 2100-01 UTC.
    if (strncmp(line,"CPCLK1:",7)!=0 || strlen(line)!=20) return false;
    int64_t value=0;
    for (int i=7;i<20;i++) {
        if (line[i]<'0' || line[i]>'9') return false;
        value=value*10+(line[i]-'0');
    }
    if (value<1700000000000LL || value>=4102444800000LL) return false;
    *epoch_ms=value;
    *seconds=(int)((value/1000+8*3600)%86400);
    *since_ms=now_ms-value%1000;
    return true;
}
