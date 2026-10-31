#!/usr/bin/python3
"""Test XDG desktop placement without touching the actual user's desktop."""
import os
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parent.parent
binary = str(root/'target/release/rbm')
with tempfile.TemporaryDirectory(prefix='rbm-desktop-test-') as home:
    home = Path(home)
    (home/'Desktop').mkdir(); (home/'.config').mkdir()
    config=home/'.config/user-dirs.dirs'
    config.write_text('XDG_DESKTOP_DIR="$HOME/Desktop"\n')
    env=dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home/'.config'), GIO_USE_VFS='local')
    env.pop('DBUS_SESSION_BUS_ADDRESS',None)
    prefix=[]
    if os.geteuid()==0:
        # CI may run as root. Desktop creation must still run as an ordinary user.
        for path in [home]+list(home.rglob('*')):
            os.chown(path,65534,65534)
        prefix=['setpriv','--reuid=65534','--regid=65534','--clear-groups']
    def run(action,ok=True):
        p=subprocess.run(prefix+[binary,'desktop-shortcut',action],cwd='/tmp',env=env,text=True,capture_output=True)
        assert (p.returncode==0)==ok, (p.stdout,p.stderr)
    launcher=home/'Desktop/rbm-windows.desktop'
    run('install')
    original=launcher.read_text()
    assert 'Exec=/usr/bin/rbm windows\n' in original
    assert launcher.stat().st_mode&0o777==0o755
    run('install')
    assert launcher.read_text()==original
    launcher.write_text((root/'packaging/legacy/rbm-windows-0.2.0.desktop').read_text())
    run('install')
    assert launcher.read_text()==original and 'Icon=rust-boot-manager-windows11' in original
    launcher.write_text('Unrelated user file')
    run('install',False); run('remove',False)
    assert launcher.read_text()=='Unrelated user file'
    launcher.unlink()
    target=home/'Desktop/keep-me'; target.write_text('Keep')
    launcher.symlink_to(target)
    run('install',False)
    assert target.read_text()=='Keep'
    launcher.unlink()
    run('install'); run('remove')
    assert not launcher.exists()
    localized=home/'桌面'; localized.mkdir()
    if os.geteuid()==0:
        os.chown(localized,65534,65534)
    config.write_text('XDG_DESKTOP_DIR="$HOME/桌面"\n')
    run('install')
    assert (localized/'rbm-windows.desktop').exists()
    run('remove')
    config.write_text('XDG_DESKTOP_DIR="$HOME"\n')
    run('install',False)
print('User desktop shortcut placement, executable mode, idempotence and overwrite protection passed')
