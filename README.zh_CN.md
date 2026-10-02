[English](README.md) · **简体中文**

# Codex 随行助手

基于 [FoloToy AI Passport](https://gitee.com/FoloToy/ai-passport) 的随身 Codex 助手：
在 240 × 320 卡片上确认语音输入、切换对话、查看回复与周额度。
Codex 和本地语音识别运行在 Mac 上，卡片负责显示、录音和按键交互。
另外提供无需电脑的离线时钟、番茄钟、秒表固件。

这是基于 FoloToy 完整项目开发的社区应用，并非 OpenAI 或 FoloToy 官方产品。
应用位于 `feature/codex-companion` 分支，保留上游历史和可复用 BSP。

## 功能

| 功能 | 行为 |
| --- | --- |
| 语音 | 按住中键录音，最长 45 秒；松开后查看简体识别结果，确认再发送。Whisper base 与 OpenCC 均在 Mac 本机运行。 |
| 对话 | 浏览最近的 Codex 对话、切换语音目标、翻阅回复、跳到最新消息。 |
| 忙碌对话 | 接口支持时将确认的消息加入原对话队列；发送结果不确定时不自动重试。 |
| 额度 | 一页显示 7 天剩余额度、自动重置时间、最早到期的两次可用重置机会；不会使用重置机会。 |
| 时钟 | 左上角 UTC+8、24 小时制，从连接的 Mac 校时。 |
| Mac 窗口 | 双击启动、账户/模型检查、USB/蓝牙选择、按需下载或复用模型。 |
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
2. 按[固件说明](docs/development/engineering/firmware-layout.zh_CN.md)，将选定的
   **合并完整固件写入 `0x0`**。刷写可能重置已有配置。已经运行本助手的卡片，仅更新
   Mac 程序不需要重新刷机。
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

克隆本仓库默认的应用分支。使用 AI 开发时，先阅读 `AGENTS.md`、`docs/README.md`；
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
| 构建 | 完整蓝牙门禁、合并镜像/调试归档校验、原生 Mac 应用通过；其他固件模式有此前构建记录。 |
| 主机测试 | 54 项助手测试及仓库/BSP 检查通过，覆盖回执丢失、防重复、队列、协议、字体覆盖、模型校验。 |
| 真机测试 | USB 语音/回复往返、此前蓝牙程序下的 45 秒录音、原生 Mac 蓝牙状态同步和一次卡片断电自动恢复通过。 |
| 未验证 | 新 Mac 安装/权限、Intel 支持、原生窗口 USB 真机、长时间休眠唤醒、重复无线干扰、新窗口下 45 秒真实录音。 |

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
