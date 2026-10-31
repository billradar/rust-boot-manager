#!/usr/bin/python3
"""Integration tests: user namespaces + private mounts. Never uses sudo or host /boot.
Requires bwrap, grub-common, grub2-common, python3 and enabled user namespaces.
Only grub-editenv, grub-reboot and grub-set-default are the real OS tools.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
helper = '/usr/libexec/rust-boot-manager-helper'
binary=Path(os.environ.get('RBM_TEST_BINARY',str(root/'target/release/rbm'))).resolve()
checks = 0

def check(condition, message):
    global checks
    assert condition, message
    checks += 1

with tempfile.TemporaryDirectory(prefix='rbm-integration-') as work:
    work = Path(work)
    for p in ['boot/grub', 'etc/default/grub.d', 'state', 'control', 'var/lib', 'efi-vars']:
        (work / p).mkdir(parents=True, exist_ok=True)
    cfg = work / 'boot/grub/grub.cfg'
    cfg.write_text((root / 'tests/fixtures/grub.cfg').read_text().replace('set default="${saved_entry}"', 'set default="0"', 1))
    defaults = work / 'etc/default/grub'
    defaults.write_text('GRUB_DEFAULT=0\n')
    env = work / 'boot/grub/grubenv'
    subprocess.run(['/usr/bin/grub-editenv', str(env), 'create'], check=True)
    defaults.chmod(0o600)
    original_env = env.read_bytes()
    original_defaults = defaults.read_bytes()
    control = work / 'control'
    (control / 'fstype').write_text('ext4')
    (control / 'abstraction').write_text('')
    (control / 'efi.json').write_text(json.dumps({'next':'0001'}))
    mock = work / 'mock'
    shutil.copyfile(root / 'tests/mock_system.py', mock)
    mock.chmod(0o755)
    for directory in work.rglob('*'):
        if directory.is_dir():
            directory.chmod(0o755)
        elif directory not in (mock, defaults):
            directory.chmod(0o644)
    (work / 'state').chmod(0o700)
    base = ['bwrap', '--unshare-all', '--uid', '0', '--gid', '0', '--die-with-parent',
            '--ro-bind', '/usr/lib', '/usr/lib', '--ro-bind', '/usr/lib64', '/usr/lib64',
            '--ro-bind', '/usr/share', '/usr/share', '--dir', '/usr/bin', '--dir', '/usr/sbin', '--dir', '/usr/libexec', '--symlink', 'usr/lib', '/lib',
            '--symlink', 'usr/lib64', '/lib64', '--symlink', 'usr/bin', '/bin',
            '--symlink', 'usr/sbin', '/sbin', '--proc', '/proc', '--dev', '/dev',
            '--bind', str(work / 'boot'), '/boot', '--bind', str(work / 'etc'), '/etc',
            '--dir', '/var/lib', '--dir', '/run/systemd/system', '--bind', str(work / 'state'), '/var/lib/rust-boot-manager',
            '--bind', str(control), '/control', '--bind', str(work/'efi-vars'), '/sys/firmware/efi/efivars',
            '--ro-bind', str(binary), helper]
    for program in ['/usr/bin/python3','/usr/bin/sh','/usr/bin/basename','/usr/bin/sed','/usr/bin/grub-editenv','/usr/sbin/grub-reboot','/usr/sbin/grub-set-default']:
        base += ['--ro-bind', program, program]
    for name in ['update-grub', 'grub-probe', 'findmnt', 'efibootmgr', 'systemd-run', 'systemctl']:
        folder = 'sbin' if name in ['update-grub', 'grub-probe'] else 'bin'
        base += ['--ro-bind', str(mock), '/usr/' + folder + '/' + name]

    def run(*args, ok=True):
        r = subprocess.run(base + [helper] + list(args), text=True, capture_output=True, timeout=20)
        check((r.returncode == 0) == ok, f'{args}: {r.returncode}\n{r.stdout}\n{r.stderr}')
        return r.stdout if ok else r.stderr

    def envvars():
        return subprocess.check_output(['/usr/bin/grub-editenv', str(env), 'list'], text=True)

    entries = json.loads(run('list'))
    check(len(entries) == 3, 'entry count')
    first, recovery = entries[0]['selector'], entries[1]['selector']
    snapshot = run('backup').strip()
    check(snapshot.isdigit(), 'snapshot id')
    check(snapshot in run('backups'), 'snapshot listed')
    inode = env.stat().st_ino
    run('set', 'once', recovery)
    check('next_entry=' + recovery in envvars(), 'one-shot env write')
    run('clear-once')
    check('next_entry=' not in envvars(), 'one-shot cleared')
    run('set', 'permanent', first)
    check('saved_entry=' + first in envvars(), 'saved env write')
    drop = work / 'etc/default/grub.d/99-rbm.cfg'
    check('GRUB_DEFAULT=saved' in drop.read_text(), 'managed configuration')
    run('restore', snapshot)
    check(not drop.exists() and env.read_bytes() == original_env, 'restore removes fragment and restores environment')
    check(env.stat().st_ino == inode, 'restore preserves grubenv inode')
    check(defaults.read_bytes() == original_defaults, 'restore defaults')
    check(defaults.stat().st_mode & 0o777 == 0o600, 'restore preserves private defaults permissions')
    (control / 'update-fails-once').touch()
    message = run('set', 'permanent', first, ok=False)
    check('rollback' in message and 'Ok(())' in message, 'failure rollback reported')
    check(not drop.exists() and env.read_bytes() == original_env, 'failure rollback contents')
    for args in [('restore','../../etc/passwd'), ('set','once','--boot-directory=/tmp'), ('efi-next','000B'), ('efi-next','00;A'), ('reboot','9'), ('reboot','86401'), ('gui',), ('list','--file','/etc/default/grub')]:
        run(*args, ok=False)
    check(env.read_bytes() == original_env, 'rejected input does not mutate env')
    for filesystem, abstraction in [('btrfs',''), ('ext4','lvm')]:
        (control/'fstype').write_text(filesystem); (control/'abstraction').write_text(abstraction)
        run('set','once',first,ok=False)
    (control/'fstype').write_text('ext4'); (control/'abstraction').write_text('')
    run('efi-next', '000a')
    check(json.loads((control/'efi.json').read_text())['next']=='000A', 'BootNext set')
    (control/'efi-fails-once').touch()
    run('efi-next', '0001', ok=False)
    check(json.loads((control/'efi.json').read_text())['next']=='000A', 'partial BootNext failure rolls back')
    run('efi-clear')
    check('next' not in json.loads((control/'efi.json').read_text()), 'BootNext cleared')
    run('reboot','120')
    timer=json.loads((control/'timer').read_text())
    check('--on-active=120s' in timer and timer[-2:]==['/usr/bin/systemctl','reboot'], 'scheduled fixed reboot command')
    run('reboot','60',ok=False)
    check(json.loads((control/'timer').read_text())==timer, 'duplicate timer preserved')
    run('cancel')
    check(not (control/'timer').exists(), 'cancel removes timer')
    check('BEGIN' in run('logs'), 'audit includes intent')
    # Windows shortcut must preserve permanent defaults and recover failed scheduling.
    windows = entries[2]['selector']
    before_windows = env.read_bytes()
    run('windows-reboot',first,ok=False)
    check(env.read_bytes()==before_windows and not (control/'timer').exists(), 'non-Windows shortcut refused')
    (control/'schedule-fails-once').touch()
    run('windows-reboot',windows,ok=False)
    check(env.read_bytes()==before_windows and not (control/'timer').exists(), 'Windows scheduling failure rolls back grubenv')
    run('windows-reboot',windows)
    check('next_entry='+windows in envvars(), 'Windows shortcut sets one-time target')
    check('--on-active=10s' in json.loads((control/'timer').read_text()), 'Windows shortcut schedules 10 second grace period')
    check(not drop.exists() and defaults.read_bytes()==original_defaults and 'saved_entry=' not in envvars(), 'Windows shortcut preserves permanent configuration')
    selected = env.read_bytes()
    run('windows-reboot',windows,ok=False)
    check(env.read_bytes()==selected, 'duplicate shortcut preserves pending boot target')
    run('cancel'); run('clear-once')
    bootnext = work/'efi-vars/BootNext-test'
    bootnext.write_bytes(b'existing firmware target')
    run('windows-reboot',windows,ok=False)
    check(not (control/'timer').exists() and 'next_entry=' not in envvars(), 'existing BootNext blocks GRUB shortcut')
    bootnext.unlink()
    subprocess.run(['/usr/bin/grub-editenv',str(env),'set','saved_entry=debian','prev_saved_entry=legacy'],check=True)
    legacy = env.read_bytes()
    run('windows-reboot',windows,ok=False)
    check(env.read_bytes()==legacy and not (control/'timer').exists(), 'legacy grub-reboot permanent-default mutation is rolled back')
    env.write_bytes(before_windows)

    # Minimal shortcut auto-detects Windows, with an explicit permanent checkbox mode.
    run('windows-reboot','once')
    check('next_entry='+windows in envvars(), 'automatic Windows target for minimal confirmation')
    run('cancel');run('restore',snapshot)
    (control/'schedule-fails-once').touch()
    run('windows-reboot','permanent',ok=False)
    check(not drop.exists() and env.read_bytes()==original_env, 'permanent checkbox scheduling failure rolls back defaults')
    run('windows-reboot','permanent')
    check('saved_entry='+windows in envvars() and 'next_entry=' not in envvars(), 'checked mode selects permanent Windows')
    check(drop.exists() and '--on-active=10s' in json.loads((control/'timer').read_text()), 'checked mode updates GRUB default and schedules reboot')
    run('cancel');run('restore',snapshot)
    original_cfg=cfg.read_text()
    cfg.write_text(original_cfg+"\nmenuentry 'Windows 11' --id second-windows {}\n")
    run('windows-reboot','once',ok=False)
    check(not (control/'timer').exists() and env.read_bytes()==original_env, 'ambiguous automatic target refused')
    run('windows-reboot','once',windows)
    check('next_entry='+windows in envvars(), 'configured explicit Windows target resolves ambiguity')
    run('cancel');cfg.write_text(original_cfg);run('restore',snapshot)
    # Unsafe root-controlled state is rejected, even after a valid polkit invocation.
    saved = env.read_bytes()
    env.chmod(0o666)
    run('set','once',first,ok=False)
    env.chmod(0o644)
    check(env.read_bytes()==saved, 'unsafe mode does not mutate env')
    real_env=env.with_name('original-grubenv'); env.rename(real_env); env.symlink_to(real_env.name)
    run('backup',ok=False)
    env.unlink(); real_env.rename(env)
    # Incomplete snapshots and corrupt environment blocks fail closed.
    marker = work/'state'/snapshot/'complete'
    marker.write_text('corrupt')
    run('restore',snapshot,ok=False)
    marker.write_text('rbm-snapshot-v1\n')
    env.write_bytes(b'x'*1024)
    run('backup',ok=False)
    env.write_bytes(saved)
    # Independent helper invocations serialize through an actual kernel flock.
    import fcntl
    with (work/'state/lock').open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        check('Another operation' in run('backup',ok=False), 'exclusive helper lock')
    # Non-systemd derivatives keep GRUB operations, but scheduling fails before writes.
    without_systemd=list(base)
    marker=without_systemd.index('/run/systemd/system');del without_systemd[marker-1:marker+1]
    before_init_test=env.read_bytes()
    unsupported=subprocess.run(without_systemd+[helper,'windows-reboot','once'],capture_output=True,text=True,timeout=20)
    check(unsupported.returncode!=0 and 'systemd' in unsupported.stderr, 'non-systemd restart has a clear capability error')
    check(env.read_bytes()==before_init_test and not (control/'timer').exists(), 'missing init capability never changes boot settings')
    ordinary=subprocess.run(without_systemd+[helper,'list'],capture_output=True,text=True,timeout=20)
    check(ordinary.returncode==0, 'GRUB list remains available without systemd')
    selection=subprocess.run(without_systemd+[helper,'set','once',first],capture_output=True,text=True,timeout=20)
    check(selection.returncode==0 and 'next_entry='+first in envvars(), 'GRUB selection remains available without systemd')
    recovery_no_init=subprocess.run(without_systemd+[helper,'restore',snapshot],capture_output=True,text=True,timeout=20)
    check(recovery_no_init.returncode==0 and env.read_bytes()==saved, 'GRUB restore remains available without systemd')
    relocated=[value.replace('/usr/bin/efibootmgr','/usr/sbin/efibootmgr') for value in base]
    relocated_result=subprocess.run(relocated+[helper,'efi-list'],capture_output=True,text=True,timeout=20)
    check(relocated_result.returncode==0 and 'BootOrder:' in relocated_result.stdout, 'system utility path variation is detected')

    # Real persistent helper: several commands over one authenticated connection.
    import struct
    def frame(args):
        encoded=[arg.encode() for arg in args]
        return struct.pack('>I',len(encoded))+b''.join(struct.pack('>I',len(arg))+arg for arg in encoded)
    wrapper="import subprocess,sys;p=subprocess.run(["+repr(helper)+",'--session'],input=sys.stdin.buffer.read(),capture_output=True);sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr);sys.exit(p.returncode)"
    raw=frame(['list'])+frame(['list','--file','/etc/passwd'])+frame(['backups'])+frame([])
    response=subprocess.run(base+['/usr/bin/python3','-c',wrapper],input=raw,capture_output=True,timeout=20)
    check(response.returncode==0, 'session helper exits cleanly on close')
    data=response.stdout; replies=[]
    while data:
        status=data[0];length=struct.unpack('>I',data[1:5])[0]
        replies.append((status,data[5:5+length].decode()));data=data[5+length:]
    check(len(replies)==3 and replies[0][0]==0 and len(json.loads(replies[0][1]))==3, 'session list response')
    check(replies[1][0]==1 and replies[2][0]==0, 'session rejects arbitrary paths and remains usable')
    check(env.read_bytes()==saved, 'read-only session does not change boot environment')
    # Keep the input writer open in an observer while the GUI parent exits.
    # PDEATHSIG must end the privileged child even without receiving pipe EOF.
    owner="""import subprocess,sys,os,struct
p=subprocess.Popen([%r,'--session'],stdin=int(sys.argv[1]),stdout=subprocess.PIPE)
header=p.stdout.read(5)
assert len(header)==5 and header[0]==0
p.stdout.read(struct.unpack('>I',header[1:])[0])
open('/control/session-child','w').write(str(p.pid))
os._exit(0)
""" % helper
    observer="""import subprocess,os,time,struct
r,w=os.pipe()
p=subprocess.Popen(['/usr/bin/python3','-c',%r,str(r)],pass_fds=(r,))
os.close(r)
os.write(w,struct.pack('>II',1,4)+b'list')
assert p.wait(timeout=5)==0
pid=open('/control/session-child').read()
dead=False
for _ in range(50):
 try:
  state=open('/proc/'+pid+'/status').read()
  dead='State:\tZ' in state
 except FileNotFoundError:dead=True
 if dead:break
 time.sleep(0.02)
os.close(w)
assert dead,'authorized helper survived its GUI parent'
print('parent-death cleanup passed')
""" % owner
    death=subprocess.run(base+['/usr/bin/python3','-c',observer],capture_output=True,text=True,timeout=20)
    check(death.returncode==0, 'session ends on parent death even if input fd leaked: '+death.stderr)
    print(f'Isolated system integration passed: {checks} assertions; host boot state untouched')
