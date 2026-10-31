#!/usr/bin/python3
"""Install/uninstall to a temporary DESTDIR, never to the host."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='rbm-package-') as stage:
    stage = Path(stage)
    env = dict(os.environ, DESTDIR=str(stage))
    subprocess.run([str(root/'scripts/install.sh')], check=True, env=env)
    binary = stage/'usr/bin/rbm'
    helper = stage/'usr/libexec/rust-boot-manager-helper'
    assert hashlib.sha256(binary.read_bytes()).digest() == hashlib.sha256(helper.read_bytes()).digest()
    assert (stage/'usr/share/rust-boot-manager/style.css').is_file()
    assert (stage/'usr/share/rust-boot-manager/windows.py').is_file()
    assert (stage/'usr/share/rust-boot-manager/privilege.py').is_file()
    assert 'Exec=/usr/bin/rbm windows' in (stage/'usr/share/applications/rbm-windows.desktop').read_text()
    for name in ['rust-boot-manager','rust-boot-manager-windows11']:
        assert (stage/('usr/share/icons/hicolor/scalable/apps/'+name+'.svg')).is_file()
    for name in ['org.rustbootmanager.Manager','org.rustbootmanager.WindowsShortcut']:
        assert 'NoDisplay=true' in (stage/('usr/share/applications/'+name+'.desktop')).read_text()
    assert helper.stat().st_mode & 0o7777 == 0o755
    policy = ET.parse(stage/'usr/share/polkit-1/actions/org.rustbootmanager.policy').getroot()
    action = policy.find('action')
    assert action.find("annotate[@key='org.freedesktop.policykit.exec.path']").text == '/usr/libexec/rust-boot-manager-helper'
    assert action.find('defaults/allow_active').text == 'auth_admin'
    assert action.find('defaults/allow_any').text == 'no'
    assert action.find('defaults/allow_inactive').text == 'no'
    assert action.find("annotate[@key='org.freedesktop.policykit.exec.allow_gui']") is None
    # Uninstall must leave boot state and backups alone.
    fragment = stage/'etc/default/grub.d/99-rbm.cfg'
    fragment.write_text('GRUB_DEFAULT=saved\n')
    state = stage/'var/lib/rust-boot-manager'
    state.mkdir(parents=True)
    (state/'retained-backup').write_text('preserve')
    subprocess.run([str(root/'scripts/uninstall.sh')], check=True, env=env)
    assert not (stage/'usr/share/icons/hicolor/scalable/apps/rust-boot-manager.svg').exists()
    assert not helper.exists() and not binary.exists()
    assert not (stage/'usr/share/applications/rbm-windows.desktop').exists()
    assert not (stage/'usr/share/rust-boot-manager/windows.py').exists()
    assert fragment.read_text() == 'GRUB_DEFAULT=saved\n'
    assert (state/'retained-backup').read_text() == 'preserve'
print('Package staging and policy checks passed; host installation untouched')
