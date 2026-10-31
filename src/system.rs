use crate::{grub, platform};
use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::Path,
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};
pub type R<T> = Result<T, String>;
pub const CFG: &str = "/boot/grub/grub.cfg";
const ENV: &str = "/boot/grub/grubenv";
const DROP: &str = "/etc/default/grub.d/99-rbm.cfg";
const STATE: &str = "/var/lib/rust-boot-manager";
const FILES: [(&str, &str); 4] = [
    (ENV, "grubenv"),
    (DROP, "managed.cfg"),
    ("/etc/default/grub", "defaults"),
    (CFG, "grub.cfg"),
];
unsafe extern "C" {
    fn geteuid() -> u32;
    fn flock(fd: i32, op: i32) -> i32;
}
fn valid_snapshot_id(id: &str) -> bool {
    !id.is_empty() && id.len() <= 30 && id.bytes().all(|b| b.is_ascii_digit())
}
pub fn uid() -> u32 {
    unsafe { geteuid() }
}
pub fn root() -> bool {
    uid() == 0
}
pub fn run(program: &str, args: &[&str]) -> R<String> {
    let resolved = platform::tool(program)?;
    let o = Command::new(&resolved)
        .args(args)
        .env_clear()
        .env("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")
        .env("LC_ALL", "C")
        .output()
        .map_err(|e| format!("{program}: {e}"))?;
    if !o.status.success() {
        return Err(format!(
            "{program}: {} {}",
            o.status,
            String::from_utf8_lossy(&o.stderr)
        ));
    }
    Ok(String::from_utf8_lossy(&o.stdout).into_owned())
}
fn secure(path: &Path, directory: bool) -> R<()> {
    let m = fs::symlink_metadata(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if m.uid() != 0
        || m.mode() & 0o022 != 0
        || m.file_type().is_symlink()
        || (directory && !m.is_dir())
        || (!directory && !m.is_file())
    {
        return Err(format!(
            "Unsafe ownership/type/mode / 不安全的权限: {}",
            path.display()
        ));
    }
    Ok(())
}
fn parents(path: &Path) -> R<()> {
    if let Some(p) = path.parent() {
        for a in p.ancestors() {
            secure(a, true)?;
        }
    }
    Ok(())
}
fn check_file(path: &str, optional: bool) -> R<()> {
    let p = Path::new(path);
    parents(p)?;
    match fs::symlink_metadata(p) {
        Ok(_) => secure(p, false),
        Err(e) if optional && e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}
pub fn lock() -> R<File> {
    parents(Path::new(STATE))?;
    match fs::create_dir(STATE) {
        Ok(()) => fs::set_permissions(STATE, fs::Permissions::from_mode(0o700))
            .map_err(|e| e.to_string())?,
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
        Err(e) => return Err(e.to_string()),
    }
    secure(Path::new(STATE), true)?;
    let f = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(0x20000)
        .open(format!("{STATE}/lock"))
        .map_err(|e| e.to_string())?;
    use std::os::fd::AsRawFd;
    if unsafe { flock(f.as_raw_fd(), 2 | 4) } != 0 {
        return Err("Another operation is running / 另一个操作正在运行".into());
    }
    Ok(f)
}
fn atomic(path: &str, bytes: &[u8], mode: u32) -> R<()> {
    check_file(path, true)?;
    let tmp = format!("{path}.rbm-{}", std::process::id());
    let mut f = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(mode)
        .open(&tmp)
        .map_err(|e| e.to_string())?;
    let result = (|| {
        f.set_permissions(fs::Permissions::from_mode(mode))
            .map_err(|e| e.to_string())?;
        f.write_all(bytes).map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
        fs::rename(&tmp, path).map_err(|e| e.to_string())?;
        File::open(Path::new(path).parent().unwrap())
            .and_then(|f| f.sync_all())
            .map_err(|e| e.to_string())
    })();
    if result.is_err() {
        let _ = fs::remove_file(tmp);
    }
    result
}
pub fn read_entries() -> R<Vec<grub::Entry>> {
    grub::parse(&fs::read_to_string(CFG).map_err(|e| format!("{CFG}: {e}"))?)
}
pub fn backup() -> R<String> {
    for (p, _) in FILES {
        check_file(p, p == DROP)?;
    }
    let env = fs::read(ENV).map_err(|e| e.to_string())?;
    if env.len() != 1024 || !env.starts_with(b"# GRUB Environment Block\n") {
        return Err(
            "Invalid or unsupported grubenv; expected a 1024-byte environment block".into(),
        );
    }
    let id = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos()
        .to_string();
    let dir = format!("{STATE}/{id}");
    fs::create_dir(&dir).map_err(|e| e.to_string())?;
    fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).map_err(|e| e.to_string())?;
    for (p, n) in FILES {
        let data = if Path::new(p).exists() {
            fs::read(p).map_err(|e| e.to_string())?
        } else {
            Vec::new()
        };
        atomic(&format!("{dir}/{n}"), &data, 0o600)?;
    }
    let modes = FILES
        .iter()
        .map(|(p, n)| {
            format!(
                "{n}={:o}\n",
                fs::metadata(p).map(|m| m.mode() & 0o777).unwrap_or(0o644)
            )
        })
        .collect::<String>();
    atomic(&format!("{dir}/file-modes"), modes.as_bytes(), 0o600)?;
    atomic(
        &format!("{dir}/drop-present"),
        if Path::new(DROP).exists() {
            b"yes"
        } else {
            b"no"
        },
        0o600,
    )?;
    atomic(&format!("{dir}/complete"), b"rbm-snapshot-v1\n", 0o600)?;
    Ok(id)
}
fn snapshot(id: &str) -> R<String> {
    if !valid_snapshot_id(id) {
        return Err("Invalid snapshot ID / 快照编号无效".into());
    }
    let d = format!("{STATE}/{id}");
    secure(Path::new(&d), true)?;
    for n in [
        "grubenv",
        "managed.cfg",
        "defaults",
        "grub.cfg",
        "drop-present",
        "complete",
        "file-modes",
    ] {
        check_file(&format!("{d}/{n}"), false)?;
    }
    if fs::read_to_string(format!("{d}/complete")).map_err(|e| e.to_string())?
        != "rbm-snapshot-v1\n"
    {
        return Err("Incomplete snapshot".into());
    }
    Ok(d)
}
fn snapshot_mode(directory: &str, name: &str) -> R<u32> {
    let text = fs::read_to_string(format!("{directory}/file-modes")).map_err(|e| e.to_string())?;
    let value = text
        .lines()
        .find_map(|l| l.strip_prefix(&format!("{name}=")))
        .ok_or("Missing file mode")?;
    let mode = u32::from_str_radix(value, 8).map_err(|_| "Invalid snapshot mode")?;
    if mode > 0o777 || mode & 0o022 != 0 {
        return Err("Unsafe snapshot mode".into());
    }
    Ok(mode)
}
fn restore_data(id: &str, defaults: bool) -> R<()> {
    let d = snapshot(id)?;
    let presence = fs::read_to_string(format!("{d}/drop-present")).map_err(|e| e.to_string())?;
    if presence != "yes" && presence != "no" {
        return Err("Invalid snapshot presence marker".into());
    }
    let data = fs::read(format!("{d}/grubenv")).map_err(|e| e.to_string())?;
    if !data.starts_with(b"# GRUB Environment Block\n") || data.len() != 1024 {
        return Err("Invalid or unsupported grubenv snapshot".into());
    }
    let defaults_mode = snapshot_mode(&d, "defaults")?;
    let managed_mode = snapshot_mode(&d, "managed.cfg")?;
    // Never restore generated grub.cfg: regenerate from the current scripts.
    if defaults {
        atomic(
            "/etc/default/grub",
            &fs::read(format!("{d}/defaults")).map_err(|e| e.to_string())?,
            defaults_mode,
        )?;
    }
    if presence == "yes" {
        atomic(
            DROP,
            &fs::read(format!("{d}/managed.cfg")).map_err(|e| e.to_string())?,
            managed_mode,
        )?;
    } else {
        check_file(DROP, true)?;
        if Path::new(DROP).exists() {
            fs::remove_file(DROP).map_err(|e| e.to_string())?;
        }
    }
    // grubenv may carry filesystem-specific layout; preserve its inode.
    check_file(ENV, false)?;
    let mut f = OpenOptions::new()
        .write(true)
        .custom_flags(0x20000)
        .open(ENV)
        .map_err(|e| e.to_string())?;
    if f.metadata().map_err(|e| e.to_string())?.len() != data.len() as u64 {
        return Err("grubenv size changed; manual recovery required".into());
    }
    f.write_all(&data)
        .and_then(|_| f.sync_all())
        .map_err(|e| e.to_string())?;
    Ok(())
}
fn transaction(action: impl FnOnce() -> R<()>, defaults: bool, regenerate: bool) -> R<String> {
    let id = backup()?;
    match action() {
        Ok(()) => Ok(format!("OK; backup / 备份: {id}")),
        Err(e) => {
            let recovery = restore_data(&id, defaults).and_then(|_| {
                if regenerate {
                    run("/usr/sbin/update-grub", &[]).map(|_| ())
                } else {
                    Ok(())
                }
            });
            Err(format!(
                "{e}\nBackup / 备份: {id}; rollback / 回滚: {recovery:?}"
            ))
        }
    }
}
fn verify_env(key: &str, value: &str) -> R<()> {
    let text = run("/usr/bin/grub-editenv", &[ENV, "list"])?;
    if !text.lines().any(|l| l == format!("{key}={value}")) {
        return Err("GRUB write verification failed".into());
    }
    Ok(())
}
fn validate_set(mode: &str, selector: &str) -> R<()> {
    if !["once", "permanent"].contains(&mode) {
        return Err("Mode must be once or permanent".into());
    }
    check_file(CFG, false)?;
    if !read_entries()?.iter().any(|e| e.selector == selector) {
        return Err("Unknown GRUB entry / 未知启动项".into());
    }
    if mode == "once" {
        let cfg = fs::read_to_string(CFG).map_err(|e| e.to_string())?;
        if !cfg.contains("next_entry") || !cfg.contains("save_env next_entry") {
            return Err("GRUB lacks next_entry handling; run update-grub first".into());
        }
        let fstype = run("/usr/bin/findmnt", &["-n", "-o", "FSTYPE", "-T", ENV])?;
        if !["ext2", "ext3", "ext4", "vfat"].contains(&fstype.trim()) {
            return Err("Cannot guarantee GRUB environment reset on this filesystem; use explicit UEFI BootNext / 此文件系统请使用 UEFI BootNext".into());
        }
        let abstractions = run("/usr/sbin/grub-probe", &["--target=abstraction", ENV])?;
        if !abstractions.trim().is_empty() {
            return Err("GRUB storage abstraction detected; use UEFI BootNext".into());
        }
        let source = run("/usr/bin/findmnt", &["-n", "-o", "SOURCE", "-T", ENV])?;
        if !source.trim().starts_with("/dev/")
            || source.contains("/mapper/")
            || source.contains("/md")
        {
            return Err(
                "Complex /boot storage is unsupported for one-shot; use UEFI BootNext".into(),
            );
        }
    }
    Ok(())
}
fn apply_set(mode: &str, selector: &str) -> R<()> {
    if mode == "permanent" {
        atomic(
            DROP,
            b"# Managed by Rust Boot Manager\nGRUB_DEFAULT=saved\nGRUB_SAVEDEFAULT=false\n",
            0o644,
        )?;
        run("/usr/sbin/update-grub", &[])?;
        if !read_entries()?.iter().any(|e| e.selector == selector) {
            return Err("Selected entry disappeared after regenerating GRUB / 重建 GRUB 后目标启动项已不存在".into());
        }
        run("/usr/sbin/grub-set-default", &[selector])?;
        run("/usr/bin/grub-editenv", &[ENV, "unset", "next_entry"])?;
        verify_env("saved_entry", selector)?;
        let cfg = fs::read_to_string(CFG).map_err(|e| e.to_string())?;
        if !cfg.contains("${saved_entry}") {
            return Err("Generated GRUB configuration does not use saved_entry".into());
        }
    } else {
        run("/usr/sbin/grub-reboot", &[selector])?;
        verify_env("next_entry", selector)?;
    }
    Ok(())
}
pub fn set(mode: &str, selector: &str) -> R<String> {
    validate_set(mode, selector)?;
    transaction(|| apply_set(mode, selector), false, mode == "permanent")
}
pub fn windows_title(title: &str) -> bool {
    let leaf = title.rsplit(" / ").next().unwrap_or(title);
    leaf.split(|c: char| !c.is_ascii_alphanumeric())
        .any(|word| word.eq_ignore_ascii_case("windows"))
}
pub fn windows_reboot(mode: &str, requested: Option<&str>) -> R<String> {
    platform::require_systemd()?;
    // Revalidate in the privileged process; never trust the desktop label alone.
    check_file(CFG, false)?;
    let targets: Vec<_> = read_entries()?
        .into_iter()
        .filter(|e| windows_title(&e.title))
        .collect();
    let target = if let Some(selector) = requested {
        targets.iter().find(|e| e.selector == selector).ok_or(
            "Selected target is not a recognized Windows entry / 所选目标不是 Windows 启动项",
        )?
    } else {
        if targets.len() != 1 {
            return Err("Expected exactly one Windows entry. Set target_selector in windows-dialog.json if multiple entries exist / 未找到唯一的 Windows 启动项；多个目标时请在配置中指定 target_selector".into());
        }
        &targets[0]
    };
    let selector = target.selector.as_str();
    validate_set(mode, selector)?;
    // Firmware BootNext would bypass the selected GRUB menu. Do not silently erase it.
    if Path::new("/sys/firmware/efi/efivars").is_dir() {
        for entry in fs::read_dir("/sys/firmware/efi/efivars").map_err(|e| e.to_string())? {
            if entry
                .map_err(|e| e.to_string())?
                .file_name()
                .to_string_lossy()
                .starts_with("BootNext-")
            {
                return Err("Firmware BootNext is already set. Review/clear it in UEFI settings first / 已有固件 BootNext，请先在管理器中核对或清除".into());
            }
        }
    }
    let timer = run(
        "/usr/bin/systemctl",
        &[
            "show",
            "rbm-reboot.timer",
            "rbm-reboot.service",
            "-p",
            "ActiveState",
            "--value",
        ],
    )?;
    if timer.lines().any(|line| {
        !matches!(
            line.trim()
                .strip_prefix("ActiveState=")
                .unwrap_or(line.trim()),
            "inactive" | "failed" | ""
        )
    }) {
        return Err(
            "A restart is already pending; cancel it first / 已有重启计划，请先取消".into(),
        );
    }
    // One authorization + lock covers selection and scheduling. Roll back grubenv
    // if systemd refuses the timer (including an already existing restart).
    let result = transaction(
        || {
            let before = run("/usr/bin/grub-editenv", &[ENV, "list"])?;
            let saved_before = before.lines().find(|line| line.starts_with("saved_entry="));
            apply_set(mode, selector)?;
            let after = run("/usr/bin/grub-editenv", &[ENV, "list"])?;
            if mode == "once"
                && saved_before != after.lines().find(|line| line.starts_with("saved_entry="))
            {
                return Err("GRUB attempted to change the saved default; restoring original settings / GRUB 尝试更改永久默认项，已进入恢复流程".into());
            }
            reboot("10")?;
            Ok(())
        },
        false,
        mode == "permanent",
    )?;
    Ok(format!("Windows restart in 10 seconds / 10 秒后启动到 Windows\n{result}\nrbm cancel: cancel restart (boot target retained) / 取消重启（保留启动目标）"))
}
pub fn restore(id: &str) -> R<String> {
    snapshot(id)?;
    transaction(
        || {
            restore_data(id, true)?;
            run("/usr/sbin/update-grub", &[])?;
            Ok(())
        },
        true,
        true,
    )
}
pub fn backups() -> R<String> {
    let mut ids = Vec::new();
    for e in fs::read_dir(STATE).map_err(|e| e.to_string())? {
        let n = e
            .map_err(|e| e.to_string())?
            .file_name()
            .to_string_lossy()
            .into_owned();
        if snapshot(&n).is_ok() {
            ids.push(n);
        }
    }
    ids.sort();
    Ok(ids.join("\n"))
}
pub fn efi_list() -> R<String> {
    if !Path::new("/sys/firmware/efi/efivars").is_dir() {
        return Err("Not booted in UEFI mode / 当前不是 UEFI 启动".into());
    }
    run("/usr/bin/efibootmgr", &[])
}
pub fn valid_efi(id: &str, list: &str) -> bool {
    id.len() == 4
        && id.bytes().all(|b| b.is_ascii_hexdigit())
        && list
            .lines()
            .any(|l| l.starts_with(&format!("Boot{}*", id.to_ascii_uppercase())))
}
pub fn efi_set(id: &str) -> R<String> {
    let before = efi_list()?;
    if !valid_efi(id, &before) {
        return Err("Unknown/inactive UEFI entry / 无效或未激活的固件启动项".into());
    }
    // Record prior BootNext for explicit recovery; never modify BootOrder.
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    atomic(
        &format!("{STATE}/efi-{stamp}.txt"),
        before.as_bytes(),
        0o600,
    )?;
    let result: R<String> = (|| {
        run("/usr/bin/efibootmgr", &["--bootnext", id])?;
        let after = efi_list()?;
        if !after
            .lines()
            .any(|l| l == format!("BootNext: {}", id.to_ascii_uppercase()))
        {
            return Err("BootNext verification failed".into());
        }
        Ok(after)
    })();
    match result {
        Ok(s) => Ok(s),
        Err(e) => {
            let old = before.lines().find_map(|l| l.strip_prefix("BootNext: "));
            let rollback = if let Some(old) = old {
                if old.len() == 4 && old.bytes().all(|b| b.is_ascii_hexdigit()) {
                    run("/usr/bin/efibootmgr", &["--bootnext", old])
                } else {
                    Err("Invalid original BootNext".into())
                }
            } else {
                run("/usr/bin/efibootmgr", &["--delete-bootnext"])
            };
            Err(format!("{e}; BootNext rollback / 回滚: {rollback:?}"))
        }
    }
}
pub fn delay(seconds: &str) -> R<u32> {
    if seconds.is_empty() || !seconds.bytes().all(|b| b.is_ascii_digit()) {
        return Err("Invalid seconds / 秒数无效".into());
    }
    let n: u32 = seconds.parse().map_err(|_| "Invalid seconds")?;
    if !(10..=86400).contains(&n) {
        return Err("Delay must be 10..86400 seconds / 延时范围 10..86400 秒".into());
    }
    Ok(n)
}
pub fn reboot(seconds: &str) -> R<String> {
    let n = delay(seconds)?;
    platform::require_systemd()?;
    let systemctl = platform::tool("systemctl")?;
    run(
        "/usr/bin/systemd-run",
        &[
            "--unit=rbm-reboot",
            "--collect",
            &format!("--on-active={n}s"),
            "--timer-property=AccuracySec=1s",
            &systemctl,
            "reboot",
        ],
    )
}
pub fn clear_once() -> R<String> {
    transaction(
        || {
            run("/usr/bin/grub-editenv", &[ENV, "unset", "next_entry"])?;
            let text = run("/usr/bin/grub-editenv", &[ENV, "list"])?;
            if text.lines().any(|l| l.starts_with("next_entry=")) {
                return Err("next_entry was not cleared".into());
            }
            Ok(())
        },
        false,
        false,
    )
}
pub fn efi_clear() -> R<String> {
    efi_list()?;
    run("/usr/bin/efibootmgr", &["--delete-bootnext"])?;
    let after = efi_list()?;
    if after.lines().any(|l| l.starts_with("BootNext:")) {
        return Err("BootNext was not cleared".into());
    }
    Ok(after)
}

pub fn restart_status() -> R<String> {
    platform::require_systemd()?;
    run(
        "systemctl",
        &[
            "show",
            "rbm-reboot.timer",
            "-p",
            "ActiveState",
            "-p",
            "NextElapseUSecMonotonic",
        ],
    )
}
pub fn cancel() -> R<String> {
    platform::require_systemd()?;
    run(
        "/usr/bin/systemctl",
        &["stop", "rbm-reboot.timer", "rbm-reboot.service"],
    )
}
pub fn audit(args: &[String], result: &R<String>) -> R<()> {
    let line = format!(
        "epoch={} uid={} args={:?} result={:?}\n",
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs(),
        std::env::var("PKEXEC_UID").unwrap_or_else(|_| "0".into()),
        args,
        result
    );
    let path = format!("{STATE}/audit.log");
    check_file(&path, true)?;
    // Bound disk use to approximately 1 MiB + one operation.
    if fs::metadata(&path)
        .map(|m| m.len() > 1_048_576)
        .unwrap_or(false)
    {
        let old = format!("{STATE}/audit.previous.log");
        check_file(&old, true)?;
        fs::rename(&path, old).map_err(|e| e.to_string())?;
    }
    let mut f = OpenOptions::new()
        .append(true)
        .create(true)
        .mode(0o600)
        .custom_flags(0x20000)
        .open(path)
        .map_err(|e| e.to_string())?;
    f.write_all(line.as_bytes())
        .and_then(|_| f.sync_all())
        .map_err(|e| e.to_string())
}
pub fn diagnostics() -> String {
    let mut s = format!(
        "Rust Boot Manager {}\nUEFI={}\n",
        env!("CARGO_PKG_VERSION"),
        Path::new("/sys/firmware/efi").exists()
    );
    s.push_str(&platform::report());
    for p in [
        CFG,
        ENV,
        DROP,
        "/etc/default/grub",
        "/usr/bin/pkexec",
        "/usr/bin/efibootmgr",
    ] {
        s.push_str(&format!(
            "{p}: {:?}\n",
            fs::metadata(p).map(|m| (m.len(), m.mode() & 0o777))
        ));
    }
    for (cmd, args) in [
        ("/usr/bin/grub-editenv", vec![ENV, "list"]),
        (
            "/usr/bin/findmnt",
            vec!["-n", "-o", "SOURCE,FSTYPE,OPTIONS", "-T", ENV],
        ),
        (
            "/usr/bin/systemctl",
            vec![
                "show",
                "rbm-reboot.timer",
                "-p",
                "ActiveState",
                "-p",
                "NextElapseUSecMonotonic",
            ],
        ),
    ] {
        s.push_str(&format!("{cmd}: {:?}\n", run(cmd, &args)));
    }
    s
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn windows_names() {
        for s in [
            "Windows Boot Manager (UEFI)",
            "Windows 11",
            "Advanced / Windows 10",
        ] {
            assert!(windows_title(s));
        }
        for s in ["Debian GNU/Linux", "NotWindows", "Windows submenu / Debian"] {
            assert!(!windows_title(s));
        }
    }
    #[test]
    fn delays() {
        for s in ["10", "60", "86400"] {
            assert!(delay(s).is_ok());
        }
        for s in [
            "",
            "0",
            "9",
            "86401",
            "-10",
            "+10",
            "10s",
            "10;reboot",
            "4294967296",
        ] {
            assert!(delay(s).is_err());
        }
    }
    #[test]
    fn snapshot_ids() {
        assert!(valid_snapshot_id("1234567890123456789"));
        for s in [
            "",
            "../1",
            "1/2",
            "-1",
            "1\n",
            "１２３",
            "1234567890123456789012345678901",
        ] {
            assert!(!valid_snapshot_id(s));
        }
    }
    #[test]
    fn unsafe_files_fail_closed() {
        use std::os::unix::fs::symlink;
        let p = std::env::temp_dir().join(format!("rbm-security-{}", std::process::id()));
        fs::create_dir(&p).unwrap();
        let file = p.join("file");
        fs::write(&file, b"x").unwrap();
        fs::set_permissions(&file, fs::Permissions::from_mode(0o666)).unwrap();
        assert!(secure(&file, false).is_err());
        let link = p.join("link");
        symlink(&file, &link).unwrap();
        assert!(secure(&link, false).is_err());
        fs::remove_file(link).unwrap();
        fs::remove_file(file).unwrap();
        fs::remove_dir(p).unwrap();
    }
    #[test]
    fn efi_validation() {
        let s = "Boot000A* Debian\nBoot000B Disabled";
        assert!(valid_efi("000a", s));
        for id in ["000B", "000", "../x", "-n00", "zzzz"] {
            assert!(!valid_efi(id, s));
        }
    }
}
