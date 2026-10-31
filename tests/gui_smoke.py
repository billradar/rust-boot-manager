#!/usr/bin/python3
"""Run under Xvfb. Real parser/async pipe; mutations are captured, never executed."""
import importlib.util
from pathlib import Path
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, message="Gdk.Window.process_updates is deprecated")

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('rbm_gui', root / 'ui/gui.py')
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)
gui.CLI = str(root / 'target/release/rbm')
from gi.repository import GLib, Gdk, Gtk

# Headless frame clocks do not provide reliable animation timing.
Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
Gtk.IconTheme.get_default().prepend_search_path(str(root/'assets/icons'))
for icon in ['rust-boot-manager', 'rust-boot-manager-windows11']:
    assert Gtk.IconTheme.get_default().load_icon(icon, 64, Gtk.IconLookupFlags.FORCE_SIZE) is not None

class Smoke(gui.Manager):
    def __init__(self):
        super().__init__(sys.argv[1] if len(sys.argv) > 1 else 'en', False)
        self.restart_available = True  # fixture exercises all callbacks; backend tests cover missing systemd
        self.failed = True
        self.captured = []

    def setup_tray(self):
        pass

    def confirm(self, message):
        return True

    def refresh(self, *_):
        def loaded(text):
            import json
            entries = json.loads(text)
            assert len(entries) == 3
            self.populate_entries(entries)
            self.say('已识别 3 个启动项。选择目标后应用设置。' if self.zh else '3 boot entries found. Select a target to get started.')
            GLib.timeout_add(300, self.check_language_switch if getattr(self, 'switch_test', False) else self.check)
        super().invoke(['list', '--file', str(root / 'tests/fixtures/grub.cfg')], loaded)

    def invoke(self, args, done=None, confirm=False):
        self.captured.append(args)
        if done:
            raise AssertionError('Unexpected follow-up')

    def check(self):
        try:
            assert self.window.get_visible()
            assert self.entries.get_active_id() == 'gnulinux-simple-123'
            self.apply()
            assert self.captured[-1] == ['set', 'once', 'gnulinux-simple-123']
            self.mode.set_active_id('permanent'); self.apply()
            assert self.captured[-1][1] == 'permanent'
            for button in self.controls:
                if button.get_label() == self.t('schedule'):
                    button.clicked()
            assert self.captured[-1] == ['reboot', '60']
            self.mode.set_active_id('once')
            for page in ['power', 'snapshots', 'firmware', 'diagnostics', 'boot']:
                self.navigate(page)
                assert self.stack.get_visible_child_name() == page
            GLib.timeout_add(250, self.capture)
        except Exception:
            import traceback
            traceback.print_exc()
            self.quit()
        return False

    def capture(self):
        try:
            self.window.check_resize()
            self.window.queue_draw()
            self.window.get_window().process_updates(True)
            Gdk.Display.get_default().sync()
            win = self.window.get_window()
            pixbuf = Gdk.pixbuf_get_from_window(win, 0, 0, self.window.get_allocated_width(), self.window.get_allocated_height())
            pixbuf.savev(str(root / 'dist' / ('gui-zh.png' if self.zh else 'gui-en.png')), 'png', [], [])
            self.remaining_pages = ['snapshots', 'firmware', 'power', 'diagnostics']
            self.capture_next_page()
        except Exception:
            import traceback
            traceback.print_exc()
            self.quit()
        return False

    def capture_next_page(self):
        if not self.remaining_pages:
            self.navigate('boot')
            self.check_async_error()
            return False
        page = self.remaining_pages.pop(0)
        self.navigate(page)
        def save():
            assert self.stack.get_visible_child_name() == page
            assert not self.stack.get_transition_running()
            self.window.check_resize()
            self.window.queue_draw()
            self.window.get_window().process_updates(True)
            Gdk.Display.get_default().sync()
            win = self.window.get_window()
            pixbuf = Gdk.pixbuf_get_from_window(win, 0, 0, self.window.get_allocated_width(), self.window.get_allocated_height())
            pixbuf.savev(str(root / 'dist' / ('gui-' + ('zh' if self.zh else 'en') + '-' + page + '.png')), 'png', [], [])
            self.capture_next_page()
            return False
        GLib.timeout_add(250, save)
        return False

    def check_async_error(self):
        def poll():
            if self.busy:
                return True
            buf = self.output.get_buffer()
            message = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            assert 'Error' in message
            assert self.details.get_reveal_child()
            self.navigate('power')
            self.mode.set_active_id('permanent')
            self.entries.set_active_id('gnulinux-advanced-123>recovery-123')
            self.switch_test = True
            self.expected_zh = not self.zh
            self.language.set_active_id('zh' if self.expected_zh else 'en')
            return False
        super().invoke(['list', '--file', '/rbm-nonexistent-test-fixture'])
        GLib.timeout_add(100, poll)

    def check_language_switch(self):
        assert self.zh == self.expected_zh
        assert self.stack.get_visible_child_name() == 'power'
        assert self.mode.get_active_id() == 'permanent'
        assert self.entries.get_active_id() == 'gnulinux-advanced-123>recovery-123'
        self.failed = False
        print('GUI smoke passed: both locales, navigation, actions, async errors and language state preservation')
        self.quit()
        return False

app = Smoke()
GLib.timeout_add_seconds(10, lambda: (app.quit(), False)[1])
app.run([sys.argv[0]])
sys.exit(int(app.failed))
