#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
cargo fmt --check
cargo test --offline
cargo build --release --offline
python3 -m py_compile ui/*.py tests/*.py packaging/rbm-nautilus.py
shellcheck scripts/*.sh
desktop-file-validate packaging/rust-boot-manager.desktop packaging/rbm-windows.desktop packaging/org.rustbootmanager.*.desktop
python3 tests/session_client.py
python3 tests/package_smoke.py
python3 tests/desktop_shortcut.py
python3 tests/isolated_system.py
mkdir -p dist
python3 tests/run_gui_smoke.py "${XVFB:-Xvfb}"
