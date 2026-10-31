//! Distribution information and capability discovery; never evaluate os-release as shell.
use crate::system::R;
use std::{collections::BTreeMap, fs, os::unix::fs::PermissionsExt, path::Path};
pub const TOOLS: &[&str] = &[
    "grub-editenv",
    "grub-reboot",
    "grub-set-default",
    "update-grub",
    "grub-probe",
    "findmnt",
    "efibootmgr",
    "systemctl",
    "systemd-run",
    "pkexec",
];
const DIRECTORIES: [&str; 4] = ["/usr/sbin", "/usr/bin", "/sbin", "/bin"];
fn select_tool(name: &str, mut executable: impl FnMut(&str) -> bool) -> R<String> {
    let name = Path::new(name)
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or("Invalid tool name")?;
    if !TOOLS.contains(&name) {
        return Err("Unknown system tool".into());
    }
    for directory in DIRECTORIES {
        let path = format!("{directory}/{name}");
        if executable(&path) {
            return Ok(path);
        }
    }
    Err(format!("Required tool not found / 缺少系统工具: {name}"))
}
pub fn tool(name: &str) -> R<String> {
    select_tool(name, |path| {
        fs::metadata(path)
            .map(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
    })
}
pub fn parse_release(text: &str) -> BTreeMap<String, String> {
    let mut values = BTreeMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.starts_with('#') {
            continue;
        }
        let Some((key, raw)) = line.split_once('=') else {
            continue;
        };
        if !["NAME", "PRETTY_NAME", "ID", "ID_LIKE", "VERSION_ID"].contains(&key) {
            continue;
        }
        let raw = raw.trim();
        let value = if raw.starts_with(['\'', '"']) {
            let quote = raw.chars().next().unwrap();
            if raw.len() < 2 || !raw.ends_with(quote) {
                continue;
            }
            raw[1..raw.len() - 1].to_owned()
        } else {
            raw.to_owned()
        };
        let mut unescaped = String::new();
        let mut chars = value.chars();
        while let Some(c) = chars.next() {
            if c == '\\' {
                if let Some(next) = chars.next() {
                    unescaped.push(next);
                }
            } else {
                unescaped.push(c);
            }
        }
        values.insert(key.to_owned(), unescaped);
    }
    values
}
pub fn os_release() -> BTreeMap<String, String> {
    for path in ["/etc/os-release", "/usr/lib/os-release"] {
        if let Ok(text) = fs::read_to_string(path) {
            return parse_release(&text);
        }
    }
    BTreeMap::new()
}
pub fn debian_family(values: &BTreeMap<String, String>) -> bool {
    values
        .get("ID")
        .into_iter()
        .chain(values.get("ID_LIKE"))
        .flat_map(|v| v.split_whitespace())
        .any(|id| ["debian", "ubuntu"].contains(&id))
}
pub fn systemd() -> bool {
    Path::new("/run/systemd/system").is_dir()
}
pub fn require_systemd() -> R<()> {
    if !systemd() {
        return Err("Scheduled restart requires a running systemd system. GRUB selection and backups remain available / 计划重启需要运行中的 systemd；GRUB 选择和备份仍可使用".into());
    }
    tool("systemctl")?;
    tool("systemd-run")?;
    Ok(())
}
pub fn report() -> String {
    let os = os_release();
    let mut text = format!(
        "OS={}\nID={}\nID_LIKE={}\nVERSION_ID={}\nDebian-family={}\nSystemd={}\nUEFI={}\n",
        os.get("PRETTY_NAME")
            .or_else(|| os.get("NAME"))
            .map(String::as_str)
            .unwrap_or("Linux"),
        os.get("ID").map(String::as_str).unwrap_or("unknown"),
        os.get("ID_LIKE").map(String::as_str).unwrap_or(""),
        os.get("VERSION_ID").map(String::as_str).unwrap_or(""),
        debian_family(&os),
        systemd(),
        Path::new("/sys/firmware/efi/efivars").is_dir()
    );
    for name in TOOLS {
        text.push_str(&format!(
            "{name}: {}\n",
            tool(name).unwrap_or_else(|_| "missing / 未安装".into())
        ));
    }
    text
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn derived_distributions() {
        for text in [
            "ID=debian",
            "ID=ubuntu\nID_LIKE=debian",
            "ID=linuxmint\nID_LIKE=\"ubuntu debian\"",
            "ID=kali\nID_LIKE=debian",
            "ID=devuan\nID_LIKE=debian",
            "ID=pop\nID_LIKE=ubuntu",
        ] {
            assert!(debian_family(&parse_release(text)));
        }
        assert!(!debian_family(&parse_release("ID=arch")));
    }
    #[test]
    fn values_are_never_executed() {
        let os=parse_release("PRETTY_NAME=\"Linux Mint 22\"\nID=linuxmint\nIGNORED=$(touch /tmp/no)\nNAME='$(touch /tmp/no)'\nVERSION_ID=\"22\"");
        assert_eq!(os["PRETTY_NAME"], "Linux Mint 22");
        assert_eq!(os["NAME"], "$(touch /tmp/no)");
        assert!(!os.contains_key("IGNORED"));
    }
    #[test]
    fn tools_use_only_fixed_directories() {
        assert_eq!(
            select_tool("/usr/bin/efibootmgr", |p| p == "/usr/sbin/efibootmgr").unwrap(),
            "/usr/sbin/efibootmgr"
        );
        assert_eq!(
            select_tool("grub-reboot", |p| p == "/sbin/grub-reboot").unwrap(),
            "/sbin/grub-reboot"
        );
        assert!(select_tool("sh", |_| true).is_err());
        assert!(select_tool("systemctl", |_| false).is_err());
    }
}
