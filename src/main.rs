mod desktop;
mod grub;
mod platform;
mod session;
mod system;
use std::{
    env, fs,
    process::{Command, ExitCode},
};
use system::R;
const HELPER: &str = "/usr/libexec/rust-boot-manager-helper";
fn json(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => o.push_str("\\r"),
            '\t' => o.push_str("\\t"),
            c if c < ' ' => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}
fn entries(path: Option<&str>) -> R<String> {
    let es = if let Some(p) = path {
        grub::parse(&fs::read_to_string(p).map_err(|e| e.to_string())?)?
    } else {
        system::read_entries()?
    };
    Ok(format!(
        "[{}]",
        es.iter()
            .map(|e| format!(
                "{{\"selector\":{},\"title\":{}}}",
                json(&e.selector),
                json(&e.title)
            ))
            .collect::<Vec<_>>()
            .join(",")
    ))
}
fn help() -> String {
    "Rust Boot Manager 0.5.0 — Debian-family Linux\n\
Usage / 用法:\n\
  rbm list [--file PATH]      JSON boot entries / 启动项\n\
  rbm set once|permanent SELECTOR   Set target (no reboot) / 设置启动目标（不重启）\n\
  rbm clear-once              Clear next_entry / 取消 GRUB 一次性目标\n\
  rbm backup | backups | restore ID   Configuration snapshots / 配置快照\n\
  rbm efi-list | efi-next XXXX | efi-clear   UEFI BootNext\n\
  rbm reboot SECONDS | cancel   Schedule/cancel reboot / 延迟重启与取消\n\
  rbm status | diagnose | logs | platform\n\
  rbm gui [--tray] [--lang en|zh]   GTK interface / 图形界面\n\
  rbm windows [--lang en|zh]   Confirm one-time Windows restart / 确认后临时重启到 Windows\n\
  rbm desktop-shortcut install|remove   Desktop launcher / 桌面快捷方式\n\
  rbm plan once|permanent SELECTOR  Validate selection without writing / 只读预览\n\
Writes request polkit authorization; install first. / 写操作需要 polkit 授权，请先安装。\n\
Cancel stops only the reboot timer; clear-once/efi-clear clear boot targets.\n\
取消重启只停止计时器；清除启动目标请使用 clear-once / efi-clear。"
        .into()
}
fn valid_privileged_args(a: &[String]) -> bool {
    if a.iter()
        .any(|s| s.len() > 4096 || s.chars().any(|c| c == '\0'))
    {
        return false;
    }
    let a: Vec<&str> = a.iter().map(String::as_str).collect();
    match a.as_slice() {
        ["list" | "backup" | "backups" | "clear-once" | "efi-list" | "efi-clear" | "cancel"
        | "status" | "diagnose" | "logs" | "platform"] => true,
        ["windows-reboot", "once" | "permanent"] => true,
        ["set", "once" | "permanent", id]
        | ["windows-reboot", "once" | "permanent", id]
        | ["windows-reboot", id] => {
            !id.is_empty() && !id.starts_with('-') && !id.contains(['\n', '\r'])
        }
        ["restore", id] => {
            !id.is_empty() && id.len() <= 30 && id.bytes().all(|b| b.is_ascii_digit())
        }
        ["efi-next", id] => id.len() == 4 && id.bytes().all(|b| b.is_ascii_hexdigit()),
        ["reboot", delay] => system::delay(delay).is_ok(),
        _ => false,
    }
}
fn valid_gui_args(a: &[&str]) -> bool {
    let mut i = 0;
    let mut tray = false;
    let mut lang = false;
    while i < a.len() {
        match a[i] {
            "--tray" if !tray => tray = true,
            "--lang" if !lang && a.get(i + 1).is_some_and(|s| ["en", "zh"].contains(s)) => {
                lang = true;
                i += 1;
            }
            _ => return false,
        }
        i += 1;
    }
    true
}
fn privileged(a: &[String]) -> R<String> {
    if !system::root() {
        return Err("Root helper requires polkit / 特权入口需要 polkit 授权".into());
    }
    if !valid_privileged_args(a) {
        return Err("Invalid arguments".into());
    }
    let _lock = system::lock()?;
    system::audit(a, &Ok("BEGIN".into()))?;
    let av: Vec<&str> = a.iter().map(String::as_str).collect();
    let r = match av.as_slice() {
        ["list"] => entries(None),
        ["set", m, id] => system::set(m, id),
        ["windows-reboot", mode @ ("once" | "permanent")] => system::windows_reboot(mode, None),
        ["windows-reboot", mode @ ("once" | "permanent"), id] => {
            system::windows_reboot(mode, Some(id))
        }
        ["windows-reboot", id] => system::windows_reboot("once", Some(id)),
        ["backup"] => system::backup(),
        ["backups"] => system::backups(),
        ["restore", id] => system::restore(id),
        ["efi-list"] => system::efi_list(),
        ["efi-next", id] => system::efi_set(id),
        ["efi-clear"] => system::efi_clear(),
        ["clear-once"] => system::clear_once(),
        ["reboot", seconds] => system::reboot(seconds),
        ["cancel"] => system::cancel(),
        ["status"] => system::restart_status(),
        ["platform"] => Ok(platform::report()),
        ["diagnose"] => Ok(system::diagnostics()),
        ["logs"] => {
            fs::read_to_string("/var/lib/rust-boot-manager/audit.log").map_err(|e| e.to_string())
        }
        _ => Err("Unknown command/arguments / 未知命令或参数".into()),
    };
    // Don't recursively include the audit log in itself.
    if av.first() == Some(&"logs") {
        system::audit(
            a,
            &r.as_ref()
                .map(|_| "log read".to_owned())
                .map_err(Clone::clone),
        )?;
    } else {
        system::audit(a, &r)?;
    }
    r
}
fn execute(a: &[String]) -> R<String> {
    let av: Vec<&str> = a.iter().map(String::as_str).collect();
    match av.as_slice() {
        [] | ["help"] | ["--help"] | ["-h"] => Ok(help()),
        ["--version"] => Ok(env!("CARGO_PKG_VERSION").into()),
        ["platform"] => Ok(platform::report()),
        ["list", "--file", p] => entries(Some(p)),
        ["list"] if fs::read_to_string(system::CFG).is_ok() => entries(None),
        ["plan", m, id] if ["once", "permanent"].contains(m) => {
            if !system::read_entries()?.iter().any(|e| e.selector == *id) {
                return Err("Unknown entry".into());
            }
            Ok(format!("mode={m}; selector={id:?}; no writes / 未写入; authorization and storage checks occur on apply"))
        }
        ["desktop-shortcut", action] => desktop::manage(action),
        ["windows", rest @ ..] => {
            if system::root() {
                return Err(
                    "Run the Windows confirmation as your normal user / 请以普通用户打开确认窗口"
                        .into(),
                );
            }
            if !(rest.is_empty() || matches!(rest, ["--lang", "en" | "zh"])) {
                return Err("Use rbm windows [--lang en|zh]".into());
            }
            let status = Command::new("/usr/bin/python3")
                .arg("-I")
                .arg("/usr/share/rust-boot-manager/windows.py")
                .args(rest)
                .status()
                .map_err(|e| e.to_string())?;
            if status.success() {
                Ok(String::new())
            } else {
                Err(format!("Windows shortcut: {status}"))
            }
        }
        ["gui", rest @ ..] => {
            if system::root() {
                return Err("Run GUI as your normal user / 请以普通用户运行界面".into());
            }
            if !valid_gui_args(rest) {
                return Err("Invalid GUI argument / GUI 参数无效".into());
            }
            let status = Command::new("/usr/bin/python3")
                .arg("-I")
                .arg("/usr/share/rust-boot-manager/gui.py")
                .args(rest)
                .status()
                .map_err(|e| e.to_string())?;
            if status.success() {
                Ok(String::new())
            } else {
                Err(format!("GUI exited: {status}"))
            }
        }
        _ => {
            if !valid_privileged_args(a) {
                return Err("Unknown command/arguments / 未知命令或参数; rbm --help".into());
            }
            // The authorized executable is fixed; never elevate the current checkout or a PATH lookup.
            if system::root() {
                return privileged(a);
            }
            let status = Command::new("/usr/bin/pkexec")
                .arg(HELPER)
                .args(a)
                .status()
                .map_err(|e| format!("Install first / 请先安装: {e}"))?;
            if status.success() {
                Ok(String::new())
            } else {
                Err(format!(
                    "Authorization or operation failed / 授权或操作失败: {status}"
                ))
            }
        }
    }
}
fn main() -> ExitCode {
    let a: Vec<String> = env::args().skip(1).collect();
    // Helper invocation bypasses all unprivileged modes including arbitrary file reads and GUI.
    let helper = env::current_exe()
        .ok()
        .map(|p| p == std::path::Path::new(HELPER))
        .unwrap_or(false);
    match if helper {
        if a.as_slice() == ["--session"] {
            session::serve(privileged)
        } else {
            privileged(&a)
        }
    } else {
        execute(&a)
    } {
        Ok(s) => {
            if !s.is_empty() {
                println!("{s}");
            }
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("Error / 错误: {e}");
            ExitCode::FAILURE
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn reject_invalid_commands_before_authorization() {
        for a in [
            vec!["gui"],
            vec!["restore", "../1"],
            vec!["reboot", "9"],
            vec!["efi-next", "000Z"],
            vec!["set", "once", "--boot-directory=x"],
            vec!["list", "--file", "/etc/shadow"],
            vec!["logs", "extra"],
        ] {
            assert!(!valid_privileged_args(
                &a.iter().map(|s| s.to_string()).collect::<Vec<_>>()
            ));
        }
        for a in [
            vec!["backup"],
            vec!["set", "once", "adv>linux"],
            vec!["reboot", "60"],
        ] {
            assert!(valid_privileged_args(
                &a.iter().map(|s| s.to_string()).collect::<Vec<_>>()
            ));
        }
    }
    #[test]
    fn gui_arguments() {
        assert!(valid_gui_args(&["--lang", "zh", "--tray"]));
        for a in [
            vec!["en"],
            vec!["--lang"],
            vec!["--lang", "de"],
            vec!["--tray", "--tray"],
        ] {
            assert!(!valid_gui_args(&a));
        }
    }
    #[test]
    fn json_escapes() {
        assert_eq!(json("a\n\"\\\t"), "\"a\\n\\\"\\\\\\t\"");
    }
}
