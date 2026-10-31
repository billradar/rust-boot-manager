#!/usr/bin/python3
"""Minimal Windows confirmation: question, optional permanent default, Yes/No."""
import argparse
import json
import os
import sys
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Gio, GLib

CLI = '/usr/bin/rbm'
TEXT = {
    'question': ('Start Windows?', '是否启动到 Windows？'),
    'remember_label': ('Always start Windows from now on', '以后每次都从 Windows 启动'),
    'yes_label': ('Yes', '是'),
    'no_label': ('No', '否'),
}

def load_configuration():
    path = os.path.join(GLib.get_user_config_dir(), 'rust-boot-manager', 'windows-dialog.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as stream:
        text = stream.read(65537)
    if len(text) > 65536:
        raise ValueError('windows-dialog.json is too large / 确认框配置过大')
    config = json.loads(text)
    allowed = set(TEXT) | {'target_selector'}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError('Invalid windows-dialog.json keys / 确认框配置字段无效')
    for key, value in config.items():
        if not isinstance(value, str) or not value.strip() or len(value) > (4096 if key == 'target_selector' else 512):
            raise ValueError('Invalid text in windows-dialog.json / 确认框文字无效')
    return config

class WindowsShortcut(Gtk.Application):
    def __init__(self, lang, configuration=None):
        GLib.set_prgname('rust-boot-manager-windows11')
        super().__init__(application_id='org.rustbootmanager.WindowsShortcut')
        self.zh = lang == 'zh'
        self.busy = False
        self.configuration_error = None
        try:
            self.config = load_configuration() if configuration is None else configuration
        except (OSError, ValueError) as error:
            self.config = {}; self.configuration_error = str(error)

    def t(self, key):
        return self.config.get(key, TEXT[key][int(self.zh)])

    def do_activate(self):
        if hasattr(self, 'window'):
            self.window.present(); return
        self.css = Gtk.CssProvider()
        self.css.load_from_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.css'))
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = Gtk.ApplicationWindow(application=self, title=self.t('question'))
        self.window.set_icon_name('rust-boot-manager-windows11')
        self.window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.window.set_resizable(False)
        self.window.set_default_size(460, -1)
        self.window.get_style_context().add_class('rbm')
        self.window.connect('delete-event', self.on_close)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22, margin=28)
        self.window.add(content)
        heading = Gtk.Box(spacing=18)
        icon = Gtk.Image.new_from_icon_name('rust-boot-manager-windows11', Gtk.IconSize.DIALOG)
        icon.set_pixel_size(46); heading.pack_start(icon, False, False, 0)
        question = Gtk.Label(label=self.t('question'), xalign=0, wrap=True)
        question.set_max_width_chars(32)
        question.get_style_context().add_class('card-title')
        heading.pack_start(question, True, True, 0); content.pack_start(heading, False, False, 0)
        self.remember = Gtk.CheckButton(label=self.t('remember_label'))
        self.remember.set_active(False)
        content.pack_start(self.remember, False, False, 0)
        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.status.set_max_width_chars(55)
        self.status.get_style_context().add_class('card-caption')
        content.pack_start(self.status, False, False, 0)
        self.spinner = Gtk.Spinner(); content.pack_start(self.spinner, False, False, 0)
        buttons = Gtk.Box(spacing=12, homogeneous=True)
        self.no_button = Gtk.Button(label=self.t('no_label'))
        self.no_button.set_can_default(True); self.no_button.connect('clicked', lambda *_: self.quit())
        self.yes_button = Gtk.Button(label=self.t('yes_label'))
        self.yes_button.get_style_context().add_class('primary')
        self.yes_button.connect('clicked', self.confirm_restart)
        buttons.pack_start(self.no_button, True, True, 0); buttons.pack_start(self.yes_button, True, True, 0)
        content.pack_start(buttons, False, False, 0)
        self.window.set_default(self.no_button)
        self.window.show_all(); self.spinner.hide(); self.status.hide()
        if self.configuration_error:
            self.status.set_text(self.configuration_error); self.status.show(); self.yes_button.set_sensitive(False)
        # No enumeration, authentication, boot writes or timer until Yes is clicked.

    def request(self, args, callback):
        try:
            proc = Gio.Subprocess.new([CLI] + args, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as error:
            callback(str(error), False); return
        def completed(process, result):
            try:
                _, stdout, stderr = process.communicate_utf8_finish(result)
                callback((stdout or '') + (stderr or ''), process.get_successful())
            except GLib.Error as error:
                callback(str(error), False)
        proc.communicate_utf8_async(None, None, completed)

    def confirm_restart(self, *_):
        if self.busy or self.configuration_error:
            return
        mode = 'permanent' if self.remember.get_active() else 'once'
        args = ['windows-reboot', mode]
        if self.config.get('target_selector'):
            args.append(self.config['target_selector'])
        self.busy = True; self.spinner.show(); self.spinner.start()
        self.remember.set_sensitive(False); self.yes_button.set_sensitive(False); self.no_button.set_sensitive(False)
        self.status.hide()
        def completed(text, success):
            self.busy = False; self.spinner.stop(); self.spinner.hide()
            if success:
                self.quit(); return
            self.remember.set_sensitive(True); self.yes_button.set_sensitive(True); self.no_button.set_sensitive(True)
            self.status.set_text(text); self.status.show()
        self.request(args, completed)

    def on_close(self, *_):
        if self.busy:
            return True
        self.quit(); return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lang', choices=['en', 'zh'], default='zh' if os.environ.get('LANG', '').startswith('zh') else 'en')
    args = parser.parse_args()
    if os.geteuid() == 0:
        sys.exit('Run this window as a normal user / 请以普通用户打开确认窗口')
    sys.exit(WindowsShortcut(args.lang).run([sys.argv[0]]))
