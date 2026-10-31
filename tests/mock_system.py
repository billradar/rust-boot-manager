#!/usr/bin/python3
"""Mounted over selected OS tools by isolated_system.py; never installed."""
import json
from pathlib import Path
import sys
name = Path(sys.argv[0]).name
control = Path('/control')
with (control / 'calls').open('a') as log:
    log.write(json.dumps([name] + sys.argv[1:]) + '\n')
args = sys.argv[1:]
if name == 'findmnt':
    if args[2] == 'FSTYPE':
        print((control / 'fstype').read_text())
    else:
        print('/dev/sda1')
elif name == 'grub-probe':
    print((control / 'abstraction').read_text())
elif name == 'update-grub':
    if (control / 'update-fails-once').exists():
        (control / 'update-fails-once').unlink()
        sys.exit('Injected update-grub failure')
    # Model regeneration while actual grubenv utilities remain real.
    cfg = Path('/boot/grub/grub.cfg')
    text = cfg.read_text()
    if Path('/etc/default/grub.d/99-rbm.cfg').exists():
        text = text.replace('set default="0"', 'set default="${saved_entry}"')
    else:
        text = text.replace('set default="${saved_entry}"', 'set default="0"')
    cfg.write_text(text)
elif name == 'efibootmgr':
    p = control / 'efi.json'
    efi = json.loads(p.read_text())
    if args == ['--delete-bootnext']:
        efi.pop('next', None)
    elif len(args) == 2 and args[0] == '--bootnext':
        efi['next'] = args[1].upper()
        if (control / 'efi-fails-once').exists():
            p.write_text(json.dumps(efi))
            (control / 'efi-fails-once').unlink()
            sys.exit('Injected partial NVRAM write failure')
    elif args:
        sys.exit('Unexpected EFI arguments')
    p.write_text(json.dumps(efi))
    if 'next' in efi:
        print('BootNext: ' + efi['next'])
    print('BootOrder: 0001,000A\nBoot0001* Debian\nBoot000A* Windows\nBoot000B Disabled')
elif name == 'systemd-run':
    if (control/'schedule-fails-once').exists():
        (control/'schedule-fails-once').unlink()
        sys.exit('Injected timer creation failure')
    p = control / 'timer'
    if p.exists():
        sys.exit('Unit rbm-reboot already exists')
    p.write_text(json.dumps(args))
elif name == 'systemctl':
    p = control / 'timer'
    if args[0] == 'stop':
        p.unlink(missing_ok=True)
    elif args[0] == 'show':
        print('ActiveState=' + ('active' if p.exists() else 'inactive'))
    else:
        sys.exit('Unexpected systemctl operation: REBOOT IS NEVER EXECUTED')
else:
    sys.exit('Unexpected mocked program: ' + name)
