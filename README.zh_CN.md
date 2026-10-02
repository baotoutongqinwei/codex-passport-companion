[English](README.md) · **简体中文**

# Codex 随行助手

<p align="center"><img src="assets/images/codex-passport-icon.png" width="96" alt="Codex 随行助手薄荷绿卡片图标"></p>

基于 [FoloToy AI Passport](https://gitee.com/FoloToy/ai-passport) 的随身 Codex 助手：
在 240 × 320 卡片上确认语音输入、切换对话、查看回复与周额度。
Codex 和本地语音识别运行在 Mac 上，卡片负责显示、录音和按键交互。
另外提供无需电脑的离线时钟、番茄钟、秒表固件。

这是基于 FoloToy 完整项目开发的社区应用，并非 OpenAI 或 FoloToy 官方产品。
默认应用分支为 `master`，已包含本次 P1 与桌面优化。保留上游历史、可复用 BSP 和此前的功能分支。

## 界面预览

### Mac 桌面端

原生连接主页、本地语音识别、免打扰设置和 USB 固件烧录，外观跟随 macOS 浅色／深色模式。

<p align="center"><img src="assets/images/codex/desktop-connection-dark.png" width="860" alt="卡片已连接的原生 Mac 主页"></p>

| 本地语音模型 · 深色 | 提醒设置 · 浅色 |
| --- | --- |
| <img src="assets/images/codex/desktop-voice-dark.png" width="430" alt="深色本机语音模型页面"> | <img src="assets/images/codex/desktop-alerts-light.png" width="430" alt="浅色提醒开关与免打扰时段页面"> |

桌面 0.4.0 新增 USB 固件烧录；下图使用隔离预览中的示例设备。

<p align="center"><img src="assets/images/codex/desktop-flasher-dark.png" width="860" alt="内置固件选择、USB 设备与保留配置的烧录页面"></p>

### 设备信息

桌面 0.5.0 新增设备监控与固件比对。下面为使用虚构读数的原生界面预览，不是真机测量。

| 设备概览 | 硬件详情 |
| --- | --- |
| <img src="assets/images/codex/desktop-device-dark.png" width="430" alt="设备资源占用与固件比对"> | <img src="assets/images/codex/desktop-device-details-dark.png" width="430" alt="硬件、配置存储、连接信号与任务详情"> |

### 卡片端

| 周额度与重置时间 | 最近对话与状态 | 录音与音量反馈 | 任务完成提醒 |
| --- | --- | --- | --- |
| <img src="assets/images/codex/card-01-quota.png" width="200" alt="周额度和重置时间"> | <img src="assets/images/codex/card-02-threads.png" width="200" alt="对话状态和未读标记"> | <img src="assets/images/codex/card-04-record.png" width="200" alt="录音时长和麦克风音量"> | <img src="assets/images/codex/card-08-completed.png" width="200" alt="任务完成横幅提醒"> |

| 独立离线时钟 | 番茄钟 | 秒表 |
| --- | --- | --- |
| <img src="assets/images/codex/card-12-offline-clock.png" width="200" alt="独立离线时钟"> | <img src="assets/images/codex/card-13-offline-focus.png" width="200" alt="离线番茄钟"> | <img src="assets/images/codex/card-14-offline-stopwatch.png" width="200" alt="离线秒表"> |

Mac 深色连接／语音截图来自正式打包应用，浅色设置和烧录页截图使用隔离的示例数据。
卡片图片为**真实 LVGL 界面在 240 × 320 分辨率下的示例数据渲染**，不是真机照片或硬件验收证据。
界面使用简体中文。[图片来源与复现方法](assets/images/codex/README.zh_CN.md)。

## 最近更新

| 批次 · 日期 | 更新内容 | 升级方式 |
| --- | --- | --- |
| 008 · 2026-10-02 | 整理第 005–007 批及蓝牙 0.5.0 真机结果，合入本地 `master` | 仅源码／文档 |
| 007 · 2026-10-02 | 桌面／固件 0.5.0：硬件信息、USB／蓝牙本机监控和版本比对 | 更新 Mac 应用并烧录匹配固件 |
| 006 · 2026-10-02 | 录音提示保持稳定，停顿不再触发音量低提醒 | 更新助手固件；Mac 程序无需更换 |
| 005 · 2026-10-02 | 桌面 0.4.0：内置四种固件、USB 烧录、默认保留配对与配置 | 替换 Mac 应用即可获得入口；写入卡片须单独确认 |
| 004 · 2026-10-02 | 更新已纳入 `master`，并将其设为默认分支 | 仅源码／文档 |
| 003 · 2026-10-02 | 连续编号更新记录和本页图集 | 仅文档 |
| 002 · 2026-10-02 | 桌面 0.3.1、三页布局、深浅外观与应用图标 | 替换 Mac 应用；外观更新无需烧录 |
| 001 · 2026-10-02 | 录音反馈、对话状态与未读、免打扰任务提醒 | 同时更新 Mac 程序和匹配的卡片固件 |

[完整更新记录与测试结果](docs/codex-updates.zh_CN.md)。下载区产物可能落后于本分支，
用户已确认 P1 音量条和识别正常；新录音提示与其余提醒功能仍待真机验收。

## 功能

| 功能 | 行为 |
| --- | --- |
| 语音 | 按住中键录音，最长 45 秒；松开后查看简体识别结果，确认再发送。Whisper base 与 OpenCC 均在 Mac 本机运行。 |
| 对话 | 每页三条，按真实交互时间排序，展示处理中／排队／需电脑处理／未读状态；切换语音目标并查看回复。 |
| 忙碌对话 | 接口支持时将确认的消息加入原对话队列；发送结果不确定时不自动重试。 |
| 额度 | 一页显示 7 天剩余额度、自动重置时间、最早到期的两次可用重置机会；不会使用重置机会。 |
| 时钟 | 左上角 UTC+8、24 小时制，从连接的 Mac 校时。 |
| Mac 窗口 | 原生五页布局、深浅外观、原创图标、账户／模型检查、USB／蓝牙选择、模型复用。 |
| 设备信息 | USB／蓝牙本机监控硬件、堆／程序／NVS 占用、电量／电压、芯片温度、运行时长、RSSI 与任务／栈；比对当前和所选／内置固件，提供升级入口。需 0.5.0 应用和固件。 |
| 固件烧录 | 内置四种固件或导入本地合并 `.bin`；USB 设备选择、版本／校验展示、默认保留配置、确认后写入、进度与记录。 |
| 反馈与提醒 | 录音阶段和音量指示，完成／需处理横幅，可选声音与 UTC+8 免打扰时段；需要 P1 固件。 |
| 恢复 | 自动重连原 USB/蓝牙设备，在程序运行期间保留草稿和请求去重，丢弃中断录音。 |

软件不增加付费识别或 API 服务，但仍需可用的 Codex 登录账户及其额度，
不提供免费订阅或无限额度。本地语音识别不依赖云端，但 Codex 本身需要互联网。
需要桌面权限的操作仍须在电脑处理。

## 选择固件

| 模式 | 连接 | 需要 Mac | 用途 |
| --- | --- | --- | --- |
| `ble` | 认证蓝牙 BLE | 是 | 无线 Codex 助手；支持原生 Mac 应用 |
| `usb` | USB 数据线 | 是 | 无需网络监听端口的 Codex 助手；支持原生 Mac 应用 |
| `wifi` | 可互通的同一 2.4 GHz 局域网 | 是 | 使用命令行 TLS 程序的 Codex 助手 |
| `offline` | 使用时无需连接 | 否 | 时钟、25/5 番茄钟、秒表 |

四种模式分别构建。Mac 窗口中切换 USB/蓝牙不会更换卡片固件。
ESP32-C3 配有 8 MB Flash、没有 PSRAM，不能独立运行 Codex 或语音模型。

## 使用 Mac 应用

1. 打开 [Releases 下载区](https://github.com/baotoutongqinwei/codex-passport-companion/releases)，选择 ARM64 Mac 应用和配套的蓝牙或 USB 固件。
   要求 Apple 芯片 Mac、macOS 15 或更新版本。应用使用临时签名，未经 Apple 公证，
   新电脑可能需要按系统正常流程校验或由管理员批准。
2. 打开应用的“固件烧录”，选择内置版本或本地合并固件，插入 USB 数据线并扫描卡片。
   默认保留配置；首次安装时按提示选择重置配置。核对设备与数据影响后确认烧录。
   详见[桌面烧录说明](docs/codex-desktop.zh_CN.md#在窗口中烧录固件)。已有卡片仅更新 Mac 程序不需要重新刷机。
3. 安装 Codex 并登录已有 ChatGPT 账户。解压打开 `Codex Passport.app`；
   使用打包应用无需安装 Python、ESP-IDF 或运行终端。
4. 选择已有的 `ggml-base.bin`，或在窗口里下载可选的约 142 MB 语音模型。
   两种方式都会校验哈希，复用模型不会复制文件。
5. 选择与卡片固件一致的连接方式并连接。首次蓝牙配对需要输入卡片上的六位码。
   使用期间保持 Mac 唤醒、应用运行。

详见 [Mac 应用说明](docs/codex-desktop.zh_CN.md)、[全部模式](docs/codex-modes.zh_CN.md)、
[按键与限制](docs/codex-companion.zh_CN.md)。息屏后用三个功能键之一唤醒；
独立电源键会切断供电。不要为了连接卡片而关闭公司网络或外设安全防护。

## 从源码构建

克隆默认应用分支 `master`。
使用 AI 开发时，先阅读 `AGENTS.md`、`docs/README.md`；
项目要求的技能位于 `skills/`。复用已有检出目录时保留本地修改。

固件环境按[环境指南](docs/development/engineering/environment-setup.zh_CN.md)安装并激活
**ESP-IDF 5.5.3**，随后在仓库根目录运行：

```bash
./tools/validate.sh --all --profile ble
# 其他模式：usb、wifi、offline
bash tools/build_variants.sh
```

合并固件位于 `build/variants/<profile>/`，匹配的 ELF、MAP 和刷写分段保存在
`build/firmware/<完整镜像哈希>/`。

Mac 配套程序要求 Python 3.10+ 和相应构建工具：

```bash
bash tools/install_transport.sh
.local/transport-venv/bin/python tools/bootstrap_bridge.py
.local/transport-venv/bin/python bridge/app.py doctor
.local/transport-venv/bin/python bridge/app.py ble
```

构建原生 Mac 窗口需使用 Apple 芯片 Mac，以及标准库目录中包含许可证文件的 Python 发行版：

```bash
.local/transport-venv/bin/python -m pip install -r bridge/desktop-requirements.txt
bash tools/build_desktop.sh
```

产物为 `build/desktop/Codex Passport.app`，含运行环境和 CPU 识别引擎，不含模型权重。
语音引擎初始化需要 Git、CMake、curl、C/C++ 编译器，源码构建与下载会额外占用磁盘。

## 验证与限制

| 项目 | 已有记录 |
| --- | --- |
| 构建 | 第 007 批四种 0.5.0 固件门禁、合并镜像／ELF 归档、ARM64 桌面应用、内置工具／固件、签名和 ZIP 检查通过。 |
| 主机测试 | 87 项助手 Python 测试及 C／BSP／仓库门禁通过；覆盖监控数据、版本比对、固件校验、保留配置边界和桌面互斥。原生中文设备页使用明确标注的示例数据检查布局。 |
| 真机测试 | 蓝牙 0.5.0 通过正式桌面入口保留配置烧录，三个写入段校验、20 秒启动观察、蓝牙重连、状态同步、真实设备读数和构建一致性比对通过。此前确认 P1 音量条／识别、USB 语音／回复、蓝牙 45 秒录音和卡片断电重连。 |
| 未验证 | 卡片与桌面电量对照、传感器精度、持续监控／录音时资源余量、第 006 批聆听提示和图形烧录异常恢复；P1 音效／提醒亮屏、新 Mac、Intel 及长期测试。 |

当前不提供 Intel、Windows、Linux 桌面安装包。Codex 实验性 app-server 队列及额度字段
可能随版本改变，不同账户或版本不保证具有全部功能。草稿和去重保存在内存中，退出前
先核对未决结果。构建通过不等于完整硬件验收。后续安排见[优化清单](docs/codex-improvements.zh_CN.md)。

## 目录与隐私

| 路径 | 内容 |
| --- | --- |
| `main/` | 卡片应用、界面、各传输模式 |
| `components/bsp/` | 共享硬件驱动 |
| `bridge/` | Mac 配套程序、原生窗口、语音集成 |
| `assets/fonts/` | 中文源字体、生成字体及 OFL 许可证 |
| `tests/`、`tools/` | 主机测试、可复现构建和校验工具 |
| `docs/`、`skills/` | 双语说明、计划、AI 开发技能 |

个人 `.local/` 配置、Wi-Fi 密码、TLS 私钥、账户令牌、录音、已安装模型、缓存和构建目录
不进入 Git。临时音频在识别完成或中断后删除。公开问题反馈中不要附带对话内容或凭据。
应用与固件二进制放在 Releases 下载区，不写入源码提交历史。

## 许可与致谢

项目代码保留 FoloToy 的 [MIT 许可证](LICENSE)。中文字体使用
[SIL OFL 1.1](assets/fonts/OFL.txt)，详见[字体来源](assets/fonts/README.zh_CN.md)。
本地识别使用 [whisper.cpp](https://github.com/ggml-org/whisper.cpp)，简体转换使用
[OpenCC](https://github.com/yichen0831/opencc-python)，蓝牙使用
[Bleak](https://github.com/hbldh/bleak)。第三方组件仍适用各自许可证，Mac 应用附带运行组件许可说明。
