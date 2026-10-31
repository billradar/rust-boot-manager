#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$(id -u)" != 0 ] && [ -z "${DESTDIR:-}" ]; then
    echo 'Use sudo scripts/install.sh, or DESTDIR=/tmp/stage scripts/install.sh' >&2; exit 1
fi
: "${DESTDIR:=}"
: "${RBM_BINARY:=target/release/rbm}"
[ -f "$RBM_BINARY" ] || { echo 'Run cargo build --release --offline first' >&2; exit 1; }
install -d -m755 "$DESTDIR/etc/default/grub.d"
install -Dm755 "$RBM_BINARY" "$DESTDIR/usr/bin/rbm"
install -Dm755 "$RBM_BINARY" "$DESTDIR/usr/libexec/rust-boot-manager-helper"
for icon in rust-boot-manager rust-boot-manager-windows11; do
    install -Dm644 "assets/icons/$icon.svg" "$DESTDIR/usr/share/icons/hicolor/scalable/apps/$icon.svg"
done
for app in org.rustbootmanager.Manager org.rustbootmanager.WindowsShortcut; do
    install -Dm644 "packaging/$app.desktop" "$DESTDIR/usr/share/applications/$app.desktop"
done
install -Dm644 packaging/windows-dialog.example.json "$DESTDIR/usr/share/doc/rust-boot-manager/windows-dialog.example.json"
install -Dm644 assets/NOTICE.md "$DESTDIR/usr/share/doc/rust-boot-manager/icons.md"
install -Dm644 ui/style.css "$DESTDIR/usr/share/rust-boot-manager/style.css"
install -Dm644 ui/privilege.py "$DESTDIR/usr/share/rust-boot-manager/privilege.py"
install -Dm644 ui/windows.py "$DESTDIR/usr/share/rust-boot-manager/windows.py"
install -Dm644 packaging/rbm-windows.desktop "$DESTDIR/usr/share/applications/rbm-windows.desktop"
install -Dm644 ui/gui.py "$DESTDIR/usr/share/rust-boot-manager/gui.py"
install -Dm644 packaging/org.rustbootmanager.policy "$DESTDIR/usr/share/polkit-1/actions/org.rustbootmanager.policy"
install -Dm644 packaging/rust-boot-manager.desktop "$DESTDIR/usr/share/applications/rust-boot-manager.desktop"
install -Dm644 packaging/rbm-nautilus.py "$DESTDIR/usr/share/nautilus-python/extensions/rbm.py"
install -Dm644 packaging/rbm-dolphin.desktop "$DESTDIR/usr/share/kio/servicemenus/rbm.desktop"
install -Dm644 packaging/rbm-dolphin.desktop "$DESTDIR/usr/share/kservices5/ServiceMenus/rbm.desktop"
install -Dm644 README.md "$DESTDIR/usr/share/doc/rust-boot-manager/README.md"
install -Dm644 LICENSE "$DESTDIR/usr/share/doc/rust-boot-manager/copyright"
if [ -z "$DESTDIR" ]; then
    chown root:root /usr/bin/rbm /usr/libexec/rust-boot-manager-helper /usr/share/rust-boot-manager/gui.py /usr/share/rust-boot-manager/style.css /usr/share/polkit-1/actions/org.rustbootmanager.policy
    if command -v gtk-update-icon-cache >/dev/null; then gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor; fi
    if command -v update-desktop-database >/dev/null; then update-desktop-database /usr/share/applications; fi
fi
printf '%s\n' 'Installed. No boot settings changed. / 安装完成，未更改启动配置。'
