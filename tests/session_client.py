#!/usr/bin/python3
"""Exercise the actual async pipe client using a local protocol peer, no root."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('client',root/'ui/privilege.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from gi.repository import Gio,GLib

PEER='''#!/usr/bin/python3
import os,struct,sys
print(os.getpid(),file=open(sys.argv[1],'a'),flush=True)
def exact(n):
 data=b''
 while len(data)<n:
  part=sys.stdin.buffer.read(n-len(data))
  if not part:sys.exit(0)
  data+=part
 return data
while True:
 count=struct.unpack('>I',exact(4))[0]
 args=[exact(struct.unpack('>I',exact(4))[0]).decode() for _ in range(count)]
 if args==['crash']:sys.exit(1)
 text=('blocked' if args==['bad'] else 'reply:'+','.join(args)).encode()
 sys.stdout.buffer.write(bytes([int(args==['bad'])])+struct.pack('>I',len(text))+text);sys.stdout.buffer.flush()
'''
with tempfile.TemporaryDirectory(prefix='rbm-session-client-') as work:
    work=Path(work);peer=work/'peer.py';peer.write_text(PEER)
    starts=work/'starts'
    original=Gio.Subprocess.new
    def launch(argv, flags):
        assert argv==['/usr/bin/pkexec',module.HELPER,'--session']
        return original(['/usr/bin/python3',str(peer),str(starts)],flags)
    Gio.Subprocess.new=launch
    session=module.PrivilegeSession();loop=GLib.MainLoop();failed=[True]
    def check(condition):
        if not condition:raise AssertionError('session client assertion failed')
    def fourth(text,ok):
        check(ok and text=='reply:again');check(len(starts.read_text().splitlines())==2)
        session.call(['crash'],crashed)
    def crashed(text,ok):
        check(not ok and session.process is None)
        failed[0]=False;loop.quit()
    def third(text,ok):
        check(ok and text=='reply:logs');check(len(starts.read_text().splitlines())==1)
        retired=session.process
        session.close();check(session.process is None)
        def closed(process,result):
            process.wait_finish(result)
            check(process.get_if_exited())
            session.call(['again'],fourth)
        retired.wait_async(None,closed)
    def second(text,ok):
        check(not ok and 'blocked' in text);session.call(['logs'],third)
    def first(text,ok):
        check(ok and text=='reply:list');session.call(['bad'],second)
    session.call(['list'],first)
    GLib.timeout_add_seconds(10,lambda:(loop.quit(),False)[1])
    loop.run();session.close();Gio.Subprocess.new=original
    assert not failed[0]
print('Session client passed: one process reused, errors recover, close reauthorizes, crash clears session')
