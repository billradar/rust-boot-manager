"""Optional Nautilus 4 background context menu extension (runs as desktop user)."""
from gi.repository import GObject, Nautilus, Gio

class BootManagerMenu(GObject.GObject, Nautilus.MenuProvider):
    def get_background_items(self, *args):
        item = Nautilus.MenuItem(name='RBM::Open', label='Boot Manager / 启动管理器', tip='Open boot manager')
        item.connect('activate', lambda *_: Gio.Subprocess.new(['/usr/bin/rbm', 'gui'], Gio.SubprocessFlags.NONE))
        return [item]
