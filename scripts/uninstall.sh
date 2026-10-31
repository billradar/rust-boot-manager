#!/bin/sh
set -eu
if [ "$(id -u)" != 0 ] && [ -z "${DESTDIR:-}" ]; then echo 'Run with sudo, or set DESTDIR' >&2; exit 1; fi
: "${DESTDIR:=}"
if [ -z "$DESTDIR" ] && [ -f /etc/default/grub.d/99-rbm.cfg ]; then
    echo 'Managed GRUB configuration exists. First restore an earlier snapshot using rbm restore ID.' >&2
    echo 'Uninstall refuses to silently change the active boot default. Backups will be preserved.' >&2
    exit 1
fi
if [ -z "$DESTDIR" ]; then
    systemctl stop rbm-reboot.timer rbm-reboot.service 2>/dev/null || true
fi
for p in /usr/share/rust-boot-manager/privilege.py /usr/share/doc/rust-boot-manager/windows-dialog.example.json /usr/share/icons/hicolor/scalable/apps/rust-boot-manager.svg /usr/share/icons/hicolor/scalable/apps/rust-boot-manager-windows11.svg /usr/share/applications/org.rustbootmanager.Manager.desktop /usr/share/applications/org.rustbootmanager.WindowsShortcut.desktop /usr/share/doc/rust-boot-manager/icons.md /usr/bin/rbm /usr/libexec/rust-boot-manager-helper /usr/share/rust-boot-manager/windows.py /usr/share/applications/rbm-windows.desktop /usr/share/rust-boot-manager/gui.py /usr/share/rust-boot-manager/style.css /usr/share/polkit-1/actions/org.rustbootmanager.policy /usr/share/applications/rust-boot-manager.desktop /usr/share/nautilus-python/extensions/rbm.py /usr/share/kio/servicemenus/rbm.desktop /usr/share/kservices5/ServiceMenus/rbm.desktop /usr/share/doc/rust-boot-manager/README.md /usr/share/doc/rust-boot-manager/copyright; do
    rm -f "$DESTDIR$p"
done
if [ -z "$DESTDIR" ] && command -v gtk-update-icon-cache >/dev/null; then gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor; fi
printf '%s\n' 'Uninstalled. Backups and audit logs retained under /var/lib/rust-boot-manager.'
printf '%s\n' 'User desktop launcher: run rbm desktop-shortcut remove before uninstall, or remove rbm-windows.desktop from your desktop.'
