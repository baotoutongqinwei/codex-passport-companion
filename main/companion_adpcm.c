#include "companion_adpcm.h"

static const int steps[89] = {
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,
    73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,
    449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,
    2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,
    7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,
    24623,27086,29794,32767
};
static const int changes[8] = {-1,-1,-1,-1,2,4,6,8};

size_t cp_adpcm_encode(const int16_t *samples, size_t count, uint8_t *out, size_t capacity) {
    size_t size = 6+(count+1)/2;
    if (!samples || !count || count > 2048 || capacity < size) return 0;
    // Start near the local signal amplitude to avoid a long ramp from index zero.
    int predictor = samples[0], index = 0, peak = 0;
    for (size_t i=1; i<count && i<32; ++i) {
        int delta = (int)samples[i]-samples[i-1]; if (delta < 0) delta = -delta;
        if (delta > peak) peak = delta;
    }
    while (index < 88 && steps[index] < peak) ++index;
    out[0]=count; out[1]=count>>8; out[2]=predictor; out[3]=(uint16_t)predictor>>8;
    out[4]=index; out[5]=0;
    for (size_t i=0; i<count; ++i) {
        int delta = (int)samples[i]-predictor, code = 0, step=steps[index], diff=step>>3;
        if (delta < 0) { code=8; delta=-delta; }
        if (delta >= step) { code|=4; delta-=step; diff+=step; }
        if (delta >= (step>>1)) { code|=2; delta-=step>>1; diff+=step>>1; }
        if (delta >= (step>>2)) { code|=1; diff+=step>>2; }
        predictor += code & 8 ? -diff : diff;
        if (predictor > 32767) predictor=32767;
        if (predictor < -32768) predictor=-32768;
        index += changes[code & 7]; if (index < 0) index=0; if (index > 88) index=88;
        if (!(i & 1)) out[6+i/2]=code; else out[6+i/2]|=code<<4;
    }
    return size;
}
