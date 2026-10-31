#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -n "${RBM_TARGET:-}" ]; then
    cargo build --release --offline --target "$RBM_TARGET"
    rbm_binary="${CARGO_TARGET_DIR:-target}/$RBM_TARGET/release/rbm"
    case "$RBM_TARGET" in
        x86_64-*) rbm_arch=amd64 ;;
        aarch64-*) rbm_arch=arm64 ;;
        *) echo 'Unsupported cross-package target; build natively on the target system.' >&2; exit 1 ;;
    esac
else
    cargo build --release --offline
    rbm_binary="${CARGO_TARGET_DIR:-target}/release/rbm"
    rbm_arch="$(dpkg --print-architecture)"
fi
rbm_binary="$(realpath "$rbm_binary")"
rbm_version="$(cargo metadata --offline --no-deps --format-version 1 | python3 -c 'import json,sys;print(json.load(sys.stdin)["packages"][0]["version"])')"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stage="$work/pkg"
rbm_output="${RBM_OUTPUT_DIR:-dist}"
mkdir -p "$stage/DEBIAN" "$work/deps/debian" "$rbm_output"
RBM_BINARY="$rbm_binary" DESTDIR="$stage" scripts/install.sh
# Native binaries use the build system's symbol metadata. Static musl builds
# have no libc dependency, and can run on older Debian/Ubuntu userlands.
rbm_shlibs=
if readelf -d "$rbm_binary" 2>/dev/null | grep -q '(NEEDED)'; then
    cat > "$work/deps/debian/control" <<'CONTROL'
Source: rust-boot-manager
Section: admin
Priority: optional
Maintainer: Rust Boot Manager contributors <maintainer@example.invalid>

Package: rust-boot-manager
Architecture: any
Description: GRUB boot manager
CONTROL
    ln -s "$stage" "$work/deps/debian/rust-boot-manager"
    rbm_shlibs="$(cd "$work/deps" && dpkg-shlibdeps -O -e debian/rust-boot-manager/usr/bin/rbm | sed -n 's/^shlibs:Depends=//p')"
    [ -n "$rbm_shlibs" ] || { echo 'Failed to determine ELF dependencies' >&2; exit 1; }
    rbm_shlibs="$rbm_shlibs, "
fi
cat > "$stage/DEBIAN/control" <<CONTROL
Package: rust-boot-manager
Version: $rbm_version
Section: admin
Priority: optional
Architecture: $rbm_arch
Maintainer: Rust Boot Manager contributors <maintainer@example.invalid>
Depends: ${rbm_shlibs}grub-common, grub2-common, polkitd | policykit-1, pkexec | policykit-1, python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, util-linux, xdg-user-dirs, librsvg2-common
Recommends: efibootmgr, gir1.2-ayatanaappindicator3-0.1 | gir1.2-appindicator3-0.1, python3-nautilus
Suggests: systemd
Description: GRUB boot manager for Debian-family Linux distributions
 Bilingual boot selection, snapshots, window-scoped polkit authorization,
 optional systemd restart scheduling, and a Windows desktop shortcut.
CONTROL
cat > "$stage/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = deconfigure ]; then
 if [ -d /run/systemd/system ] && command -v systemctl >/dev/null; then
  systemctl stop rbm-reboot.timer rbm-reboot.service 2>/dev/null || true
 fi
fi
exit 0
PRERM
chmod 755 "$stage/DEBIAN/prerm"
dpkg-deb --root-owner-group --build "$stage" "$rbm_output/rust-boot-manager_${rbm_version}_${rbm_arch}.deb"
