#!/usr/bin/env python3
"""Native macOS companion window; slow work stays off the AppKit thread."""
import json
import os
from pathlib import Path

import AppKit as A
import objc
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

from desktop_controller import DesktopController
from local_data import data_root


class WindowDelegate(NSObject):
    def applicationDidFinishLaunching_(self, _notification):
        self.controller = DesktopController(data_root())
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (700, 570)), A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable |
            A.NSWindowStyleMaskMiniaturizable, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("Codex 随行助手")
        self.window.setDelegate_(self)
        self.window.setReleasedWhenClosed_(False)
        self.window.center()
        self.controls = []
        self.label("Codex 随行助手", 30, 510, 640, 36, 28, True)
        self.label("连接你的 AI Passport · 语音留在本机识别", 30, 478, 640, 26, 14)
        self.fields = {}
        for key, title, y in (("codex", "Codex 服务", 422), ("account", "账户与额度", 372),
                              ("voice", "离线语音", 322), ("connection", "卡片连接", 258)):
            self.label(title, 30, y, 112, 36, 14, True)
            self.fields[key] = self.label("等待检查", 158, y-10, 510, 48, 14)
        self.mode = A.NSSegmentedControl.alloc().initWithFrame_(((30, 201), (245, 30)))
        self.mode.setSegmentCount_(2)
        self.mode.setLabel_forSegment_("蓝牙 BLE", 0)
        self.mode.setLabel_forSegment_("USB 数据线", 1)
        self.mode.setWidth_forSegment_(120, 0)
        self.mode.setWidth_forSegment_(120, 1)
        self.mode.setSelectedSegment_(0)
        self.window.contentView().addSubview_(self.mode)
        self.checkButton = self.button("重新自检", "check:", 290, 199, 116)
        self.connectButton = self.button("连接卡片", "connect:", 416, 199, 116)
        self.pauseButton = self.button("暂停连接", "pause:", 542, 199, 126)
        self.installButton = self.button("下载免费语音模型", "install:", 30, 148, 200)
        self.chooseButton = self.button("选择已有模型…", "choose:", 240, 148, 190)
        self.detail = self.label("", 30, 72, 638, 64, 14)
        self.footer = self.label("卡片息屏后用功能键唤醒。首次蓝牙连接按系统提示输入卡片配对码。", 30, 24, 638, 40, 12)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "refresh:", None, True)
        self.window.makeKeyAndOrderFront_(None)
        A.NSApp.activateIgnoringOtherApps_(True)
        self.controller.doctor()

    @objc.python_method
    def label(self, text, x, y, width, height, size, bold=False):
        field = A.NSTextField.wrappingLabelWithString_(text)
        field.setFrame_(((x, y), (width, height)))
        field.setFont_(A.NSFont.boldSystemFontOfSize_(size) if bold else A.NSFont.systemFontOfSize_(size))
        field.setTextColor_(A.NSColor.labelColor())
        self.window.contentView().addSubview_(field)
        return field

    @objc.python_method
    def button(self, title, action, x, y, width):
        button = A.NSButton.alloc().initWithFrame_(((x, y), (width, 34)))
        button.setTitle_(title)
        button.setBezelStyle_(A.NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(action)
        self.window.contentView().addSubview_(button)
        return button

    def refresh_(self, _timer):
        view = self.controller.snapshot()
        for key, field in self.fields.items():
            field.setStringValue_(view[key])
        busy = view["busy"] or self.controller.closing
        for button in (self.checkButton, self.connectButton, self.installButton, self.chooseButton, self.mode):
            button.setEnabled_(not busy)
        self.pauseButton.setEnabled_(view["busy"] and not self.controller.closing)
        self.detail.setStringValue_("正在安全退出…" if self.controller.closing else view["detail"])
        self.detail.setTextColor_(A.NSColor.systemRedColor() if view["state"] in ("error", "service_error") else A.NSColor.secondaryLabelColor())
        # Optional test-only metadata. Never store conversation IDs, text or audio.
        diagnostic = os.environ.get("PASSPORT_STATUS_PATH")
        if diagnostic:
            Path(diagnostic).write_text(json.dumps(view, ensure_ascii=False, indent=2))
        if self.controller.closed:
            self.timer.invalidate()
            A.NSApp.terminate_(None)

    def check_(self, _sender):
        self.controller.doctor()

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

    def applicationShouldTerminate_(self, _app):
        if self.controller.closed:
            return A.NSTerminateNow
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
