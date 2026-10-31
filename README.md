# Rust Boot Manager · Debian 系 Linux

Rust 编写的 GRUB 启动管理核心与 CLI，系统 GTK 3 / Python GI 图形界面。无 Cargo 第三方依赖，无 WebView、Electron、root GUI 或系统常驻特权服务。**v0.5.0 是可编译的开发版本，应先在可恢复的目标发行版虚拟机中验证，再用于真实双启动机器。** 本工程开发期间没有改动主机启动配置，也没有执行真实重启。

## 功能

- 自动读取 `/boot/grub/grub.cfg` 的静态 `menuentry` / 多层 `submenu`；支持引号、注释和 GRUB ID，使用 ID 路径或数字索引，不执行配置脚本。
- 一次性 `grub-reboot` 与永久 `grub-set-default`；永久模式建立 `/etc/default/grub.d/99-rbm.cfg`，设置 `GRUB_DEFAULT=saved` / `GRUB_SAVEDEFAULT=false` 并运行 `update-grub`，成功后验证环境块。
- 写 GRUB 前自动快照，手动备份、列举、恢复；发生普通操作错误时尝试回滚并报告备份编号。
- polkit 独立授权 helper，活动会话首次需要管理员认证，当前窗口内复用授权；关闭窗口后结束，不使用 setuid、不提升 GUI。
- 10 秒至 24 小时延迟重启，systemd transient timer，无轮询守护进程，可跨 GUI 退出继续计时，可取消。
- 显式选择 UEFI BootNext 作为 GRUB 一次性模式不适用时的备用方案，验证固件启动项和写入结果，不更改 BootOrder。
- 现代卡片式英文 / 简体中文 GTK GUI、侧边导航、可视启动项列表、双语 CLI 提示，托盘启动目标/状态/取消快捷项。
- 应用启动器右键动作、Nautilus 背景右键扩展、Dolphin 目录右键服务菜单。
- 诊断输出与有界审计日志，release 使用大小优化和 LTO。

## 构建

```sh
sudo apt install build-essential python3-gi gir1.2-gtk-3.0 \
    grub-common grub2-common polkitd pkexec systemd util-linux xdg-user-dirs efibootmgr \
    gir1.2-ayatanaappindicator3-0.1
cargo test --offline
cargo build --release --offline
./target/release/rbm list --file tests/fixtures/grub.cfg
```

最低 Rust 1.85 / edition 2021；无需联网下载 crate。Debian 12、Ubuntu 22.04 等系统仓库中的编译器可能较旧，请先通过 [rustup](https://rust-lang.github.io/rustup/installation/) 安装 Rust 1.85 或更新工具链；运行已编译安装包无需安装 Rust。GUI 代码为系统 Python，不是纯 Rust GUI；实际启动授权逻辑、解析、备份和恢复均在 Rust 内实现。命令行不需要图形环境，但远程会话是否允许授权由管理员的 polkit 策略决定。建议 CLI 使用已有会话授权代理；不修改默认禁止非活动会话的策略。

## 安装与运行

```sh
sudo scripts/install.sh
rbm gui
rbm gui --lang zh
rbm gui --tray --lang en
rbm list
rbm set once 'gnulinux-simple-实际ID'
rbm set permanent 'gnulinux-advanced-实际ID>gnulinux-实际内核ID'
rbm reboot 60
rbm status
rbm cancel
```

启动项 ID 使用 `rbm list` 输出的 `selector` 字段，不要照抄示例 ID。**设置启动目标不会重启；重启是单独、明确的操作。** `cancel` 仅取消本应用的 `rbm-reboot.timer` 和 service，不清除已设置的启动目标；使用 `rbm clear-once` 或 `rbm efi-clear` 清除对应目标。不会取消其他软件安排的关机。到期后系统已开始关机时无法保证取消成功。

```sh
rbm backup
rbm backups
rbm restore 备份编号
rbm clear-once
rbm efi-list
rbm efi-next 000A
rbm efi-clear
rbm diagnose
rbm logs
rbm plan once '实际selector'
```

`plan` 只校验当前启动项存在且显示计划，不写入文件；完整的文件系统、安全和环境块检查在执行时进行。`list --file PATH` 是开发/诊断用只读解析入口，特权 helper 不接受任意文件路径。

固件条目与 GRUB 条目没有可靠的一一对应关系：程序不会在 GRUB 失败时猜测固件目标，也不会自动重启。用户需要显式通过 `efi-next` 或 GUI 选择活动固件条目。已有的 BootNext 内容保存在 `/var/lib/rust-boot-manager/efi-时间戳.txt`；恢复先前目标请查看该文件，使用 `efi-next 原编号`，原来没有 BootNext 时使用 `efi-clear`。

## Windows 桌面快捷方式

安装 / 升级到 v0.5.0 后，以普通用户执行：

```sh
rbm desktop-shortcut install
```

也可在 GUI 的「重启计划」中点击「创建 Windows 桌面快捷方式」。程序通过 XDG 定位当前用户真实桌面目录，创建可执行的 `rbm-windows.desktop`，兼容 `Desktop` / `桌面` 等本地化路径，不覆盖无关同名文件。如果文件管理器要求，请右键图标选择「允许启动」；GNOME 需桌面图标扩展或文件管理器支持显示桌面图标。安装程序不会使用 root 猜测用户桌面。

点击「启动 Windows」只显示：**是否启动到 Windows？**、一个默认不勾选的 **「以后每次都从 Windows 启动」** 选项，以及 **「是 / 否」** 两个按钮。

- 不勾选：仅下次启动 Windows，保留永久默认系统。
- 勾选：将 Windows 设为永久默认，再重启。
- 点击「否」或关闭窗口：没有系统授权请求、启动配置写入或重启计划。

点击「是」后才通过一次 polkit 授权读取并校验 Windows 目标、设置启动模式和安排 **10 秒后重启**，成功后关闭确认框。窗口不再显示启动项列表、管理器入口或其他功能。已有重启计划或固件 BootNext 会拒绝执行；创建计时器失败时回滚本次启动设置。

确认框可通过 `rbm windows` / `rbm windows --lang zh` 打开。文字可以在普通用户的 `~/.config/rust-boot-manager/windows-dialog.json` 中自定义，示例：

```json
{
  "question": "是否启动到 Windows？",
  "remember_label": "以后每次都从 Windows 启动",
  "yes_label": "是",
  "no_label": "否"
}
```

配置只控制文字，不会自动勾选永久模式。检测到多个 Windows 项时会停止；可额外添加 `"target_selector": "实际Windows选择器"` 明确指定，选择器来自 `rbm list`。示例文件也安装到 `/usr/share/doc/rust-boot-manager/windows-dialog.example.json`。

已确认但尚未到期时可用主应用或 `rbm cancel` 取消计时器；这保留已设置的启动目标。清除一次性目标用 `rbm clear-once`；恢复永久默认值用 `rbm restore ID` 或主应用重新选择。

移除桌面图标：`rbm desktop-shortcut remove`（普通用户）。卸载程序前先运行此命令，或之后手动删除桌面的 `rbm-windows.desktop`；卸载不会遍历和修改每个用户的桌面。应用菜单和原启动器右键动作同样提供 Windows 快捷入口。

## 桌面集成

托盘依赖 Ayatana AppIndicator（兼容旧 AppIndicator）。GNOME 需要启用 AppIndicator/KStatusNotifierItem 扩展；没有托盘宿主时系统无法显示图标。没有 GI 托盘库时保持普通窗口并报告原因，不影响 CLI。关闭窗口在托盘启用时隐藏；托盘“退出”真正退出。

- `.desktop` 文件提供“启动系统托盘”“取消计划重启”动作；支持动作菜单的桌面可在应用图标上右键。
- Nautilus：安装 `python3-nautilus`，重新启动文件管理器/重新登录后，文件夹空白处出现菜单。Debian 13 的 GNOME 默认桌面通常不由 Nautilus 管理，桌面空白右键取决于桌面扩展，不能跨桌面通用安装。
- KDE Dolphin：安装脚本部署 service menu，重新登录或重启 Dolphin 后生效。
- XFCE/Thunar：在“编辑 → 配置自定义动作”添加 `/usr/bin/rbm gui`，勾选目录。不同桌面的真正桌面空白右键接口并不统一，本程序不会修改用户已有的窗口管理器配置。
- 可选自动启动：将 `/usr/share/applications/rust-boot-manager.desktop` 复制到用户 `~/.config/autostart/`，把 `Exec` 改为 `/usr/bin/rbm gui --tray`；默认不自动启动。

## 备份与恢复范围

快照目录 `/var/lib/rust-boot-manager/数字编号/` 为 root 管理，保存：

|文件|恢复方式|
|---|---|
|`grubenv`|恢复原 inode 内的数据，要求尺寸一致|
|`managed.cfg`、`drop-present`|恢复本应用片段或恢复其“不存在”状态|
|`defaults`|显式恢复 `/etc/default/grub`|
|`grub.cfg`|参考副本，**不直接覆盖**生成文件|
|`file-modes`|恢复原始配置文件权限|
|`complete`|完整快照标记|

显式恢复前会再备份一次当前状态，并执行 `update-grub` 重建菜单。**不备份其他 `/etc/default/grub.d/*.cfg`、`/etc/grub.d` 自定义脚本、内核、EFI 分区或 NVRAM 全量状态。** 这不是全盘灾难恢复工具；涉及这些文件时请另做系统备份。快照不自动删除，日志在约 1 MiB 轮换一次并保留一个旧日志。备份保留期由管理员管理。

## 安全边界与兼容限制

固定 `/usr/libexec/rust-boot-manager-helper` 由 pkexec 授权；所有系统命令使用绝对路径和参数数组，清空继承环境，拒绝任意命令/路径、未知启动项、非数字快照 ID、非活动 EFI 编号。敏感路径要求 root 所有、不可被组/其他用户写入、非符号链接；操作使用排他锁，写入前记录审计 BEGIN，之后记录结果。读取受保护列表或日志也需授权。主 GUI 使用进程专属管道连接会话助手，首次认证后在窗口内复用；关闭窗口（包括隐藏到托盘）即断开管道并结束授权。GUI 异常退出时，Linux 父进程死亡信号会结束助手。重新打开窗口后的首次特权操作需要重新认证。切换语言不会关闭授权会话。CLI 每次命令和 Windows 桌面确认框仍各自单独授权；不会保存密码或设置系统全局免密规则。

一次性模式拒绝 Btrfs/ZFS 等未验证的环境块写回布局、LVM/RAID/加密等 GRUB 存储抽象；这些环境优先使用 UEFI BootNext。即使普通 ext4 上通过检查，也需要在虚拟机确认固件实际启动相同 GRUB、GRUB 能清除 `next_entry`。程序不会声称仅凭 Linux 端文件写入即可证明固件端启动成功。

静态解析器不是 GRUB 解释器：由运行期循环/条件生成或外部 `source` 文件产生的条目不在保证范围内；当前系统必须使用 Debian 系标准 `/boot/grub/grub.cfg` 和环境块路径。重复 selector、损坏引号/大括号会失败关闭。其他程序、管理员或内核更新不共享本程序锁，执行前应避免同时更新 GRUB。默认配置在其他片段中被覆盖时，应检查 `rbm diagnose` 和生成的 `grub.cfg`。断电、磁盘损坏、失败回滚、固件拒绝写入仍可能需要从恢复介质人工恢复；详见 [恢复说明](docs/RECOVERY.md)。

## 打包与卸载

```sh
# 推荐发布通用包（需 rustup 的 musl 目标）
rustup target add x86_64-unknown-linux-musl
scripts/build-portable.sh
sudo apt install ./dist/rust-boot-manager_0.5.0_amd64.deb
```

打包脚本依赖 `dpkg-deb`、`readelf` 和 Python 3；本机动态链接构建还需要 `dpkg-shlibdeps`（dpkg-dev）。`scripts/build-deb.sh` 保留本机构建模式，并按实际 ELF 符号生成 libc 依赖，不再固定为 Debian 13 的 libc 版本。通用静态 musl 包不依赖宿主 glibc 版本。临时维护者地址需要在正式发布时替换。DEB 安装不修改启动设置；卸载只移除程序，保留现有启动选择、配置片段、快照和审计日志，避免突然改变默认系统。

手动安装的卸载：先用 `rbm backups` 找到修改前快照，`rbm restore ID`，再运行 `sudo scripts/uninstall.sh`。手动卸载脚本在仍存在本程序 GRUB 片段时会停止，并提示先恢复。如果原快照已经带有片段，按 [恢复说明](docs/RECOVERY.md) 人工移除片段并重建 GRUB 后再卸载。恢复既有默认启动设置是明确的管理操作，不由卸载脚本猜测。用户自行添加的自动启动文件须自行移除。

可在不安装到主机的情况下验证布局：

```sh
DESTDIR=/tmp/rbm-stage scripts/install.sh
DESTDIR=/tmp/rbm-stage scripts/uninstall.sh
```

## 验证

`python3 tests/isolated_system.py` 在 bubblewrap 用户/挂载命名空间内测试真实 GRUB 环境块工具、备份恢复、错误回滚、BootNext、计时器、权限和排他锁；固件与重启调用使用替身，不触碰主机。需要 `bubblewrap` 和启用用户命名空间。`python3 tests/run_gui_smoke.py` 在 Xvfb 和隔离 D-Bus 会话中测试中英界面、页面导航、异步结果处理，以及语言切换后保留选择状态，需要 `xvfb` 和 `dbus-run-session`。

`cargo test --offline` 验证 GRUB 嵌套、真实格式 fixture、引号/变量/花括号、损坏输入、重复选择器、JSON 编码和 EFI 参数验证。`python3 -m py_compile ui/gui.py`、`shellcheck scripts/*.sh`、`desktop-file-validate packaging/rust-boot-manager.desktop` 验证界面与安装资源。测试覆盖和真实启动验收边界见 [测试说明](docs/TESTING.md)。许可证 MIT。

实现参考：[GNU GRUB 手册](https://www.gnu.org/software/grub/manual/grub/grub.html)、[pkexec 文档](https://www.freedesktop.org/software/polkit/docs/latest/pkexec.1.html)、[systemd-run 文档](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)、[efibootmgr 上游](https://github.com/rhboot/efibootmgr)。

## 源码内置图标

主应用、窗口、托盘使用 GNU GRUB 图标；Windows 快捷入口、确认框使用 Windows 11 四窗格图标。
资源在 `assets/icons/`，原始 GRUB 图片及来源说明在 `assets/vendor/`、`assets/NOTICE.md`。
安装到 hicolor 图标主题，不依赖当前桌面主题提供同名图标；GNOME 的 Wayland 应用 ID 同时有对应的隐藏 desktop 映射，以保持任务栏图标一致。
更新后再次执行 `rbm desktop-shortcut install`，会迁移本程序 v0.2.0 创建的旧图标定义，并保留其他用户文件。

## 窗口会话授权（v0.4.0 起）

旧版每个操作都执行一次 pkexec，策略 auth_admin 会要求逐次认证。现在 GUI 首次启动一个经过 polkit 授权的 Rust 会话助手，后续白名单操作复用同一进程。窗口关闭/退出时关闭通信管道，授权随助手退出结束；助手崩溃或断开后，下次操作会重新请求认证。后台托盘启动本身不请求授权，打开管理窗口或明确使用托盘操作时才授权。

客户端和助手仅使用创建者持有的匿名进程管道，没有网络端口、共享套接字、密码文件或可被其他程序复用的全局授权缓存。协议限制参数数目、长度及响应大小；每个请求仍执行完整白名单、文件权限、排他锁和审计检查。`python3 tests/session_client.py` 验证会话复用、错误恢复、关闭后重新创建和异常退出处理；隔离系统测试还验证真实 root helper 的多请求、路径拒绝及父进程死亡清理。

## Debian 系兼容策略（v0.5.0）

不按发行版名称或版本拒绝运行。通过 `/etc/os-release`（回退 `/usr/lib/os-release`）识别 ID / ID_LIKE / PRETTY_NAME，GUI 显示实际系统名称。Debian、Ubuntu、Linux Mint、LMDE、Kali、Pop!_OS、Devuan 等按其系统能力运行；派生版名称识别不等于已经逐一完成真实启动验收。

- 固定系统目录 `/usr/sbin`、`/usr/bin`、`/sbin`、`/bin` 查找白名单工具，兼容 merged-/usr 和 efibootmgr 等工具的路径差异，不使用用户 PATH 执行特权命令。
- 采用 GRUB 2 标准的 `/boot/grub/grub.cfg`、`grubenv`、`/etc/default/grub.d`；不调用 grub-install，也不安装或替换固件加载器。
- 有运行中的 systemd 才启用计划重启、取消和 Windows 组合重启；无 systemd 的派生版仍支持 GRUB 读取、目标设置、快照和恢复。安装包不会把 systemd 作为强制依赖，缺少能力时在写启动设置前拒绝重启。
- UEFI BootNext 取决于 UEFI 启动及 efibootmgr；BIOS 系统保留 GRUB 功能。
- KDE 5/6 菜单分别部署到 kservices5 和 kio 路径，托盘支持 Ayatana / AppIndicator，桌面路径使用 XDG。
- `rbm platform` 无需授权即可查看发行版、init、UEFI 及工具路径；`rbm diagnose` 提供受保护的详细信息。

提供 amd64 静态 musl 通用包，Rust CLI 不依赖 Debian 13 的 glibc。GUI 继续使用目标系统的 Python 3 / GTK 3。其他 CPU 架构可本机构建；aarch64 的 musl 构建入口已提供，但本次仅实际验证 amd64。

Debian 12、Ubuntu 22.04 和 Ubuntu 24.04 使用同一个通用包进行容器安装与 CLI/GTK/会话客户端检查，Debian 13 另有本机只读测试。容器不代表实际重启、固件写入、各桌面托盘或其他派生发行版已完成硬件验收。具体结果见 `docs/TESTING.md` 和 `dist/compat-*.log`。

## 自动发布（CD）

GitHub Actions 在推送 `vX.Y.Z` 标签后发布 GitHub Release。标签版本必须与
`Cargo.toml` 一致。发布前运行 Debian 12 / 13、Ubuntu 22.04 / 24.04 的完整 CI；
任一检查失败均不发布。通过后复用 Debian 12 任务已测试的静态 musl amd64 安装包，
同时上传当前提交的源码归档和 `SHA256SUMS`。所有附件上传成功后才公开 Release。
无需配置个人访问令牌，只有发布任务获得仓库内容写权限。

```sh
# 先更新 Cargo.toml / Cargo.lock 中的版本并提交、推送
git tag -a v0.5.0 -m 'Release v0.5.0'
git push origin v0.5.0
```

首次运行若失败，修正问题后应使用新版本标签；仅临时上传故障可在 Actions 中重跑，
流程允许补全尚未公开的草稿，不覆盖已经公开的 Release。
