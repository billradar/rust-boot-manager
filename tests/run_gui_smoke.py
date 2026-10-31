#!/usr/bin/python3
"""Start a private X server; never connect to the user's desktop."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
server = subprocess.Popen([sys.argv[1] if len(sys.argv)>1 else 'Xvfb', '-displayfd', '1', '-screen', '0', '1280x900x24', '-nolisten', 'tcp'], stdout=subprocess.PIPE, text=True)
runtime = tempfile.TemporaryDirectory(prefix="rbm-gui-runtime-")
try:
    display = server.stdout.readline().strip()
    if not display.isdigit():
        raise RuntimeError('Xvfb failed to start')
    env = dict(os.environ, DISPLAY=':' + display, GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1', GDK_BACKEND='x11', GTK_USE_PORTAL='0', GIO_USE_VFS='local', XDG_CURRENT_DESKTOP='', XDG_RUNTIME_DIR=runtime.name)
    env.pop('DBUS_SESSION_BUS_ADDRESS', None)
    env.pop('WAYLAND_DISPLAY', None)
    for lang in ('en', 'zh'):
        for test in ['gui_smoke.py', 'windows_gui_smoke.py']:
            subprocess.run(['dbus-run-session', '--config-file=' + str(root/'tests/session-bus.conf'), '--', '/usr/bin/python3', str(root / 'tests' / test), lang], cwd=root, env=env, check=True, timeout=20)
finally:
    server.terminate()
    server.wait(timeout=5)
    runtime.cleanup()
