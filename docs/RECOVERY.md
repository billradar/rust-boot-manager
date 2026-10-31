# 恢复手册

如果尚可启动 Debian，先 `rbm diagnose`、`rbm logs`、`rbm backups`，记录失败信息和自动备份编号。所有 `rbm set` 都不会自动重启。

- 错误的一次性 GRUB 目标：`rbm clear-once`。
- 错误的固件 BootNext：`rbm efi-clear`；这不改变 BootOrder。
- 延迟重启：`rbm cancel`；它不清除启动目标。
- 还原配置：`rbm restore 数字编号`。该操作恢复 `/etc/default/grub`、本程序片段和 grubenv，然后重新生成 grub.cfg；先自动备份当前状态。
- 去掉永久模式：优先恢复启用前快照。如果不保留旧默认值，管理员可以检查并删除 `/etc/default/grub.d/99-rbm.cfg`，确认 `/etc/default/grub` 中 `GRUB_DEFAULT` 设置正确，再 `sudo update-grub`。若其他片段覆盖默认值，也需要检查它们。

如果无法启动，用 Debian 13 安装介质的 rescue 模式，挂载根分区、独立 /boot 和 EFI 分区，并正确准备 chroot 的 /dev、/proc、/sys。**根据本机分区布局操作，勿照抄不确定的设备名。** 在 chroot 中检查 `/var/lib/rust-boot-manager/` 的快照，恢复 `defaults` 至 `/etc/default/grub`，按 `drop-present` 恢复/移除 managed fragment，再运行 `update-grub`。

快照的 `grub.cfg` 是取证参考，不应覆盖已经更新了内核/分区布局的生成菜单。`grubenv` 尺寸变化、文件系统不支持 GRUB 写回或环境块损坏时不要直接使用 `cp` 替换环境块；请先查阅系统 GRUB 文档，确认需要重建后再使用 `grub-editenv`，重新设置 saved_entry。NVRAM 不包含在 GRUB 快照内；固件 BootNext 使用 `efibootmgr -N` 清除。必要时由管理员根据本机 EFI 分区和固件状态修复启动加载器；本工具不自动运行 `grub-install`。

日志路径：`/var/lib/rust-boot-manager/audit.log` 和 `audit.previous.log`，权限 0600；快照可能包含启动参数等敏感信息，不应公开上传全部内容。
