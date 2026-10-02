[简体中文](README.zh_CN.md) · **English**

# Companion font

Source: [Noto Sans CJK SC](https://github.com/notofonts/noto-cjk/tree/main/Sans/SubsetOTF/SC),
`NotoSansSC-Regular.otf`, SIL Open Font License 1.1, retained in [OFL.txt](OFL.txt).
Source SHA-256: `faa6c9df652116dde789d351359f3d7e5d2285a2b2a1f04a2d7244df706d5ea9`.

Generated with `lv_font_conv@1.5.3`, 16 px, 2 bpp, uncompressed, no kerning.
Reproduce from the repository root (install the pinned converter locally first):

```bash
npm install --prefix .local/font-tools lv_font_conv@1.5.3
.local/font-tools/node_modules/.bin/lv_font_conv --font assets/fonts/NotoSansSC-Regular.otf --range 0x20-0x7e,0x3000-0x3030,0x3033-0x303f,0x4e00-0x9fff,0xff01-0xff60 --size 16 --bpp 2 --format lvgl --no-compress --no-kerning --lv-font-name passport_font_16 --lv-include lvgl.h -o assets/fonts/passport_font_16.c
python3 tests/test_companion_font.py
```

Actual CJK coverage ends at U+9FEF. U+3031/U+3032 vertical marks are excluded to
keep the measured line height at 22 px. Combining punctuation is not accepted by
the bridge. Unsupported dynamic characters become `?`. The test checks every
declared code point against the generated LVGL cmaps, every fixed Chinese label,
actual ASCII advances used by pagination, and per-widget font binding.
`CONFIG_LV_FONT_FMT_TXT_LARGE=y` is mandatory because bitmaps exceed 1 MB.
The font lives in read-only Flash; on-device rendering and runtime memory still
require device acceptance. The source font and license are retained for regeneration.
