[English](README.md) · **简体中文**

# 随行助手字体

来源：[Noto Sans CJK SC](https://github.com/notofonts/noto-cjk/tree/main/Sans/SubsetOTF/SC)，
`NotoSansSC-Regular.otf`，采用 SIL Open Font License 1.1，保留于 [OFL.txt](OFL.txt)。
源字体 SHA-256：`faa6c9df652116dde789d351359f3d7e5d2285a2b2a1f04a2d7244df706d5ea9`。

使用 `lv_font_conv@1.5.3` 生成，16 px、2 bpp、不压缩、不含字偶间距。
从项目根目录复现（先本地安装固定版本转换器）：

```bash
npm install --prefix .local/font-tools lv_font_conv@1.5.3
.local/font-tools/node_modules/.bin/lv_font_conv --font assets/fonts/NotoSansSC-Regular.otf --range 0x20-0x7e,0x3000-0x3030,0x3033-0x303f,0x4e00-0x9fff,0xff01-0xff60 --size 16 --bpp 2 --format lvgl --no-compress --no-kerning --lv-font-name passport_font_16 --lv-include lvgl.h -o assets/fonts/passport_font_16.c
python3 tests/test_companion_font.py
```

实际汉字覆盖到 U+9FEF。去掉 U+3031/U+3032 竖排重复符，使实测行高保持 22 px。
桥接不接收组合标点；不支持的动态字符替换成 `?`。
测试会比对实际 LVGL cmap、全部固定中文文字、分页使用的 ASCII 字宽，以及各标签的字体绑定。
点阵超过 1 MB，必须启用 `CONFIG_LV_FONT_FMT_TXT_LARGE=y`。
字体存于只读 Flash；真机渲染和运行内存仍需上板验收。保留源字体及许可以便重新生成。
