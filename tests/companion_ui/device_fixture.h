// Public sample values, never device measurements.
void cp_device_update(void) {}
void cp_device_snapshot(cp_device_info_t *out) { (void)out; }
static cp_device_info_t device_fixture(void) {
    cp_device_info_t d={.valid=true,.battery=86,.voltage=4028,.has_temperature=true,.temperature=31.5f,
        .heap_total=207872,.heap_free=54272,.app_size=2704688,.app_capacity=8323072,.flash_size=8388608};
    strcpy(d.version,"0.10.2");
    return d;
}
