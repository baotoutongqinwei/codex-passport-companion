#!/usr/bin/env python3
"""Native macOS companion window; slow work stays off the AppKit thread."""
import json
import os
from pathlib import Path
import sys

if __name__ == "__main__" and sys.argv[1:2] == ["--firmware-tool"]:
    from firmware import tool_main
    tool_main()
    raise SystemExit(0)

import AppKit as A
import objc
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

from desktop_controller import DesktopController
from local_data import data_root
from firmware import bundled_firmware, PROFILE_NAMES


def asset_path(name):
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    return root / "assets/images" / name


def color(hex_value, alpha=1):
    return A.NSColor.colorWithSRGBRed_green_blue_alpha_(
        ((hex_value >> 16) & 255)/255, ((hex_value >> 8) & 255)/255, (hex_value & 255)/255, alpha)


def dark_appearance(view):
    return view.effectiveAppearance().bestMatchFromAppearancesWithNames_(
        [A.NSAppearanceNameAqua, A.NSAppearanceNameDarkAqua]) == A.NSAppearanceNameDarkAqua


class Surface(A.NSView):
    """Small native, flipped canvas for rounded panels and semantic backgrounds."""
    def isFlipped(self):
        return True

    def drawRect_(self, _rect):
        dark = dark_appearance(self)
        kind = getattr(self, "kind", "card")
        if kind == "nav":
            if getattr(self, "selected", False):
                color(0x78E2BD if dark else 0x237C68, .15).setFill()
                A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 10, 10).fill()
            return
        fills = {"background": (0xF3F6F3, 0x151D21), "sidebar": (0xE7EEEA, 0x11191D),
                 "card": (0xFFFFFF, 0x202B30), "hero": (0xE3F3EB, 0x1A3833)}
        color(fills[kind][dark]).setFill()
        radius = 0 if kind in ("background", "sidebar") else 14
        path = A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), radius, radius)
        path.fill()


class WindowDelegate(NSObject):
    def applicationDidFinishLaunching_(self, _notification):
        self.controller = DesktopController(data_root())
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (860, 604)), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable |
            A.NSWindowStyleMaskMiniaturizable, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("Codex 随行助手")
        self.window.setDelegate_(self)
        self.window.setReleasedWhenClosed_(False)
        self.window.center()
        self.window.setTitlebarAppearsTransparent_(True)
        self.surfaces = []
        self.root = self.surface(None, 0, 0, 860, 604, "background")
        self.window.setContentView_(self.root)
        sidebar = self.surface(self.root, 0, 0, 194, 604, "sidebar")
        self.icon = A.NSImage.alloc().initWithContentsOfFile_(str(asset_path("codex-passport-icon.png")))
        if self.icon:
            A.NSApp.setApplicationIconImage_(self.icon)
            image = A.NSImageView.alloc().initWithFrame_(((20, 25), (72, 72)))
            image.setImage_(self.icon)
            image.setImageScaling_(A.NSImageScaleProportionallyUpOrDown)
            sidebar.addSubview_(image)
        self.label(sidebar, "Codex 随行助手", 24, 110, 164, 30, 19, True)
        self.label(sidebar, "PASSPORT", 25, 144, 140, 20, 11, muted=True)
        self.nav = []
        self.nav_panels = []
        for index, (name, symbol) in enumerate((("连接卡片", "rectangle.connected.to.line.below"),
                                                ("语音模型", "waveform"), ("提醒设置", "bell"),
                                                ("固件烧录", "arrow.down.doc"), ("设备信息", "cpu"))):
            background = self.surface(sidebar, 14, 209+index*52, 166, 42, "nav")
            button = self.button(background, "  "+name, "navigate:", 14, 0, 142, height=42)
            button.setTag_(index)
            button.setBordered_(False)
            button.setAlignment_(A.NSTextAlignmentLeft)
            button.setImage_(A.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, name))
            button.setImagePosition_(A.NSImageLeft)
            self.nav.append(button)
            self.nav_panels.append(background)
        self.label(sidebar, "语音识别留在本机", 24, 543, 158, 20, 11, muted=True)
        self.label(sidebar, "版本 0.5.0", 24, 568, 140, 18, 11, muted=True)

        self.label(self.root, "CODEX PASSPORT", 226, 27, 330, 18, 10, muted=True)
        self.page_title = self.label(self.root, "", 226, 53, 476, 34, 26, True)
        self.page_subtitle = self.label(self.root, "", 226, 96, 600, 22, 13, muted=True)
        self.badge = self.label(self.root, "待连接", 720, 62, 112, 24, 12, True)
        self.badge.setAlignment_(A.NSTextAlignmentRight)
        self.pages = [self.surface(self.root, 226, 132, 608, 352, "background") for _ in range(5)]
        self.fields = {}
        connection = self.surface(self.pages[0], 0, 0, 608, 172, "hero")
        self.connection_title = self.label(connection, "准备连接", 20, 19, 530, 28, 19, True)
        self.fields["connection"] = self.label(connection, "", 20, 57, 568, 42, 13, muted=True)
        self.mode = A.NSSegmentedControl.alloc().initWithFrame_(((18, 119), (273, 30)))
        self.mode.setSegmentCount_(2)
        self.mode.setLabel_forSegment_("蓝牙 BLE", 0)
        self.mode.setLabel_forSegment_("USB 数据线", 1)
        self.mode.setWidth_forSegment_(130, 0)
        self.mode.setWidth_forSegment_(130, 1)
        self.mode.setSelectedSegment_(0)
        connection.addSubview_(self.mode)
        self.connectButton = self.button(connection, "连接卡片", "connect:", 309, 116, 132, primary=True)
        self.pauseButton = self.button(connection, "暂停连接", "pause:", 453, 116, 137)
        for key, title, x in (("codex", "Codex 服务", 0), ("account", "账户与额度", 314)):
            card = self.surface(self.pages[0], x, 186, 294, 104)
            self.label(card, title, 18, 16, 258, 21, 13, True)
            self.fields[key] = self.label(card, "等待检查", 18, 47, 258, 42, 12, muted=True)
        self.label(self.pages[0], "首次配对：在 Mac 输入卡片上的六位码。", 2, 311, 440, 35, 12, muted=True)
        self.checkButton = self.button(self.pages[0], "重新自检", "check:", 485, 308, 123)

        voice = self.surface(self.pages[1], 0, 0, 608, 192)
        self.label(voice, "本机语音识别", 20, 20, 420, 28, 19, True)
        self.label(voice, "Whisper base  /  简体中文", 20, 54, 530, 24, 12, muted=True)
        self.fields["voice"] = self.label(voice, "等待检查", 20, 87, 562, 40, 13)
        self.installButton = self.button(voice, "下载免费语音模型", "install:", 16, 141, 214, primary=True)
        self.chooseButton = self.button(voice, "选择已有模型…", "choose:", 239, 141, 195)
        self.cancelModelButton = self.button(voice, "取消下载", "pause:", 450, 141, 140)
        self.label(self.pages[1], "轻量复用", 3, 216, 134, 24, 13, True)
        self.label(self.pages[1], "模型约 142 MB。已有模型可以直接使用，无需重复下载。", 3, 244, 600, 24, 12, muted=True)
        self.label(self.pages[1], "你来决定何时发送", 3, 287, 250, 24, 13, True)
        self.label(self.pages[1], "识别后先在卡片预览，再按中键确认。更换模型前请先暂停连接。", 3, 315, 600, 35, 12, muted=True)

        settings = self.controller.alert_settings
        self.alert_controls = {}
        preferences = self.surface(self.pages[2], 0, 0, 608, 205)
        for i, (key, title, hint) in enumerate((
                ("enabled", "卡片任务提醒", "完成或需要处理时，短暂显示提醒。"),
                ("sound", "提示音", "录音开始前和任务提醒时短鸣，录音期间不播放。"),
                ("quiet", "免打扰", "指定时段不提醒、不亮屏、不发声，保留未读。"))):
            y = i*66
            self.label(preferences, title, 20, y+14, 490, 22, 13, True)
            self.label(preferences, hint, 20, y+39, 498, 20, 11, muted=True)
            switch = A.NSSwitch.alloc().initWithFrame_(((539, y+23), (48, 28)))
            switch.setTarget_(self); switch.setAction_("saveAlerts:")
            switch.setAccessibilityLabel_(title)
            switch.setState_(A.NSControlStateValueOn if settings[key] else A.NSControlStateValueOff)
            preferences.addSubview_(switch)
            self.alert_controls[key] = switch
        quiet = self.surface(self.pages[2], 0, 217, 608, 101)
        self.label(quiet, "免打扰时段", 20, 15, 280, 23, 13, True)
        self.label(quiet, "UTC+8 · 24 小时制", 420, 17, 170, 22, 11, muted=True)
        for key, x in (("start", 20), ("end", 156)):
            field = A.NSTextField.alloc().initWithFrame_(((x, 52), (94, 30)))
            field.setStringValue_(settings[key])
            field.setPlaceholderString_("HH:MM")
            field.setAlignment_(A.NSTextAlignmentCenter)
            field.setFont_(A.NSFont.monospacedDigitSystemFontOfSize_weight_(15, A.NSFontWeightRegular))
            field.setBezelStyle_(A.NSTextFieldRoundedBezel)
            field.setAccessibilityLabel_("免打扰开始时间" if key == "start" else "免打扰结束时间")
            quiet.addSubview_(field)
            self.alert_controls[key] = field
        self.label(quiet, "至", 126, 57, 24, 24, 12, muted=True)
        self.saveButton = self.button(quiet, "保存时段", "saveAlerts:", 443, 49, 148)
        self.label(self.pages[2], "默认静音，22:00–08:00 免打扰。起止相同表示全天免打扰。", 2, 332, 604, 20, 11, muted=True)

        firmware = self.surface(self.pages[3], 0, 0, 608, 141, "hero")
        self.label(firmware, "选择固件", 20, 13, 170, 24, 15, True)
        self.catalog = bundled_firmware()
        self.firmwarePicker = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((17, 43), (378, 30)), False)
        self.firmwarePicker.addItemWithTitle_("请选择固件版本…")
        for row in self.catalog:
            self.firmwarePicker.addItemWithTitle_(PROFILE_NAMES[row["profile"]])
        self.firmwarePicker.setTarget_(self); self.firmwarePicker.setAction_("pickFirmware:")
        firmware.addSubview_(self.firmwarePicker)
        self.chooseFirmwareButton = self.button(firmware, "本地 .bin…", "chooseFirmware:", 421, 40, 167)
        self.firmwareInfo = self.label(firmware, "", 20, 85, 568, 45, 11, muted=True)
        device = self.surface(self.pages[3], 0, 153, 608, 125)
        self.label(device, "USB 烧录设备", 20, 12, 250, 22, 13, True)
        self.usbPicker = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((17, 40), (429, 30)), False)
        self.usbPicker.addItemWithTitle_("连接数据线后，点击扫描")
        device.addSubview_(self.usbPicker)
        self.usbRows = []
        self.scanUsbButton = self.button(device, "扫描", "scanUsb:", 462, 37, 126)
        self.preserveConfig = A.NSButton.checkboxWithTitle_target_action_("保留配对与配置（推荐）", self, None)
        self.preserveConfig.setFrame_(((20, 84), (340, 26)))
        self.preserveConfig.setState_(A.NSControlStateValueOn)
        device.addSubview_(self.preserveConfig)
        self.flashProgress = A.NSProgressIndicator.alloc().initWithFrame_(((3, 293), (400, 8)))
        self.flashProgress.setIndeterminate_(False)
        self.flashProgress.setMinValue_(0); self.flashProgress.setMaxValue_(100)
        self.pages[3].addSubview_(self.flashProgress)
        self.flashMessage = self.label(self.pages[3], "", 3, 311, 394, 40, 11, muted=True)
        self.flashButton = self.button(self.pages[3], "确认烧录…", "flash:", 424, 283, 182, primary=True)
        self.flashLogButton = self.button(self.pages[3], "查看烧录记录", "flashLog:", 448, 322, 158, height=28)

        scroll = A.NSScrollView.alloc().initWithFrame_(((0, 0), (608, 352)))
        scroll.setHasVerticalScroller_(True)
        scroll.setDrawsBackground_(False)
        scroll.setAutomaticallyAdjustsContentInsets_(False)
        self.pages[4].addSubview_(scroll)
        monitor = self.surface(None, 0, 0, 594, 704, "background")
        scroll.setDocumentView_(monitor)
        self.device_fields = {}
        summary = self.surface(monitor, 0, 0, 594, 110, "hero")
        self.device_fields["version"] = self.label(summary, "", 18, 12, 407, 22, 14, True)
        self.deviceUpgrade = self.button(summary, "查看固件…", "deviceFirmware:", 435, 8, 146)
        self.deviceVersionHint = self.label(summary, "", 18, 42, 555, 38, 12)
        self.device_fields["status"] = self.label(summary, "", 18, 84, 555, 20, 11, muted=True)
        self.device_bars = {}
        for key, title, x in (("heap", "运行内存 · 可分配堆", 0), ("app", "固件 · 应用分区", 304)):
            panel = self.surface(monitor, x, 122, 290, 130)
            self.label(panel, title, 16, 12, 258, 22, 12, True)
            self.device_fields[key] = self.label(panel, "", 16, 38, 258, 26, 18, True)
            bar = A.NSProgressIndicator.alloc().initWithFrame_(((16, 71), (258, 6)))
            bar.setIndeterminate_(False); bar.setMinValue_(0); bar.setMaxValue_(100)
            panel.addSubview_(bar); self.device_bars[key] = bar
            self.device_fields[key+"_note"] = self.label(panel, "", 16, 85, 258, 36, 11, muted=True)
        for key, title, note, x in (("battery", "电池", "", 0), ("temperature", "芯片温度", "非环境／电池温度", 202),
                                     ("uptime", "本次运行", "时 : 分 : 秒", 404)):
            panel = self.surface(monitor, x, 264, 190, 98)
            self.label(panel, title, 16, 12, 158, 20, 12, True)
            self.device_fields[key] = self.label(panel, "", 16, 38, 158, 26, 21, True)
            field = self.label(panel, note, 16, 72, 158, 20, 11, muted=True)
            if key == "battery": self.device_fields["voltage"] = field
        details = self.surface(monitor, 0, 374, 594, 260)
        for i, (key, title) in enumerate((("hardware", "芯片配置"), ("peripherals", "屏幕与外设"),
                ("memory_spec", "内存规格"), ("radio", "连接信号"), ("nvs", "配置存储"),
                ("tasks", "任务与栈"), ("reset", "上次复位"), ("build", "构建信息"))):
            self.label(details, title, 16, 13+i*30, 100, 22, 12, muted=True)
            self.device_fields[key] = self.label(details, "", 117, 13+i*30, 460, 22, 12)
        self.label(monitor, "内存按可分配堆统计；NVS 按条目统计，不等于文件空间。\nCPU 占用、充电状态／电流暂不可读；Wi-Fi 与离线版暂不上报。", 4, 650, 580, 46, 11, muted=True)

        status = self.surface(self.root, 226, 500, 608, 82)
        self.label(status, "当前状态", 17, 11, 140, 20, 11, True)
        self.detail = self.label(status, "", 17, 35, 570, 42, 12, muted=True)
        self.spinner = A.NSProgressIndicator.alloc().initWithFrame_(((570, 12), (16, 16)))
        self.spinner.setStyle_(A.NSProgressIndicatorStyleSpinning)
        self.spinner.setDisplayedWhenStopped_(False)
        status.addSubview_(self.spinner)
        self.appearance = None
        self.show_page(0)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "refresh:", None, True)
        self.window.makeKeyAndOrderFront_(None)
        A.NSApp.activateIgnoringOtherApps_(True)
        self.controller.doctor()

    @objc.python_method
    def surface(self, parent, x, y, width, height, kind="card"):
        view = Surface.alloc().initWithFrame_(((x, y), (width, height)))
        view.kind = kind
        if parent is not None: parent.addSubview_(view)
        self.surfaces.append(view)
        return view

    @objc.python_method
    def label(self, parent, text, x, y, width, height, size=13, bold=False, muted=False):
        field = A.NSTextField.wrappingLabelWithString_(text)
        field.setFrame_(((x, y), (width, height)))
        field.setFont_(A.NSFont.boldSystemFontOfSize_(size) if bold else A.NSFont.systemFontOfSize_(size))
        field.setTextColor_(A.NSColor.secondaryLabelColor() if muted else A.NSColor.labelColor())
        parent.addSubview_(field)
        return field

    @objc.python_method
    def button(self, parent, title, action, x, y, width, height=36, primary=False):
        button = A.NSButton.alloc().initWithFrame_(((x, y), (width, height)))
        button.setTitle_(title)
        button.setBezelStyle_(A.NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(action)
        button.setFont_(A.NSFont.systemFontOfSize_weight_(13, A.NSFontWeightMedium))
        if primary: button.setBezelColor_(color(0x237C68))
        parent.addSubview_(button)
        return button

    @objc.python_method
    def show_page(self, index):
        self.page = index
        titles = ("连接你的卡片", "让语音留在本机", "按自己的节奏接收提醒", "给卡片换上新固件", "看看卡片的运行状态")
        hints = ("选择连接方式，同步对话、时间与额度。", "使用免费离线模型，将你的声音转成简体中文。",
                 "任务提醒与声音开关立即生效，修改时段后记得保存。",
                 "插上 USB 数据线，选择固件；不需要安装开发环境。",
                 "硬件、资源占用与固件版本 · USB／蓝牙本机监控。")
        self.page_title.setStringValue_(titles[index])
        self.page_subtitle.setStringValue_(hints[index])
        for i, page in enumerate(self.pages): page.setHidden_(i != index)
        dark = dark_appearance(self.root)
        for i, button in enumerate(self.nav):
            selected = i == index
            self.nav_panels[i].selected = selected
            self.nav_panels[i].setNeedsDisplay_(True)
            button.setContentTintColor_(color(0x8BEDCD if dark else 0x176A51) if selected else A.NSColor.secondaryLabelColor())
            button.setAccessibilityValue_("已选择" if selected else "")
        self.root.setNeedsDisplay_(True)

    def navigate_(self, sender):
        self.show_page(sender.tag())

    def refresh_(self, _timer):
        view = self.controller.snapshot()
        for key, field in self.device_fields.items():
            field.setStringValue_(view["device"][key])
        for key, bar in self.device_bars.items():
            bar.setDoubleValue_(view["device"][key+"_percent"])
        upgrade = view["upgrade"]
        self.deviceVersionHint.setStringValue_(f"{upgrade['source']} {upgrade['version']} · {upgrade['message']}")
        self.deviceUpgrade.setTitle_("查看升级…" if upgrade["kind"] == "upgrade" else "查看固件…")
        for key, field in self.fields.items():
            field.setStringValue_(view[key])
        busy = view["busy"] or view["firmware_busy"] or self.controller.closing
        for button in (self.checkButton, self.connectButton, self.installButton, self.chooseButton, self.mode):
            button.setEnabled_(not busy)
        self.pauseButton.setEnabled_(view["busy"] and not view["firmware_busy"] and not self.controller.closing)
        self.cancelModelButton.setEnabled_(bool(view.get("model_busy")) and not self.controller.closing)
        state = view["state"]
        badge = {"ready": "已连接", "connected": "正在同步", "checking": "自检中",
                 "waiting": "等待卡片", "scanning": "正在寻找", "pairing": "等待配对",
                 "reconnecting": "重新连接", "error": "需要处理", "service_error": "需要处理", "flashing": "正在烧录"}.get(state, "待连接")
        self.badge.setStringValue_(badge)
        self.badge.setTextColor_(A.NSColor.systemGreenColor() if state == "ready" else
                                A.NSColor.systemOrangeColor() if state in ("error", "service_error") else A.NSColor.secondaryLabelColor())
        self.connection_title.setStringValue_("卡片已连接" if state == "ready" else "准备连接" if state == "idle" else badge)
        if view["busy"] and state != "ready": self.spinner.startAnimation_(None)
        else: self.spinner.stopAnimation_(None)
        self.detail.setStringValue_("正在安全退出…" if self.controller.closing else view["detail"])
        self.detail.setTextColor_(A.NSColor.systemRedColor() if view["state"] in ("error", "service_error") else A.NSColor.secondaryLabelColor())
        for control in (self.firmwarePicker, self.chooseFirmwareButton, self.usbPicker,
                        self.scanUsbButton, self.preserveConfig):
            control.setEnabled_(not view["firmware_busy"] and not self.controller.closing)
        self.firmwareInfo.setStringValue_(view["firmware_info"])
        self.flashMessage.setStringValue_("请先完成录音、处理草稿并在 Codex 确认队列，再烧录。"
                                         if view["pending"] and not view["flashing"] else view["flash_detail"])
        self.flashProgress.setDoubleValue_(view["flash_progress"])
        if self.usbRows != view["usb_devices"]:
            self.usbRows = view["usb_devices"]
            self.usbPicker.removeAllItems()
            self.usbPicker.addItemWithTitle_("请选择卡片…" if self.usbRows else "未发现 USB 卡片")
            for row in self.usbRows:
                self.usbPicker.addItemWithTitle_(f"{Path(row['port']).name} · {row['serial']}")
            if len(self.usbRows) == 1: self.usbPicker.selectItemAtIndex_(1)
        self.flashButton.setEnabled_(bool(self.controller.firmware) and self.usbPicker.indexOfSelectedItem() > 0
                                     and not view["firmware_busy"] and not view["pending"] and not self.controller.closing)
        self.flashLogButton.setEnabled_((self.controller.root / "firmware-last.log").is_file() and not view["flashing"])
        appearance = dark_appearance(self.root)
        if appearance != self.appearance:
            self.appearance = appearance
            self.window.setBackgroundColor_(color(0x151D21 if appearance else 0xF3F6F3))
            for surface in self.surfaces: surface.setNeedsDisplay_(True)
            self.show_page(self.page)
        # Optional test-only metadata. Never store conversation IDs, text or audio.
        diagnostic = os.environ.get("PASSPORT_STATUS_PATH")
        if diagnostic:
            Path(diagnostic).write_text(json.dumps(view, ensure_ascii=False, indent=2))
        if self.controller.closed:
            self.timer.invalidate()
            A.NSApp.terminate_(None)

    def check_(self, _sender):
        self.controller.doctor()

    def deviceFirmware_(self, _sender):
        self.show_page(3)
        if self.controller.firmware or self.controller.snapshot()["firmware_busy"]:
            return
        profile = self.controller.snapshot()["upgrade"]["profile"] or ("ble" if self.mode.selectedSegment() == 0 else "usb")
        for index, row in enumerate(self.catalog):
            if row["profile"] == profile:
                self.firmwarePicker.selectItemAtIndex_(index+1)
                self.pickFirmware_(self.firmwarePicker)
                break

    def connect_(self, _sender):
        self.controller.connect("ble" if self.mode.selectedSegment() == 0 else "usb")

    def pause_(self, _sender):
        self.controller.pause()

    def install_(self, _sender):
        self.controller.model()

    def choose_(self, _sender):
        panel = A.NSOpenPanel.openPanel()
        panel.setTitle_("选择已有的 ggml-base.bin（校验后直接使用，不复制）")
        panel.setCanChooseDirectories_(False)
        panel.setAllowsMultipleSelection_(False)
        if panel.runModal() == A.NSModalResponseOK:
            self.controller.model(panel.URL().path())

    def pickFirmware_(self, _sender):
        index = self.firmwarePicker.indexOfSelectedItem() - 1
        if 0 <= index < len(self.catalog):
            row = self.catalog[index]
            self.controller.select_firmware(row["path"], row["sha256"], row["profile"])
        else:
            with self.controller.lock:
                self.controller.firmware = None
            self.controller.update(firmware_info="请选择内置版本或本地合并 .bin 固件。")

    def chooseFirmware_(self, _sender):
        panel = A.NSOpenPanel.openPanel()
        panel.setTitle_("选择从 0x0 烧录的完整合并固件")
        panel.setCanChooseDirectories_(False); panel.setAllowsMultipleSelection_(False)
        panel.setAllowedFileTypes_(["bin"])
        if panel.runModal() == A.NSModalResponseOK:
            self.firmwarePicker.selectItemAtIndex_(0)
            self.controller.select_firmware(panel.URL().path())

    def scanUsb_(self, _sender):
        self.controller.scan_usb()

    def flashLog_(self, _sender):
        A.NSWorkspace.sharedWorkspace().openFile_(str(self.controller.root / "firmware-last.log"))

    def flash_(self, _sender):
        firmware = self.controller.firmware
        index = self.usbPicker.indexOfSelectedItem() - 1
        if not firmware or not 0 <= index < len(self.usbRows): return
        device = dict(self.usbRows[index])
        preserve = self.preserveConfig.state() == A.NSControlStateValueOn
        alert = A.NSAlert.alloc().init()
        alert.setMessageText_("确认烧录这张卡片？" if preserve else "确认重新初始化卡片配置？")
        impact = ("保留配对与配置；分区不一致时会停止，不写入。" if preserve else
                  "将从 0x0 写入完整固件，清除配对、Wi-Fi 等配置，需要重新设置。")
        name = PROFILE_NAMES.get(firmware.get("profile"), firmware["name"])
        alert.setInformativeText_(f"固件：{name}\n版本：{firmware['descriptor']['version']}\n"
                                  f"校验：{firmware['sha256']}\n"
                                  f"设备：{device['port']}\n序列号：{device['serial']}\n\n{impact}\n"
                                  "连接将暂停。写入期间请勿拔线、关机或退出应用。")
        alert.addButtonWithTitle_("取消")
        alert.addButtonWithTitle_("开始烧录" if preserve else "清除配置并烧录")
        if alert.runModal() == A.NSAlertSecondButtonReturn:
            self.controller.flash(firmware["sha256"], device, preserve)


    def saveAlerts_(self, _sender):
        settings = {key: button.state() == A.NSControlStateValueOn for key, button in self.alert_controls.items()
                    if key in ("enabled", "sound", "quiet")}
        settings.update({key: self.alert_controls[key].stringValue() for key in ("start", "end")})
        try:
            self.controller.set_alerts(settings)
        except (OSError, ValueError) as exc:
            for key in ("enabled", "sound", "quiet"):
                self.alert_controls[key].setState_(A.NSControlStateValueOn if self.controller.alert_settings[key] else A.NSControlStateValueOff)
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_("提醒设置未保存")
            alert.setInformativeText_(str(exc) if isinstance(exc, ValueError) else "无法写入本机设置，请检查磁盘和权限。")
            alert.runModal()

    def applicationShouldTerminate_(self, _app):
        if self.controller.closed:
            return A.NSTerminateNow
        if self.controller.snapshot()["firmware_busy"]:
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_("固件操作进行中")
            alert.setInformativeText_("请等待检查或烧录结束后再退出，写入期间请保持 USB 连接。")
            alert.runModal()
            return A.NSTerminateCancel
        if self.controller.pending() and not self.controller.closing:
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_("仍有录音、草稿或待核对的发送记录")
            alert.setInformativeText_("退出会清空本机草稿和去重记录。已交给 Codex 的消息不会撤回；请先在电脑确认队列与发送结果。")
            alert.addButtonWithTitle_("继续使用")
            alert.addButtonWithTitle_("退出程序")
            if alert.runModal() == A.NSAlertFirstButtonReturn:
                return A.NSTerminateCancel
        self.controller.close()
        # Keep the normal run loop alive while the worker drains. TerminateLater
        # enters a modal loop where our normal refresh timer is not scheduled.
        return A.NSTerminateCancel

    def windowShouldClose_(self, _window):
        A.NSApp.terminate_(None)
        return False


def main():
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
    delegate = WindowDelegate.alloc().init()
    app.setDelegate_(delegate)
    menu = A.NSMenu.alloc().init()
    item = A.NSMenuItem.alloc().init()
    menu.addItem_(item)
    submenu = A.NSMenu.alloc().init()
    submenu.addItemWithTitle_action_keyEquivalent_("退出 Codex 随行助手", "terminate:", "q")
    item.setSubmenu_(submenu)
    app.setMainMenu_(menu)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
