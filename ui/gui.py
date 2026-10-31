#!/usr/bin/python3
"""Unprivileged GTK frontend. All privileged operations go through the fixed Rust CLI."""
import argparse
import importlib.util
import json
import os
import sys
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, Pango

CLI = "/usr/bin/rbm"
_privilege_spec = importlib.util.spec_from_file_location('rbm_privilege', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'privilege.py'))
_privilege_module = importlib.util.module_from_spec(_privilege_spec)
_privilege_spec.loader.exec_module(_privilege_module)
PrivilegeSession = _privilege_module.PrivilegeSession

TEXT = {
 'title': ('Rust Boot Manager', 'Rust 启动管理器'),
 'refresh': ('Refresh entries', '刷新启动项'),
 'once': ('Next boot only', '仅下次启动'),
 'permanent': ('Permanent default', '永久默认启动'),
 'apply': ('Apply boot target', '应用启动目标'),
 'backup': ('Back up configuration', '备份配置'),
 'restore': ('Restore snapshot', '恢复快照'),
 'efi': ('UEFI BootNext fallback', 'UEFI BootNext 备用方案'),
 'clear': ('Clear GRUB next target', '清除 GRUB 一次性目标'),
 'eficlear': ('Clear UEFI BootNext', '清除 UEFI BootNext'),
 'schedule': ('Schedule restart', '计划重启'),
 'cancel': ('Cancel restart', '取消重启'),
 'diagnose': ('Diagnostics', '诊断信息'),
 'logs': ('Audit log', '审计日志'),
 'status': ('Restart status', '重启状态'),
 'quit': ('Quit', '退出'),
 'show': ('Open manager', '打开管理器'),
 'confirm': ('Confirm operation', '确认操作'),
 'notice': ('Applying a target does not reboot. Cancel restart only stops the timer.\nBackups cover GRUB defaults, this app’s fragment, grubenv and a reference grub.cfg.',
            '应用启动目标不会立即重启。取消重启仅停止计时器。\n备份包括 GRUB 默认配置、本程序片段、grubenv 和 grub.cfg 参考副本。'),
 'busy': ('Working… authorization may be required.', '正在处理…可能需要管理员授权。'),
 'delay': ('Restart delay (seconds, 10–86400)', '重启延迟（秒，10–86400）'),
 'empty': ('No selection', '请先选择启动项'),
 'traymissing': ('Tray unavailable. Install gir1.2-ayatanaappindicator3-0.1 and enable your desktop’s tray extension.',
                 '托盘不可用。请安装 gir1.2-ayatanaappindicator3-0.1，并启用桌面托盘扩展。'),
}

TEXT.update({
 'boot_page': ('Boot selection', '启动选择'),
 'snapshots_page': ('Snapshots', '备份与恢复'),
 'firmware_page': ('UEFI firmware', 'UEFI 固件'),
 'power_page': ('Restart planner', '重启计划'),
 'diagnostics_page': ('Diagnostics', '诊断与日志'),
 'boot_heading': ('Your next destination.', '下一站，由你决定。'),
 'boot_subtitle': ('Choose a system and decide how you want to boot.', '选择系统，设置下一次启动方式。'),
 'systems': ('Available systems', '可用系统'),
 'systems_sub': ('Detected from your GRUB configuration', '自动识别 GRUB 配置中的启动项'),
 'mode_heading': ('Boot preference', '启动偏好'),
 'once_desc': ('Return to your default after one boot', '本次使用，下次回到原默认系统'),
 'permanent_desc': ('Use this system as your new default', '将此系统设为以后的默认选择'),
 'apply_tip': ('Boot selection and restart are separate steps.', '设置启动目标后，可在「重启计划」中安排重启。'),
 'ready': ('Ready when you are', '准备就绪'),
 'windows': ('Start Windows', '启动 Windows'),
 'windows_desc': ('Confirm a Windows boot, optionally making it the default.', '确认启动 Windows，可选以后每次默认启动。'),
 'shortcut': ('Create Windows desktop shortcut', '创建 Windows 桌面快捷方式'),
 'details': ('Activity details', '操作详情'),
 'workspace': ('WORKSPACE', '工作空间'),
 'local': ('Local system utility', '本机系统工具'),
 'snapshot_sub': ('Keep a recovery point before changing your boot setup.', '为启动配置保留一个可恢复的时间点。'),
 'backup_desc': ('Save GRUB defaults, the managed fragment and environment block.', '保存 GRUB 默认配置、本程序配置片段和环境块。'),
 'restore_desc': ('Choose a saved snapshot. Current settings are backed up first.', '选择已保存的快照，恢复前会自动备份当前设置。'),
 'scope': ('Snapshot scope: GRUB defaults, this app’s fragment, grubenv and a reference grub.cfg. Custom scripts and the EFI partition are excluded.',
           '备份范围：GRUB 默认配置、本程序片段、grubenv 及 grub.cfg 参考副本。不包含自定义脚本和 EFI 分区。'),
 'firmware_sub': ('A one-time firmware target when GRUB is not the right fit.', '通过固件 BootNext 设置一次性启动目标。'),
 'firmware_desc': ('Select an active UEFI entry. Your firmware boot order stays in place.', '从已激活的 UEFI 启动项中选择目标，保留现有固件启动顺序。'),
 'firmware_tip': ('Firmware entries and GRUB entries are separate. Always check the selected target.', '固件启动项与 GRUB 启动项相互独立，请核对所选目标。'),
 'power_sub': ('Give yourself a moment before the system restarts.', '留出保存工作的时间，再从容重启。'),
 'delay_short': ('Delay in seconds', '延迟秒数'),
 'delay_hint': ('From 10 seconds to 24 hours', '支持 10 秒至 24 小时'),
 'cancel_desc': ('Stop this app’s scheduled restart. The selected boot target is retained.', '停止本程序的重启计时器，保留已设置的启动目标。'),
 'diagnostics_sub': ('Understand your boot setup and review recent operations.', '了解启动环境，查看操作记录。'),
 'diagnostics_desc': ('Inspect GRUB paths, environment variables and restart timer state.', '检查 GRUB 文件、环境变量和重启计时器状态。'),
 'logs_desc': ('Review authorized operations, results and recovery information.', '查看授权操作、执行结果和恢复记录。'),
 'clearonce_desc': ('Remove a previously selected one-time GRUB target.', '移除之前设置的 GRUB 一次性启动目标。'),
 'eficlear_desc': ('Remove a pending firmware BootNext selection.', '清除尚未消费的固件 BootNext 目标。'),
 'saved': ('Operation completed', '操作已完成'),
 'failed': ('Could not complete the operation. See activity details.', '操作未完成，请查看操作详情。'),
})

class Manager(Gtk.Application):
    def __init__(self, lang, tray):
        GLib.set_prgname('rust-boot-manager')
        super().__init__(application_id='org.rustbootmanager.Manager', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.zh = lang == 'zh'
        self.want_tray = tray
        self.indicator = None
        self.busy = False
        self.controls = []
        self.current_entries = []
        self.authority = PrivilegeSession()
        self.restart_available = os.path.isdir("/run/systemd/system")
        self.unavailable_controls = set()

    def t(self, key):
        return TEXT[key][int(self.zh)]

    @staticmethod
    def styled(widget, *classes):
        for name in classes:
            widget.get_style_context().add_class(name)
        return widget

    def label(self, text, style=None, wrap=False):
        label = Gtk.Label(label=text, xalign=0, wrap=wrap)
        if style:
            self.styled(label, style)
        if wrap:
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_max_width_chars(68)
        return label

    def do_activate(self):
        if hasattr(self, 'window'):
            self.present_window()
            return
        if not hasattr(self, 'css'):
            self.css = Gtk.CssProvider()
            self.css.load_from_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.css'))
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = self.styled(Gtk.ApplicationWindow(application=self, title=self.t('title')), 'rbm')
        self.window.set_icon_name('rust-boot-manager')
        self.window.set_default_size(1120, 790)
        self.window.set_size_request(950, 690)
        self.window.connect('delete-event', self.on_close)
        header = Gtk.HeaderBar(title='Rust Boot Manager', show_close_button=True)
        self.language = Gtk.ComboBoxText()
        self.language.append('en', 'English'); self.language.append('zh', '简体中文')
        self.language.set_active_id('zh' if self.zh else 'en')
        self.language.connect('changed', self.change_language)
        header.pack_end(self.language)
        self.window.set_titlebar(header)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body = Gtk.Box()
        outer.pack_start(body, True, True, 0)
        self.window.add(outer)
        sidebar = self.styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), 'sidebar')
        sidebar.set_size_request(220, -1)
        body.pack_start(sidebar, False, False, 0)
        brand = Gtk.Box(spacing=12, margin_start=22, margin_end=16, margin_top=30, margin_bottom=32)
        mark = self.styled(Gtk.Image.new_from_icon_name('rust-boot-manager', Gtk.IconSize.LARGE_TOOLBAR), 'brand-mark')
        brand.pack_start(mark, False, False, 0)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        names.pack_start(self.label('BOOT MANAGER', 'brand'), False, False, 0)
        distribution = GLib.get_os_info('NAME') or 'Linux'
        distro_label = self.label(distribution, 'brand-caption')
        distro_label.set_ellipsize(Pango.EllipsizeMode.END); distro_label.set_max_width_chars(22)
        names.pack_start(distro_label, False, False, 0)
        brand.pack_start(names, False, False, 0)
        sidebar.pack_start(brand, False, False, 0)
        section = self.label(self.t('workspace'), 'nav-section'); section.set_margin_start(26)
        section.set_margin_bottom(8); sidebar.pack_start(section, False, False, 0)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=140)
        self.nav_buttons = {}
        for key, icon in [('boot', 'drive-harddisk-symbolic'), ('snapshots', 'document-save-symbolic'),
                          ('firmware', 'computer-symbolic'), ('power', 'system-reboot-symbolic'),
                          ('diagnostics', 'document-properties-symbolic')]:
            button = self.styled(Gtk.ToggleButton(), 'nav')
            row = Gtk.Box(spacing=12)
            row.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
            row.pack_start(self.label(self.t(key + '_page')), False, False, 0)
            button.add(row); button.set_margin_start(12); button.set_margin_end(12)
            button.connect('clicked', lambda _, page=key: self.navigate(page))
            self.nav_buttons[key] = button; sidebar.pack_start(button, False, False, 0)
        foot = self.styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=22), 'sidebar-foot')
        foot.set_margin_top(28)
        version = self.label('●   ' + self.t('local')); version.set_margin_top(18)
        foot.pack_start(version, False, False, 0)
        foot.pack_start(self.label('v0.5.0  ·  GTK / Rust'), False, False, 0)
        sidebar.pack_end(foot, False, False, 0)
        body.pack_start(self.stack, True, True, 0)
        boot = self.page('boot', self.t('boot_heading'), self.t('boot_subtitle'))
        card = self.card()
        heading = Gtk.Box(spacing=10)
        heading.pack_start(self.label(self.t('systems'), 'card-title'), True, True, 0)
        self.count_badge = self.styled(Gtk.Label(label='GRUB'), 'badge')
        heading.pack_end(self.count_badge, False, False, 0)
        card.pack_start(heading, False, False, 0)
        card.pack_start(self.label(self.t('systems_sub'), 'card-caption'), False, False, 0)
        self.entries = Gtk.ComboBoxText()  # model shared with selection and tests
        self.boot_list = self.styled(Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE), 'boot-list')
        self.boot_list.connect('row-selected', self.row_selected)
        self.entries.connect('changed', self.entry_changed)
        entry_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        entry_scroll.set_min_content_height(190); entry_scroll.set_max_content_height(190)
        entry_scroll.set_propagate_natural_height(True); entry_scroll.add(self.boot_list)
        card.pack_start(entry_scroll, True, True, 0)
        boot.pack_start(card, False, False, 0)
        modes = self.card()
        modes.pack_start(self.label(self.t('mode_heading'), 'card-title'), False, False, 0)
        mode_row = Gtk.Box(spacing=12, homogeneous=True)
        self.mode = Gtk.ComboBoxText()
        self.mode.append('once', self.t('once')); self.mode.append('permanent', self.t('permanent'))
        self.mode.set_active_id('once')
        self.mode_buttons = {}
        group = None
        for key in ('once', 'permanent'):
            radio = self.styled(Gtk.RadioButton.new_from_widget(group), 'mode-card')
            if group is None:
                group = radio
            radio.set_mode(False)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            inner.pack_start(self.label(self.t(key), 'mode-title'), False, False, 0)
            inner.pack_start(self.label(self.t(key + '_desc'), 'mode-caption', True), False, False, 0)
            radio.add(inner)
            radio.connect('toggled', lambda b, m=key: self.mode.set_active_id(m) if b.get_active() else None)
            self.mode_buttons[key] = radio; mode_row.pack_start(radio, True, True, 0)
            self.controls.append(radio)
        self.mode.connect('changed', lambda combo: self.mode_buttons[combo.get_active_id()].set_active(True))
        modes.pack_start(mode_row, False, False, 0); boot.pack_start(modes, False, False, 0)
        actions = Gtk.Box(spacing=10)
        self.button(actions, 'apply', self.apply, 'primary')
        self.button(actions, 'refresh', self.refresh)
        boot.pack_start(actions, False, False, 0)
        note = self.label('设置目标不会立即重启' if self.zh else 'Applying a target does not restart.', 'card-caption', True)
        note.set_max_width_chars(24); note.set_ellipsize(Pango.EllipsizeMode.END)
        actions.pack_end(note, True, True, 8)
        snapshots = self.page('snapshots', self.t('snapshots_page'), self.t('snapshot_sub'))
        self.action_card(snapshots, 'document-save-symbolic', 'backup', 'backup_desc', lambda *_: self.invoke(['backup'], confirm=True), 'primary')
        self.action_card(snapshots, 'document-revert-symbolic', 'restore', 'restore_desc', self.restore)
        snapshots.pack_start(self.tip(self.t('scope')), False, False, 0)
        firmware = self.page('firmware', self.t('firmware_page'), self.t('firmware_sub'))
        self.action_card(firmware, 'computer-symbolic', 'efi', 'firmware_desc', self.efi, 'primary')
        self.action_card(firmware, 'edit-clear-symbolic', 'eficlear', 'eficlear_desc', lambda *_: self.invoke(['efi-clear'], confirm=True))
        firmware.pack_start(self.tip(self.t('firmware_tip')), False, False, 0)
        power = self.page('power', self.t('power_page'), self.t('power_sub'))
        self.action_card(power, 'computer-symbolic', 'windows', 'windows_desc', self.open_windows, 'primary')
        shortcut_row = Gtk.Box(); self.button(shortcut_row, 'shortcut', lambda *_: self.invoke(['desktop-shortcut', 'install']))
        power.pack_start(shortcut_row, False, False, 0)
        planner = self.card()
        planner.pack_start(self.label(self.t('delay_short'), 'card-title'), False, False, 0)
        planner.pack_start(self.label(self.t('delay_hint'), 'card-caption'), False, False, 0)
        row = Gtk.Box(spacing=12)
        self.delay = Gtk.SpinButton.new_with_range(10, 86400, 10); self.delay.set_value(60)
        self.delay.set_numeric(True); self.delay.set_width_chars(7)
        row.pack_start(self.delay, False, False, 0)
        self.button(row, 'schedule', lambda *_: self.invoke(['reboot', str(self.delay.get_value_as_int())], confirm=True), 'primary')
        self.button(row, 'status', lambda *_: self.invoke(['status']))
        planner.pack_start(row, False, False, 0); power.pack_start(planner, False, False, 0)
        self.action_card(power, 'process-stop-symbolic', 'cancel', 'cancel_desc', lambda *_: self.invoke(['cancel']), 'danger')
        self.action_card(power, 'edit-clear-symbolic', 'clear', 'clearonce_desc', lambda *_: self.invoke(['clear-once'], confirm=True))
        diagnostics = self.page('diagnostics', self.t('diagnostics_page'), self.t('diagnostics_sub'))
        self.action_card(diagnostics, 'document-properties-symbolic', 'diagnose', 'diagnostics_desc', lambda *_: self.invoke(['diagnose'], done=lambda _: self.show_details()), 'primary')
        self.action_card(diagnostics, 'text-x-generic-symbolic', 'logs', 'logs_desc', lambda *_: self.invoke(['logs'], done=lambda _: self.show_details()))
        status = self.styled(Gtk.Box(spacing=10), 'status-bar')
        self.spinner = Gtk.Spinner()
        self.status_icon = self.styled(Gtk.Image.new_from_icon_name('object-select-symbolic', Gtk.IconSize.MENU), 'status-ok')
        status.pack_start(self.status_icon, False, False, 0); status.pack_start(self.spinner, False, False, 0)
        self.status_label = self.label(self.t('ready'), 'status-text')
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        status.pack_start(self.status_label, True, True, 0)
        self.details_toggle = self.styled(Gtk.ToggleButton(label=self.t('details')), 'quiet')
        status.pack_end(self.details_toggle, False, False, 0)
        outer.pack_start(status, False, False, 0)
        self.details = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP, transition_duration=120)
        self.output = self.styled(Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR), 'output')
        self.output.set_left_margin(24); self.output.set_right_margin(24); self.output.set_top_margin(10); self.output.set_bottom_margin(10)
        scroll = Gtk.ScrolledWindow(); scroll.set_min_content_height(120); scroll.set_max_content_height(120); scroll.add(self.output)
        self.details.add(scroll); outer.pack_start(self.details, False, False, 0)
        self.details_toggle.connect('toggled', lambda b: self.details.set_reveal_child(b.get_active()))
        self.window.show_all(); self.spinner.hide()
        self.navigate(getattr(self, 'saved_page', 'boot'))
        self.mode.set_active_id(getattr(self, 'saved_mode', 'once'))
        self.setup_tray()
        if self.want_tray and self.indicator:
            self.window.hide()
        else:
            self.refresh()

    def page(self, key, title, subtitle):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=24)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        heading.pack_start(self.label('BOOT / ' + self.t(key + '_page').upper(), 'eyebrow'), False, False, 0)
        heading.pack_start(self.label(title, 'page-title'), False, False, 0)
        heading.pack_start(self.label(subtitle, 'page-subtitle', True), False, False, 0)
        heading.set_margin_bottom(6)
        content.pack_start(heading, False, False, 0)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.add(content); self.stack.add_named(scroll, key)
        return content

    def card(self):
        frame = self.styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), 'card')
        return frame

    def tip(self, text):
        box = self.styled(Gtk.Box(spacing=10), 'tip')
        box.pack_start(Gtk.Image.new_from_icon_name('dialog-information-symbolic', Gtk.IconSize.MENU), False, False, 0)
        box.pack_start(self.label(text, wrap=True), True, True, 0)
        return box

    def action_card(self, parent, icon, action, description, callback, style=None):
        card = self.card()
        row = Gtk.Box(spacing=14)
        row.pack_start(self.styled(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR), 'entry-icon'), False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        text.pack_start(self.label(self.t(action), 'card-title'), False, False, 0)
        text.pack_start(self.label(self.t(description), 'card-caption', True), False, False, 0)
        row.pack_start(text, True, True, 0); card.pack_start(row, False, False, 0)
        buttons = Gtk.Box(); self.button(buttons, action, callback, style)
        card.pack_start(buttons, False, False, 0); parent.pack_start(card, False, False, 0)

    def navigate(self, page):
        if getattr(self, 'navigating', False):
            return
        self.navigating = True
        self.stack.set_visible_child_name(page)
        for key, button in self.nav_buttons.items():
            button.set_active(key == page)
        self.navigating = False

    def populate_entries(self, values):
        previous = self.entries.get_active_id() or getattr(self, 'saved_selector', None)
        self.saved_selector = None
        self.current_entries = values
        self.entries.remove_all()
        for child in self.boot_list.get_children():
            self.boot_list.remove(child)
        for entry in values:
            self.entries.append(entry['selector'], entry['title'])
            row = self.styled(Gtk.ListBoxRow(), 'boot-row'); row.selector = entry['selector']
            line = Gtk.Box(spacing=13)
            line.pack_start(self.styled(Gtk.Image.new_from_icon_name('drive-harddisk-symbolic', Gtk.IconSize.LARGE_TOOLBAR), 'entry-icon'), False, False, 0)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            title = self.label(entry['title'], 'entry-title'); title.set_ellipsize(Pango.EllipsizeMode.END)
            title.set_max_width_chars(52); title.set_tooltip_text(entry['title'])
            text.pack_start(title, False, False, 0)
            ident = self.label(entry['selector'], 'entry-id'); ident.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            ident.set_max_width_chars(58); text.pack_start(ident, False, False, 0)
            line.pack_start(text, True, True, 0)
            line.pack_end(self.styled(Gtk.Image.new_from_icon_name('object-select-symbolic', Gtk.IconSize.MENU), 'checkmark'), False, False, 0)
            row.add(line); self.boot_list.add(row)
        self.boot_list.show_all()
        self.count_badge.set_text((str(len(values)) + ' 个启动项') if self.zh else (str(len(values)) + ' detected'))
        if values:
            desired = previous
            if not desired or not self.entries.set_active_id(desired):
                self.entries.set_active(0)
        if self.indicator:
            self.update_tray_menu()

    def row_selected(self, _, row):
        if row and self.entries.get_active_id() != row.selector:
            self.entries.set_active_id(row.selector)

    def entry_changed(self, combo):
        for row in self.boot_list.get_children():
            if row.selector == combo.get_active_id():
                self.boot_list.select_row(row)
                break

    def button(self, row, key, callback, style=None):
        button = Gtk.Button(label=self.t(key))
        if style:
            self.styled(button, style)
        button.connect('clicked', callback)
        if key in ('schedule', 'cancel', 'status', 'windows') and not self.restart_available:
            button.set_sensitive(False)
            button.set_tooltip_text('Requires a running systemd system / 此功能需要运行中的 systemd')
            self.unavailable_controls.add(button)
        row.pack_start(button, False, False, 0); self.controls.append(button)
        return button

    def show_details(self):
        self.details_toggle.set_active(True)

    def say(self, text):
        self.output.get_buffer().set_text(text)
        error = 'Error / 错误:' in text
        context = self.status_icon.get_style_context()
        for name in ('status-ok', 'status-error', 'status-busy'):
            context.remove_class(name)
        context.add_class('status-error' if error else ('status-busy' if self.busy else 'status-ok'))
        self.status_icon.set_from_icon_name('dialog-warning-symbolic' if error else 'object-select-symbolic', Gtk.IconSize.MENU)
        self.status_label.set_text(self.t('failed') if error else (self.t('busy') if self.busy else (text.splitlines()[0][:100] if text else self.t('saved'))))
        if error:
            self.show_details()

    def confirm(self, message):
        d = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.OK_CANCEL, text=self.t('confirm'))
        d.format_secondary_text(message)
        d.set_default_response(Gtk.ResponseType.CANCEL)
        result = d.run() == Gtk.ResponseType.OK; d.destroy()
        return result

    def describe_operation(self, args):
        if args[0] == 'set':
            title = next((e['title'] for e in self.current_entries if e['selector'] == args[2]), args[2])
            return self.t(args[1]) + '\n\n' + title + '\n\n' + self.t('apply_tip')
        if args[0] == 'reboot':
            return (f'系统将在 {args[1]} 秒后重启。请先保存工作。' if self.zh else f'The system will restart in {args[1]} seconds. Save your work first.')
        labels = {'backup': 'backup', 'restore': 'restore', 'efi-next': 'efi', 'efi-clear': 'eficlear', 'clear-once': 'clear'}
        return self.t(labels.get(args[0], 'confirm')) + ('\n\n' + args[1] if len(args) > 1 else '')

    def invoke(self, args, done=None, confirm=False):
        if self.busy:
            return
        if confirm and not self.confirm(self.describe_operation(args)):
            return
        self.busy = True
        self.spinner.show(); self.spinner.start()
        self.language.set_sensitive(False)
        for control in self.controls:
            control.set_sensitive(False)
        self.say(self.t('busy'))
        def reported(text, success):
            self.finish()
            self.say(text or self.t('saved'))
            if success and done:
                try:
                    done(text)
                except (ValueError, KeyError, TypeError) as error:
                    self.say('Error / 错误: ' + str(error))
        local = args[0] == 'desktop-shortcut' or args[:2] == ['list', '--file']
        if not local:
            self.authority.call(args, reported)
            return
        try:
            process = Gio.Subprocess.new([CLI] + args, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as error:
            self.finish(); self.say(str(error)); return
        def completed(proc, result):
            try:
                _, stdout, stderr = proc.communicate_utf8_finish(result)
                success = proc.get_successful()
                self.finish()
                self.say((stdout or '') + (stderr or ''))
                if success and done:
                    done(stdout or '')
            except (GLib.Error, ValueError, KeyError) as error:
                self.finish(); self.say(str(error))
        process.communicate_utf8_async(None, None, completed)

    def finish(self):
        self.busy = False
        self.spinner.stop(); self.spinner.hide()
        self.language.set_sensitive(True)
        for control in self.controls:
            control.set_sensitive(control not in self.unavailable_controls)

    def refresh(self, *_):
        def update(text):
            values = json.loads(text)
            self.populate_entries(values)
            self.say((f'已识别 {len(values)} 个启动项。选择目标后应用设置。') if self.zh else (f'{len(values)} boot entries found. Select a target to get started.'))
        self.invoke(['list'], update)

    def open_windows(self, *_):
        try:
            Gio.Subprocess.new([CLI, 'windows', '--lang', 'zh' if self.zh else 'en'], Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            self.say('Error / 错误: ' + str(error))

    def apply(self, *_):
        selector = self.entries.get_active_id()
        if not selector:
            self.say(self.t('empty')); return
        self.invoke(['set', self.mode.get_active_id(), selector], confirm=True)

    def choose(self, title, choices, callback):
        d = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        d.add_button('Cancel / 取消', Gtk.ResponseType.CANCEL)
        d.add_button('OK / 确定', Gtk.ResponseType.OK)
        combo = Gtk.ComboBoxText()
        for key, label in choices:
            combo.append(key, label)
        combo.set_active(0)
        d.get_content_area().pack_start(combo, False, False, 16)
        d.show_all(); response = d.run(); key = combo.get_active_id(); d.destroy()
        if response == Gtk.ResponseType.OK and key:
            callback(key)

    def restore(self, *_):
        self.invoke(['backups'], lambda text: self.choose(self.t('restore'), [(s,s) for s in text.splitlines()],
                    lambda key: self.invoke(['restore', key], confirm=True)))

    def efi(self, *_):
        def choose(text):
            import re
            choices = [(m.group(1), m.group(2)) for line in text.splitlines()
                       if (m := re.match(r'^Boot([0-9A-Fa-f]{4})\*\s+(.*)$', line))]
            self.choose(self.t('efi'), choices, lambda key: self.invoke(['efi-next', key], confirm=True))
        self.invoke(['efi-list'], choose)

    def change_language(self, combo):
        # Rebuild the view without restarting the application or privileged core.
        if self.busy:
            return
        self.saved_page = self.stack.get_visible_child_name()
        self.saved_mode = self.mode.get_active_id()
        self.saved_selector = self.entries.get_active_id()
        self.zh = combo.get_active_id() == 'zh'
        if self.indicator:
            self.indicator.set_status(self.indicator_module.IndicatorStatus.PASSIVE)
            self.indicator = None
        self.window.destroy(); del self.window; self.controls = []; self.unavailable_controls = set()
        self.do_activate()

    def setup_tray(self):
        # A library alone does not imply that the desktop can display an indicator.
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            owner = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                                  'org.freedesktop.DBus', 'NameHasOwner',
                                  GLib.Variant('(s)', ('org.kde.StatusNotifierWatcher',)),
                                  GLib.VariantType.new('(b)'), Gio.DBusCallFlags.NONE, 1000, None)
            if not owner.unpack()[0]:
                raise RuntimeError('No tray host')
        except (GLib.Error, RuntimeError):
            if self.want_tray:
                GLib.idle_add(lambda: (self.say(self.t('traymissing')), False)[1])
            return
        for namespace in ('AyatanaAppIndicator3', 'AppIndicator3'):
            try:
                gi.require_version(namespace, '0.1')
                import importlib
                module = importlib.import_module('gi.repository.' + namespace)
                self.indicator_module = module
                self.indicator = module.Indicator.new('rust-boot-manager', 'rust-boot-manager', module.IndicatorCategory.SYSTEM_SERVICES)
                self.update_tray_menu()
                self.indicator.set_status(module.IndicatorStatus.ACTIVE)
                return
            except (ValueError, ImportError):
                continue
        if self.want_tray:
            GLib.idle_add(lambda: (self.say(self.t('traymissing')), False)[1])

    def tray_target(self, mode, selector):
        self.window.present()
        self.invoke(['set', mode, selector], confirm=True)

    def update_tray_menu(self):
        menu = Gtk.Menu()
        for key, callback in [('show', lambda *_: self.present_window()),
                              ('cancel', lambda *_: (self.window.present(), self.invoke(['cancel']))),
                              ('status', lambda *_: (self.window.present(), self.invoke(['status'])))]:
            item = Gtk.MenuItem(label=self.t(key)); item.connect('activate', callback)
            if key in ('cancel','status'):
                item.set_sensitive(self.restart_available)
            menu.append(item)
        for mode in ('once', 'permanent'):
            parent = Gtk.MenuItem(label=self.t(mode))
            choices = Gtk.Menu()
            for entry in self.current_entries:
                item = Gtk.MenuItem(label=entry['title'])
                item.connect('activate', lambda _, m=mode, s=entry['selector']: self.tray_target(m, s))
                choices.append(item)
            parent.set_submenu(choices); parent.set_sensitive(bool(self.current_entries)); menu.append(parent)
        item = Gtk.MenuItem(label=self.t('quit')); item.connect('activate', lambda *_: self.request_quit()); menu.append(item)
        menu.show_all(); self.indicator.set_menu(menu)

    def present_window(self):
        self.window.present()
        if not self.current_entries and not self.busy:
            self.refresh()

    def request_quit(self):
        if self.busy:
            self.window.present()
            return
        self.authority.close()
        self.quit()

    def do_shutdown(self):
        self.authority.close()
        Gtk.Application.do_shutdown(self)

    def on_close(self, *_):
        if self.busy:
            return True
        self.authority.close()
        if self.indicator:
            self.window.hide(); return True
        self.quit(); return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tray', action='store_true')
    parser.add_argument('--lang', choices=['en', 'zh'], default='zh' if os.environ.get('LANG','').startswith('zh') else 'en')
    args = parser.parse_args()
    sys.exit(Manager(args.lang, args.tray).run([sys.argv[0]]))
