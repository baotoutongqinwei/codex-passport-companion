<p align="right">
  <strong>简体中文</strong> · <a href="CI-build-and-release.md">English</a>
</p>

# 自动构建与发布（CI / Build & Release）

`.github/workflows/build-firmware.yml` 支持手动构建，必须选择 `profile`：
`ble`（默认）、`usb`、`wifi` 或 `offline`。分支和 tag 推送均不触发该工作流。
本文件与工作流一同维护。

在 Actions 选择 **Build firmware**，选择应用分支和模式，然后运行。工作流恢复
ccache，使用 ESP-IDF 5.5.3 为 ESP32-C3 执行
`./tools/validate.sh --firmware --profile <profile>`，核验合并镜像片段和 8 MB Flash
布局，并上传 `build/variants/<profile>/FoloToy-AI-Passport-full.bin`，artifact 名称为
`codex-passport-<profile>-<commit>`。所有 Action 固定到完整 commit SHA；构建仅有
`contents: read` 权限。

Release 由维护者在核验具体文件和测试证据后单独发布。提供 Mac 应用、明确命名的
`codex-passport-<profile>-full-0x0.bin`、SHA-256 校验表和清单。创建 tag 不会自动
发布默认 Wi-Fi 固件。每个产物需要记录构建来源，并区分历史真机测试与未刷入的重新
构建；源码 tag 本身不能证明已有二进制由该 tag 构建。

## 在线烧录

使用浏览器在本机完成写入与校验，固件不会上传服务器。打开 **在线刷机工具**：

`https://ai-passport.folotoy.cn/tools/web-flasher/`

步骤：连接设备（USB JTAG/serial debug unit）→ 选择对应模式的合并固件 `codex-passport-<profile>-full-0x0.bin` → 选择波特率（如 460800）→ 从 `0x0` 开始写入。目标是 8MB Flash 板卡，无需其它参数。

## Release 标题

当本仓库从同一棵源码树发布多个不同应用时，只有版本号看不出这个 Release 是哪个应用。给每个 tag 起一个
同时带版本与应用名的名字，并确保 Release 标题两者都显示。

- **Tag 命名约定**：按 `v<版本>-<应用名>` 小写连字符命名，例如 `v0.1.0-voice-keychain`、
  `v1.0.0-pocket-pomodoro`。`<应用名>` 是该 Release 构建的应用（见
  相对仓库根目录的 `docs/reference/<username>/<app-name>/` 档案命名）。多应用共享同一棵树时，只写版本号的 tag 会有歧义。
- **发布成功后，核对 Release 标题**：发布时把标题设为 tag 名，使命名正确的 Release 显示成
  `v0.1.0-voice-keychain`。若 tag 没带应用名，或标题一眼看不出是哪个应用，就编辑该 Release
  （GitHub：`Edit release`；GitLab：编辑 tag），让标题为 `<版本> <应用名>`，例如 `v0.1.0 Voice
  Keychain`。快速扫一遍 Release 列表，就能区分每个 Release 是哪个应用。
- **标题与 tag 保持一致**：用 `<版本>-<应用名>`，让应用名在 tag 列表和 Release 列表里都可见。不要只靠
  人类可读的正文承载应用名。

## 变更日志准备

普通功能、应用和文档 PR 不修改中英文变更日志。创建并推送发布 tag 前，发布负责人需要：

1. 确认上一版本，并检查此后已合并的 PR，以及对应的产品和应用权威文档。
2. 汇总用户可见功能、修复、兼容性变化和发布流程变化；忽略内部重构、CI 维护、拼写修复与生成文件刷新。
3. 同时更新 `docs/CHANGELOG.md` 和 `docs/CHANGELOG.zh_CN.md`，把本次发布条目放入
   `## <tag> - YYYY-MM-DD` 标题下，保留一个新的 `Unreleased` 章节，再提交发布准备变更。

现有 `Unreleased` 条目只作为待核对输入：必须与实际合并内容及目标版本核对，不能直接照搬。该发布准备
变更是共享变更日志的唯一写入方，并且必须包含在 tag 所指向的 commit 中。

## Release 说明

Release 只有在合并固件与它的 Release 说明一起发布时才完整。发布 Release 后，要写一份
说明，向可能没读过仓库的用户解释这次构建。覆盖三块：

- **功能（What's new / 功能）**：本次 Release 相对上一版新增或变更的功能、行为或修复。面向用户，
  不是 commit 日志。
- **方法（How to build / 方法）**：运行 `./tools/validate.sh --firmware --profile <profile>` 生成并校验合并固件，
  明确从 `0x0` 烧录的产物为 `FoloToy-AI-Passport-full.bin`。单独执行 `idf.py build`
  仅做增量编译，不生成也不校验合并完整镜像，不能作为交付命令的替代。
- **使用（How to use / 使用）**：如何烧录（上方在线刷机工具），以及本次 Release 的关键交互或硬件
  要求。

用英文写 Release 说明（项目双语时再配一份简体中文），并在 GitHub/GitLab Release 上链接它们。
用户可见摘要以发布准备阶段的变更日志为依据，确保两者一致。

## 相关文件

- `.github/workflows/build-firmware.yml`：本流水线定义。
- 详见 `docs/hardware-design/AI_HARDWARE_DEVELOPMENT_GUIDE.md`（硬件/烧录细节）。
