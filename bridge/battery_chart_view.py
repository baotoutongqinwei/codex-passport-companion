"""Native AppKit battery bars, with file reads kept off the UI thread."""
from datetime import datetime
import csv
from pathlib import Path
import threading
import time

import AppKit as A
import objc
from Foundation import NSObject, NSTimer, NSString

from battery_chart import read_history, chart_data
from battery_history import UTC8


def tint(value):
    return A.NSColor.colorWithSRGBRed_green_blue_alpha_(
        (value >> 16 & 255)/255, (value >> 8 & 255)/255, (value & 255)/255, 1)


class BatteryBars(A.NSView):
    def isFlipped(self):
        return True

    @objc.python_method
    def text(self, text, x, y, size=11, muted=True):
        NSString.stringWithString_(text).drawAtPoint_withAttributes_((x, y), {
            A.NSFontAttributeName: A.NSFont.systemFontOfSize_(size),
            A.NSForegroundColorAttributeName: A.NSColor.secondaryLabelColor() if muted else A.NSColor.labelColor()})

    def drawRect_(self, _rect):
        dark = self.effectiveAppearance().bestMatchFromAppearancesWithNames_(
            [A.NSAppearanceNameAqua, A.NSAppearanceNameDarkAqua]) == A.NSAppearanceNameDarkAqua
        tint(0x202B30 if dark else 0xFFFFFF).setFill()
        A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 14, 14).fill()
        data = getattr(self, "data", None)
        if not data:
            return
        x, y, width, height = 20, 28, 624, 172
        for percent in (100, 50, 0):
            level = y+height*(1-percent/100)
            A.NSColor.separatorColor().setStroke()
            line = A.NSBezierPath.bezierPath()
            line.moveToPoint_((x, level)); line.lineToPoint_((x+width, level)); line.stroke()
            self.text(f"{percent}%", x+width+10, level-7)
        step = width/len(data["bins"])
        selected = getattr(self, "selected", -1)
        for index, sample in enumerate(data["bins"]):
            if sample is None:
                continue
            bar_height = max(2, height*sample["percent"]/100)
            tint(0xFF6868 if sample["percent"] <= 20 else (0x78E2BD if dark else 0x2B9F78)).setFill()
            rect = ((x+index*step+1, y+height-bar_height), (max(2, step-2), bar_height))
            bar = A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 2, 2)
            bar.fill()
            if index == selected:
                A.NSColor.labelColor().setStroke(); bar.setLineWidth_(1.5); bar.stroke()
        for i in range(5):
            stamp = datetime.fromtimestamp(data["start"]+(data["end"]-data["start"])*i/4, UTC8)
            label = stamp.strftime("%H:%M" if data["interval"] == 900 else "%m/%d %H时")
            self.text(label, x+(width-65)*i/4, y+height+15)
        if not data["latest"]:
            self.text("此时段暂无记录", 275, 94, 17, False)
            self.text("升级卡片固件后连接 Mac 导入，断开连接期间也会采样", 172, 125)

    def mouseDown_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        data = getattr(self, "data", None)
        if data and 20 <= point.x < 644 and 28 <= point.y <= 200:
            self.selected = min(len(data["bins"])-1, int((point.x-20)/624*len(data["bins"])))
            self.owner.select_sample(data["bins"][self.selected])
            self.setNeedsDisplay_(True)


class BatteryHistoryWindow(NSObject):
    @objc.python_method
    def setup(self, root):
        self.path = Path(root)/"battery-history.csv"
        self.cards, self.card_ids = {}, []
        self.signature = None
        self.loading = False
        self.loaded = None
        self.lock = threading.Lock()
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (760, 548)), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable |
            A.NSWindowStyleMaskMiniaturizable, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("电量历史 · Codex 随行助手")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.window.center()
        self.root = BatteryBars.alloc().initWithFrame_(((0, 0), (760, 548)))
        self.window.setContentView_(self.root)
        self.label("电量变化", 28, 20, 260, 34, 25, True)
        self.label("UTC+8 · 卡片电量计实测", 30, 59, 350, 20, 12)
        self.range = A.NSSegmentedControl.alloc().initWithFrame_(((487, 28), (244, 30)))
        self.range.setSegmentCount_(2)
        for index, label in enumerate(("最近 24 小时", "最近 7 天")):
            self.range.setLabel_forSegment_(label, index); self.range.setWidth_forSegment_(116, index)
        self.range.setSelectedSegment_(0); self.range.setTarget_(self); self.range.setAction_("changeRange:")
        self.root.addSubview_(self.range)
        self.picker = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((27, 94), (370, 29)), False)
        self.picker.addItemWithTitle_("尚无已导入卡片")
        self.picker.setTarget_(self); self.picker.setAction_("changeRange:")
        self.root.addSubview_(self.picker)
        self.stats = self.label("等待导入电量记录", 30, 139, 700, 27, 17, True)
        self.bars = BatteryBars.alloc().initWithFrame_(((28, 178), (704, 247)))
        self.bars.owner = self
        self.bars.setAccessibilityLabel_("电量历史柱状图")
        self.root.addSubview_(self.bars)
        self.detail = self.label("点击柱子查看采样时间、电量和电压", 30, 438, 700, 23, 12)
        self.note = self.label("", 30, 472, 580, 50, 11)
        button = A.NSButton.buttonWithTitle_target_action_("打开 CSV", self, "openCSV:")
        button.setFrame_(((615, 484), (118, 32))); self.root.addSubview_(button)
        self.csv_button = button
        return self

    @objc.python_method
    def label(self, value, x, y, width, height, size, bold=False):
        label = A.NSTextField.wrappingLabelWithString_(value)
        label.setFrame_(((x, y), (width, height)))
        label.setFont_(A.NSFont.boldSystemFontOfSize_(size) if bold else A.NSFont.systemFontOfSize_(size))
        label.setTextColor_(A.NSColor.labelColor() if bold else A.NSColor.secondaryLabelColor())
        self.root.addSubview_(label)
        return label

    @objc.python_method
    def show(self):
        self.window.makeKeyAndOrderFront_(None)
        if not getattr(self, "timer", None):
            self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1, self, "refresh:", None, True)
        self.checked = 0
        self.refresh_(None)

    @objc.python_method
    def load(self):
        try:
            try:
                stat = self.path.stat()
                signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            except FileNotFoundError:
                signature = ()
            cards = read_history(self.path, time.time()) if signature != self.signature else None
            result = (signature, cards, "")
        except BlockingIOError:
            result = (self.signature, None, "正在导入记录，稍后自动刷新")
        except (OSError, ValueError, csv.Error):
            result = (self.signature, None, "无法读取电量记录，请检查 CSV 文件")
        with self.lock:
            self.loaded = result
            self.loading = False

    def refresh_(self, _timer):
        with self.lock:
            loaded, self.loaded = self.loaded, None
        if loaded:
            signature, cards, error = loaded
            self.signature = signature
            if cards is not None:
                selected = self.picker.titleOfSelectedItem()
                self.cards = cards
                self.card_ids = sorted(cards)
                self.picker.removeAllItems()
                self.picker.addItemsWithTitles_(self.card_ids or ["尚无已导入卡片"])
                if selected in self.card_ids: self.picker.selectItemWithTitle_(selected)
            self.render()
            if error: self.detail.setStringValue_(error)
        if time.monotonic()-self.checked >= 10 and not self.loading:
            self.checked = time.monotonic()
            self.loading = True
            self.render()
            threading.Thread(target=self.load, daemon=True).start()

    @objc.python_method
    def render(self):
        card = self.cards.get(self.picker.titleOfSelectedItem(), {})
        data = chart_data(card.get("samples", []), time.time(), 1 if self.range.selectedSegment() == 0 else 7)
        self.bars.data = data
        self.bars.selected = -1
        self.bars.setNeedsDisplay_(True)
        latest = data["latest"]
        stats = (f"最近记录 {latest['percent']}%     时段最低 {data['minimum']}%" if latest else "此时段暂无已校时的电量记录")
        self.stats.setStringValue_(stats)
        self.bars.setAccessibilityValue_(stats)
        self.select_sample(latest)
        interval = "15 分钟" if data["interval"] == 900 else "2 小时"
        self.note.setStringValue_(f"每柱为 {interval} 内最后一次读数 · 红色 ≤20% · 空白表示缺少记录\n"
                                  f"未校时 {card.get('unsynced', 0)} 条／无效 {card.get('invalid', 0)} 条未绘制 · 不推断充电状态")
        self.csv_button.setEnabled_(self.path.is_file())

    @objc.python_method
    def select_sample(self, sample):
        if sample:
            stamp = datetime.fromtimestamp(sample["at"], UTC8).strftime("%m-%d %H:%M:%S")
            voltage = f"{sample['voltage']} mV" if sample["voltage"] > 0 else "电压不可用"
            self.detail.setStringValue_(f"{stamp}    {sample['percent']}%    {voltage}    · 点击柱子查看其他样本")
        else:
            self.detail.setStringValue_("此时间段没有读数；缺失数据不会补齐")

    def changeRange_(self, _sender):
        self.render()

    def openCSV_(self, _sender):
        A.NSWorkspace.sharedWorkspace().openFile_(str(self.path))

    def windowWillClose_(self, _notification):
        if getattr(self, "timer", None):
            self.timer.invalidate(); self.timer = None
