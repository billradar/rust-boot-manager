//! User-owned desktop launcher; this module is never exposed by the root helper.
use crate::system::{self, R};
use std::{
    env,
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::PathBuf,
    process::Command,
};
const NAME: &str = "rbm-windows.desktop";
const TEMPLATE: &str = include_str!("../packaging/rbm-windows.desktop");
const LEGACY: &str = include_str!("../packaging/legacy/rbm-windows-0.2.0.desktop");
fn desktop_directory() -> R<PathBuf> {
    let output = Command::new("/usr/bin/xdg-user-dir")
        .arg("DESKTOP")
        .output()
        .map_err(|e| format!("xdg-user-dir: {e}"))?;
    if !output.status.success() {
        return Err("Cannot locate your desktop / 无法定位桌面目录".into());
    }
    let path = PathBuf::from(
        String::from_utf8(output.stdout)
            .map_err(|e| e.to_string())?
            .trim(),
    );
    if !path.is_absolute()
        || path == PathBuf::from(env::var_os("HOME").ok_or("Missing HOME")?)
        || !path.is_dir()
    {
        return Err("Desktop is disabled or missing / 桌面目录未启用或不存在".into());
    }
    Ok(path)
}
fn matches_owned_launcher(path: &std::path::Path) -> R<bool> {
    let m = fs::symlink_metadata(path).map_err(|e| e.to_string())?;
    Ok(
        m.is_file() && !m.file_type().is_symlink() && m.uid() == system::uid() && {
            let data = fs::read(path).map_err(|e| e.to_string())?;
            data == TEMPLATE.as_bytes() || data == LEGACY.as_bytes()
        },
    )
}
pub fn manage(action: &str) -> R<String> {
    if system::root() {
        return Err(
            "Run desktop-shortcut as your normal user / 请用普通用户创建桌面快捷方式".into(),
        );
    }
    if !["install", "remove"].contains(&action) {
        return Err("Use desktop-shortcut install|remove".into());
    }
    let path = desktop_directory()?.join(NAME);
    if action == "remove" {
        if path.try_exists().map_err(|e| e.to_string())? {
            if !matches_owned_launcher(&path)? {
                return Err(
                    "Launcher has been changed; refusing to remove / 快捷方式已修改，请手动处理"
                        .into(),
                );
            }
            fs::remove_file(&path).map_err(|e| e.to_string())?;
        }
        return Ok(format!("Removed / 已移除: {}", path.display()));
    }
    match OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o755)
        .open(&path)
    {
        Ok(mut file) => {
            file.write_all(TEMPLATE.as_bytes())
                .and_then(|_| file.sync_all())
                .map_err(|e| e.to_string())?;
            file.set_permissions(fs::Permissions::from_mode(0o755))
                .map_err(|e| e.to_string())?;
        }
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
            if !matches_owned_launcher(&path)? {
                return Err("Desktop filename is occupied; refusing to overwrite / 同名文件已存在，不会覆盖".into());
            }
            let mut file = OpenOptions::new()
                .write(true)
                .truncate(true)
                .custom_flags(0x20000)
                .open(&path)
                .map_err(|e| e.to_string())?;
            file.write_all(TEMPLATE.as_bytes())
                .and_then(|_| file.sync_all())
                .map_err(|e| e.to_string())?;
            fs::set_permissions(&path, fs::Permissions::from_mode(0o755))
                .map_err(|e| e.to_string())?;
        }
        Err(e) => return Err(e.to_string()),
    }
    // Desktop trust metadata is optional and varies with the file manager.
    let trusted = Command::new("/usr/bin/gio")
        .args(["set"])
        .arg(&path)
        .args(["metadata::trusted", "true"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);
    Ok(format!(
        "Created / 已创建: {}\n{}",
        path.display(),
        if trusted {
            "Desktop launcher ready / 桌面快捷方式已就绪"
        } else {
            "If requested, right-click and allow launching / 如有提示，请右键选择允许启动"
        }
    ))
}
