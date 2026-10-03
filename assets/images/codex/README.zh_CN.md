[English](README.md) · **简体中文**

# 助手界面截图

于 2026-10-02 采集，用于本分支根目录 README。这些图片展示本项目应用界面，并非第三方产品照片。
随项目按 MIT 条款分发，中文字体继续遵守 [SIL OFL 许可证](../../fonts/OFL.txt)。

| 文件 | 来源 | 尺寸 |
| --- | --- | --- |
| `card-19-quota-cached.png`、`card-20-quota-unavailable.png` | 0.10.1 真实 LVGL 渲染，使用虚构额度故障样本，不访问账号或设备。 | 240 × 320 |
| `desktop-battery-dark.png`、`desktop-battery-light.png` | 桌面 0.9.0 原生图表，由 `tools/preview_battery_chart.py` 用公开虚构样本渲染，不访问设备，不是真实电量测量。 | 1520 × 1096 |
| `desktop-console-dark.png` | 桌面 0.6.0 原生窗口隔离渲染，使用公开示例事件；未连接卡片，也未采集真实请求或私人日志。 | 1720 × 1208 |
| `card-17-device.png`、`card-18-offline-device.png` | 0.9.0 真实 LVGL 渲染的设备页（功能始于 0.6.0），使用 `tests/companion_ui/device_fixture.h` 的公开示例值，不是真实传感器读数；离线页展示示例记录条数。 | 240 × 320 |
| `desktop-device-dark.png`、`desktop-device-details-dark.png` | 0.5.0 设备信息页原生隔离预览，使用虚构硬件读数与版本元数据，不访问真实设备。 | 1720 × 1264 |
| `desktop-connection-dark.png`、`desktop-voice-dark.png` | 正式打包 Mac 应用 0.3.1 的原生截图，蓝牙已连接，仅展示通用应用状态。 | 1720 × 1264 |
| `desktop-alerts-light.png` | 0.3.1 原生窗口的隔离浅色测试，使用示例／默认设置。 | 1720 × 1264 |
| `desktop-flasher-dark.png` | 0.4.0 原生烧录页隔离预览，使用虚构 USB 端口／序列号和真实已验证固件元数据；没有打开或烧录设备。 | 1720 × 1264 |
| `card-01-quota.png`、`card-02-threads.png`、`card-04-record.png`、`card-08-completed.png` | LVGL 渲染真实助手界面和字体；使用 `tests/companion_ui/preview.c` 中固定的公开示例数据。 | 240 × 320 |
| `card-10-offline-unset.png`、`card-12-offline-clock.png`、`card-13-offline-focus.png`、`card-14-offline-stopwatch.png` | `tests/companion_ui/offline_preview.c` 渲染的真实离线界面。 | 240 × 320 |

第 006 批刷新了 `card-04-record.png`，展示保持稳定的聆听提示。
第 009 批刷新额度页快捷入口和离线时钟页提示，加入两种设备页。
第 011 批新增未校时时的 USB 自动校时提示预览，并刷新离线时钟与设备页。
第 012 批刷新两种设备页，离线页显示电量记录条数。
第 013 批新增亮暗色电量图表。在桌面 Python 环境运行 `python tools/preview_battery_chart.py`，
再从 `build/battery-preview/` 复制所选 PNG 即可复现。

卡片图是渲染图，不是真机照片。额度、日期、对话标题、电量和任务状态均为测试数据；
界面代码与中文字体和固件共用。渲染截图不能证明麦克风、扬声器、按键或电源的真机表现。

## 刷新图集

1. 按 [Mac 说明](../../../docs/codex-desktop.zh_CN.md)构建并启动应用，确认不含私人文字、路径和标识后，
   截取完整窗口。切换页面时保留卡片连接和已有设置；需要另一种外观时使用隔离预览，
   不为截图而修改用户系统外观。
2. 激活已有构建环境，在仓库根目录运行 `bash tools/preview_companion.sh`，编译真实界面并执行断言。
3. 将选中的 PPM 帧无损转换为 PNG。macOS 可在仓库根目录运行：

```bash
for name in 01-quota 02-threads 04-record 08-completed 10-offline-unset 12-offline-clock 13-offline-focus 14-offline-stopwatch 17-device 18-offline-device; do
  sips -s format png "build/ui-preview/images/${name}.ppm" \
    --out "assets/images/codex/card-${name}.png" >/dev/null
done
```

4. 逐图检查中文缺字、裁切和隐私内容；保留原生像素，用 README 的 HTML 控制展示尺寸，
   不重绘界面。将刷新情况写入[批次记录](../../../docs/codex-updates.zh_CN.md)。

第 015 批新增额度故障状态预览，并将设备页示例版本更新为 0.10.1。

第 016 批新增虚构数据的原生桌面草稿监控与连接错误图片。运行 `.local/transport-venv/bin/python tools/preview_desktop_status.py` 可复现；不连接设备或账户。

第 017 批更新卡片顶部状态栏截图，并新增 20%／50%／100% 电池示例。图标由 LVGL 图形绘制，不依赖字体字符；使用虚构读数。
