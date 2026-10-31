#!/usr/bin/python3
"""Minimal confirmation: no request until Yes; capture once/permanent commands."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import json
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, message='Gdk.Window.process_updates is deprecated')
root=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('rbm_windows',root/'ui/windows.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from gi.repository import Gtk,Gdk,GLib
Gtk.Settings.get_default().set_property('gtk-enable-animations',False)
Gtk.IconTheme.get_default().prepend_search_path(str(root/'assets/icons'))
assert Gtk.IconTheme.get_default().load_icon('rust-boot-manager-windows11',64,Gtk.IconLookupFlags.FORCE_SIZE) is not None
class Smoke(module.WindowsShortcut):
    def __init__(self):
        super().__init__(sys.argv[1],configuration={})
        self.calls=[];self.failed=True;self.quit_calls=0;self.success=False
    def do_activate(self):
        super().do_activate();GLib.timeout_add(300,self.check)
    def request(self,args,callback):
        self.calls.append(args);callback('Authorization cancelled' if not self.success else 'OK',self.success)
    def quit(self):
        self.quit_calls+=1
    def check(self):
        try:
            assert self.calls==[] and not self.remember.get_active()
            assert self.yes_button.get_sensitive() and not self.status.get_visible()
            self.window.check_resize();self.window.queue_draw();self.window.get_window().process_updates(True)
            Gdk.Display.get_default().sync()
            pixbuf=Gdk.pixbuf_get_from_window(self.window.get_window(),0,0,self.window.get_allocated_width(),self.window.get_allocated_height())
            pixbuf.savev(str(root/'dist'/('windows-confirm-'+('zh' if self.zh else 'en')+'.png')),'png',[],[])
            self.no_button.clicked();assert self.quit_calls==1 and self.calls==[]
            self.yes_button.clicked();assert self.calls==[['windows-reboot','once']]
            assert self.status.get_visible() and self.yes_button.get_sensitive()
            self.remember.set_active(True);self.yes_button.clicked()
            assert self.calls[-1]==['windows-reboot','permanent']
            self.config['target_selector']='windows-known';self.remember.set_active(False);self.yes_button.clicked()
            assert self.calls[-1]==['windows-reboot','once','windows-known']
            self.success=True;self.yes_button.clicked();assert self.quit_calls==2
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory)/'rust-boot-manager';folder.mkdir()
                config=folder/'windows-dialog.json'
                config.write_text(json.dumps({'question':'自定义确认文字','target_selector':'known'}))
                original=module.GLib.get_user_config_dir
                try:
                    module.GLib.get_user_config_dir=lambda:directory
                    assert module.load_configuration()['question']=='自定义确认文字'
                    config.write_text('{"yes_label": false}')
                    try:
                        module.load_configuration()
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('invalid custom text accepted')
                finally:
                    module.GLib.get_user_config_dir=original
            self.failed=False
            print('Minimal Windows confirmation passed: no initial request, No cancels, unchecked once, checked permanent, denial retry, success closes')
        finally:
            Gtk.Application.quit(self)
        return False
app=Smoke()
GLib.timeout_add_seconds(10,lambda:(Gtk.Application.quit(app),False)[1])
app.run([sys.argv[0]])
sys.exit(int(app.failed))
