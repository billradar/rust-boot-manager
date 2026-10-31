#!/bin/sh
# Run inside a disposable Debian/Ubuntu container with /work mounted read-only.
set -eu
if [ ! -f /.dockerenv ] && [ ! -f /run/.containerenv ]; then
    echo "Run this test in a disposable container, not on the host." >&2; exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends /work/dist/rust-boot-manager_0.5.0_amd64.deb xvfb xauth dbus-daemon fonts-dejavu-core
mkdir -p /tmp/rbm-runtime/target/release /tmp/rbm-runtime/dist
for name in ui assets tests scripts packaging README.md LICENSE; do
    cp -a "/work/$name" /tmp/rbm-runtime/
done
cp /usr/bin/rbm /tmp/rbm-runtime/target/release/rbm
cd /tmp/rbm-runtime
rbm --version
rbm platform
rbm list --file tests/fixtures/grub.cfg
python3 tests/package_smoke.py
python3 tests/desktop_shortcut.py
python3 tests/session_client.py
python3 tests/run_gui_smoke.py
printf '%s\n' 'DEBIAN_FAMILY_RUNTIME_OK'
