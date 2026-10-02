[English](README.md) · **简体中文**

# 助手界面截图

于 2026-10-02 采集，用于本分支根目录 README。这些图片展示本项目应用界面，并非第三方产品照片。
随项目按 MIT 条款分发，中文字体继续遵守 [SIL OFL 许可证](../../fonts/OFL.txt)。

| 文件 | 来源 | 尺寸 |
| --- | --- | --- |
| `desktop-device-dark.png`、`desktop-device-details-dark.png` | 0.5.0 设备信息页原生隔离预览，使用虚构硬件读数与版本元数据，不访问真实设备。 | 1720 × 1264 |
| `desktop-connection-dark.png`、`desktop-voice-dark.png` | 正式打包 Mac 应用 0.3.1 的原生截图，蓝牙已连接，仅展示通用应用状态。 | 1720 × 1264 |
| `desktop-alerts-light.png` | 0.3.1 原生窗口的隔离浅色测试，使用示例／默认设置。 | 1720 × 1264 |
| `desktop-flasher-dark.png` | 0.4.0 原生烧录页隔离预览，使用虚构 USB 端口／序列号和真实已验证固件元数据；没有打开或烧录设备。 | 1720 × 1264 |
| `card-01-quota.png`、`card-02-threads.png`、`card-04-record.png`、`card-08-completed.png` | LVGL 渲染真实助手界面和字体；使用 `tests/companion_ui/preview.c` 中固定的公开示例数据。 | 240 × 320 |
| `card-12-offline-clock.png`、`card-13-offline-focus.png`、`card-14-offline-stopwatch.png` | `tests/companion_ui/offline_preview.c` 渲染的真实离线界面。 | 240 × 320 |

第 006 批刷新了 `card-04-record.png`，展示保持稳定的聆听提示。

卡片图是渲染图，不是真机照片。额度、日期、对话标题、电量和任务状态均为测试数据；
界面代码与中文字体和固件共用。渲染截图不能证明麦克风、扬声器、按键或电源的真机表现。

## 刷新图集

1. 按 [Mac 说明](../../../docs/codex-desktop.zh_CN.md)构建并启动应用，确认不含私人文字、路径和标识后，
   截取完整窗口。切换页面时保留卡片连接和已有设置；需要另一种外观时使用隔离预览，
   不为截图而修改用户系统外观。
2. 激活已有构建环境，在仓库根目录运行 `bash tools/preview_companion.sh`，编译真实界面并执行断言。
3. 将选中的 PPM 帧无损转换为 PNG。macOS 可在仓库根目录运行：

```bash
for name in 01-quota 02-threads 04-record 08-completed 12-offline-clock 13-offline-focus 14-offline-stopwatch; do
  sips -s format png "build/ui-preview/images/${name}.ppm" \
    --out "assets/images/codex/card-${name}.png" >/dev/null
done
```

4. 逐图检查中文缺字、裁切和隐私内容；保留原生像素，用 README 的 HTML 控制展示尺寸，
   不重绘界面。将刷新情况写入[批次记录](../../../docs/codex-updates.zh_CN.md)。
