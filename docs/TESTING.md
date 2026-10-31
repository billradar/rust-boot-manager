# 验证与发布前验收

无需 root 的测试：

```sh
cargo test --offline
cargo build --release --offline
./target/release/rbm list --file tests/fixtures/grub.cfg
python3 -m py_compile ui/gui.py packaging/rbm-nautilus.py
shellcheck scripts/*.sh
desktop-file-validate packaging/rust-boot-manager.desktop
scripts/build-deb.sh
dpkg-deb --info dist/*.deb
python3 tests/package_smoke.py
python3 tests/isolated_system.py
python3 tests/run_gui_smoke.py
```

应在 Debian 13 虚拟机快照上逐项执行以下真实集成测试。开发环境不执行这些会更改主机启动状态的操作：

1. BIOS+ext4、UEFI+ext4 双启动环境：比较 `rbm list` 和实际 GRUB 菜单，验证子菜单 selector；包含 Windows 固件条目。
2. 普通用户拒绝 polkit 后，确认 grubenv、默认配置和计时器没有改变；非活动会话、无授权代理会话应失败关闭。
3. `set once` 后 `grub-editenv list` 出现正确 next_entry，重启一次到目标，下一次恢复原默认项；测试分离 /boot。Btrfs、LVM、加密/RAID 布局应拒绝 GRUB 一次性并可手动选择 BootNext。
4. `set permanent` 后重启至少两次，确认 saved_entry 与实际结果一致；执行 `restore` 后恢复原默认行为。检查其他默认片段覆盖的情况。
5. 模拟 update-grub/grub-set-default 失败和只读文件系统，确认错误包含快照编号和回滚结果。断电恢复只能用虚拟机快照/恢复介质验收。
6. 创建快照后改变默认配置，再 restore；损坏完整标记、symlink 快照、路径遍历 ID 必须拒绝；测试第二个进程的互斥锁。
7. `efi-next XXXX` 只修改 BootNext，不改 BootOrder；复核原 BootNext 的审计副本，验证下一次固件消费、清除和失败回滚。
8. `reboot 120` 后关闭 GUI，确认 timer 仍有效；及时 `cancel` 后等待过期时间确认没有重启；重复安排不应覆盖已有计时器；拒绝 <10 秒和 >86400 秒延时。
9. GTK 中英切换、错误显示、授权期间界面不冻结、所有按钮对应用于 CLI 的操作；托盘缺失回退窗口；有托盘宿主时隐藏、打开和退出。Nautilus、Dolphin 分别重新登录后检查右键。
10. 安装/升级/移除 DEB 不改变现有启动配置；移除时停止本程序计时器，保留快照。手动卸载要求先恢复配置。

自动测试不等同于真实 GRUB/固件、polkit 会话或 systemd 重启验收。资源占用需在目标桌面使用 `/usr/bin/time -v rbm gui`、`ps`/`smem` 量测；无目标环境测量时不承诺具体 GUI 内存值。

## 本次开发实测（2026-10-31）

- Rust 1.85.1：24 项单元测试通过，离线 release 编译通过。
- 隔离系统测试：97 项断言通过；使用真实 grub-editenv / grub-reboot / grub-set-default，update-grub、findmnt、GRUB probe、固件和 systemd 命令为隔离替身。
- 安装/卸载 staging 与 polkit XML 策略检查通过；静态检查通过。
- Xvfb 中英文 GUI：启动项选择、模式、重启按钮命令、5 页导航、异步错误显示和切换语言保留状态通过；截图保存在 dist/。截图使用测试 fixture，不代表当前主机的实际系统列表。为了稳定截图，测试关闭动画，并在抓图前强制 GTK 3 布局与绘制。
- 没有执行主机启动配置写入、真实重启、固件写入或真实 polkit 管理员认证。真实启动和桌面托盘/右键集成仍需按上述虚拟机清单验收。

## Windows 桌面快捷入口（v0.2.0）

- 普通用户的隔离 HOME/XDG 目录验证桌面路径定位（包含「桌面」中文目录）、0755 可执行权限、重复安装、同名文件/符号链接保护和移除。不会写实际桌面。
- 真实 GTK 确认框在中英文 Xvfb 会话验证：确认前只有枚举，不设置启动目标或重启；授权被拒后无已安排状态；确认按钮发送唯一的 windows-reboot 请求；多目标要求选择，无目标时禁止确认；取消已安排的重启只请求取消计时器。
- root helper 隔离测试验证 Windows 标签、一次性 next_entry 与 10 秒 systemd 计时器、永久设置不变、计时器失败回滚、重复计划拒绝、固件 BootNext 冲突拒绝。旧版 grub-reboot 的 prev_saved_entry 恢复机制若尝试改动 saved_entry，也必须回滚并拒绝重启。
- 桌面管理器实际显示图标、首次信任提示、真实 polkit 授权和重启到 Windows 需在目标桌面 / 虚拟机确认；未对主机执行真实重启。

## v0.3.0 简化确认框与图标

桌面窗口只有 Windows 11 图标、问题文字、默认未勾选的永久启动选项和是/否按钮。确认前不调用任何 CLI，按「否」退出；按「是」只发起一次组合授权操作，不勾选为 once，勾选为 permanent。Xvfb 测试在独立 dbus-run-session 中运行，避免与本机已运行应用的相同 application ID 相互激活。

GRUB 与 Windows 11 图标资源直接随包安装；原始 GRUB 图片、嵌入 SVG 和来源说明均在 assets/。验证图标渲染、应用 ID desktop 映射，以及 v0.2.0 用户桌面图标向新模板的安全迁移。隔离系统测试新增自动目标、永久模式成功、永久模式调度失败回滚和多 Windows 歧义拒绝。

## v0.4.0 窗口授权会话

实际异步管道客户端验证同一进程处理多个请求、操作错误后继续使用、关闭后建立新会话及助手异常退出。Rust 协议测试覆盖分帧、截断、超大参数、非法 UTF-8、关闭及有界响应。隔离 root helper 一次连接验证多个真实命令，并验证非法路径请求仍被拒绝；父进程死亡测试特意保留输入管道写端，证明助手依靠 PDEATHSIG 退出，而不是仅依赖 EOF。

真实桌面首次认证后应观察只有一个 helper --session；刷新列表、诊断、状态等只读操作不再弹出认证。关闭窗口后 helper 应消失；重新打开并使用特权操作时重新认证。验证只读请求期间 grubenv 哈希不变，且无重启计时器。

## v0.5.0 Debian 系兼容验收

|环境|实际验证内容|结果|
|---|---|---|
|Debian 13 本机|静态/动态 CLI、平台检测、GTK Xvfb、97 项隔离后端断言|通过|
|Debian 12 容器|同一静态 DEB 安装、CLI、staging、XDG 图标、会话客户端、中英 GTK|通过|
|Ubuntu 22.04 容器|同上，Python 3.10 / 较旧 GTK / glibc 用户空间|通过|
|Ubuntu 24.04 容器|同上|通过|

使用官方容器镜像 `debian:12`、`ubuntu:22.04`、`ubuntu:24.04`，只读挂载源码并在容器临时目录运行测试。日志保存在 dist/compat-*.log，成功标记为 DEBIAN_FAMILY_RUNTIME_OK。本次没有对宿主机执行 apt 安装、GRUB 写入或重启；宿主机已安装的 v0.4.0 保持原状。

原生 GNU 和静态 musl 分别通过 24 项单元测试及 97 项隔离集成断言。新增发行版标识解析、固定工具目录查找、efibootmgr 迁移路径，以及无 systemd 时读取/设置/恢复仍可用、重启组合操作不写启动状态的检查。通用安装包的 ELF 无 NEEDED 动态库依赖；本机动态构建的 libc 约束由 dpkg-shlibdeps 自动产生。

以上是用户空间与隔离逻辑验收，不代表各发行版的实际固件、真实重启或所有桌面集成已验证。Linux Mint、LMDE、Kali、Pop!_OS、Devuan 等只有发行版检测逻辑及对应基底/能力兼容设计，尚未逐一完成发行版硬件验收。CI 已覆盖 Debian 12/13 与 Ubuntu 22.04/24.04 的矩阵。
