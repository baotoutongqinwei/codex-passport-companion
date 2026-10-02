"""Verify actual LVGL cmaps, dynamic-text contract, and every fixed Chinese label."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
from service import ASCII_WIDTHS, display_text


class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = (ROOT / "assets/fonts/passport_font_16.c").read_text()
        cmaps = cls.font.split("static const lv_font_fmt_txt_cmap_t cmaps[] =", 1)[1].split("};", 1)[0]
        cls.coverage = set()
        for block in re.findall(r"\{([^{}]+)\}", cmaps):
            # Fail rather than overclaim coverage if converter starts emitting sparse maps.
            assert ".type = LV_FONT_FMT_TXT_CMAP_FORMAT0_TINY" in block
            assert ".unicode_list = NULL" in block
            start = int(re.search(r"\.range_start = (\d+)", block)[1])
            count = int(re.search(r"\.range_length = (\d+)", block)[1])
            cls.coverage.update(range(start, start+count))

    def test_static_chinese_and_dynamic_contract(self):
        for path in list((ROOT/"main").glob("companion*.c")) + list((ROOT/"bridge").glob("*.py")):
            required = {ord(c) for c in path.read_text() if '\u4e00' <= c <= '\u9fff'}
            self.assertFalse(required-self.coverage, path.name)
        for cp in range(0x10000):
            char = chr(cp)
            if display_text(char) == char and char not in "\n\t":
                self.assertIn(cp, self.coverage, f"U+{cp:04X}")
        self.assertNotIn(0x1f600, self.coverage)
        self.assertNotIn(0x9fff, self.coverage)
        self.assertEqual(display_text("😀\u9fff"), "??")

    def test_font_metrics_and_widget_binding(self):
        advances = [int(x) for x in re.findall(r"\.adv_w = (\d+)", self.font)]
        self.assertEqual(ASCII_WIDTHS, [(x+15)//16 for x in advances[1:96]])
        self.assertLessEqual(max(advances), 16*16)
        height = int(re.search(r"\.line_height = (\d+)", self.font)[1])
        self.assertLessEqual(height*7+2*6, 176)
        ui = (ROOT/"main/companion_ui.c").read_text()
        self.assertEqual(ui.count("lv_label_create("), 1)
        self.assertIn("lv_obj_set_style_text_font(obj, &passport_font_16", ui)
        self.assertIn("CONFIG_LV_FONT_FMT_TXT_LARGE=y", (ROOT/"sdkconfig.defaults").read_text())
        self.assertIn("passport_font_16.c", (ROOT/"main/CMakeLists.txt").read_text())


if __name__ == "__main__": unittest.main()
