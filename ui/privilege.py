"""A process-private authorization session. No sockets, passwords or global cache."""
import struct
from gi.repository import Gio, GLib

HELPER = '/usr/libexec/rust-boot-manager-helper'
MAX_REPLY = 4 * 1024 * 1024

class PrivilegeSession:
    def __init__(self):
        self.process = None
        self.generation = 0
        self.pending = None
        self.error_text = ''
        self.cancellable = None

    def close(self):
        process = self.process
        self.generation += 1
        self.process = None; self.pending = None
        if self.cancellable:
            self.cancellable.cancel(); self.cancellable = None
        if process:
            try:
                # EOF ends the helper after any current transaction completes.
                process.get_stdin_pipe().close(None)
            except GLib.Error:
                pass

    def _fail(self, generation, message):
        if generation != self.generation:
            return
        callback = self.pending
        self.close()
        if callback:
            callback('Error / 错误: ' + message, False)

    def _start(self):
        self.generation += 1
        generation = self.generation
        self.error_text = ''
        self.cancellable = Gio.Cancellable()
        self.process = Gio.Subprocess.new(
            ['/usr/bin/pkexec', HELPER, '--session'],
            Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        def stderr_ready(stream, result):
            try:
                data = stream.read_bytes_finish(result).get_data()
                if generation != self.generation or not data:
                    return
                self.error_text = (self.error_text + data.decode('utf-8', errors='replace'))[-65536:]
                stream.read_bytes_async(4096, GLib.PRIORITY_DEFAULT, self.cancellable, stderr_ready)
            except GLib.Error:
                pass
        self.process.get_stderr_pipe().read_bytes_async(4096, GLib.PRIORITY_DEFAULT, self.cancellable, stderr_ready)
        def exited(process, result):
            try:
                process.wait_finish(result)
            except GLib.Error:
                pass
            if generation == self.generation:
                self._fail(generation, self.error_text.strip() or 'Authorization session closed / 授权会话已关闭')
        self.process.wait_async(None, exited)

    def _read_exact(self, generation, count, callback, data=b''):
        if generation != self.generation:
            return
        if len(data) == count:
            callback(data); return
        def read_ready(stream, result):
            if generation != self.generation:
                return
            try:
                chunk = stream.read_bytes_finish(result).get_data()
                if not chunk:
                    self._fail(generation, self.error_text.strip() or 'Authorization ended / 授权已结束'); return
                self._read_exact(generation, count, callback, data + chunk)
            except GLib.Error as error:
                self._fail(generation, str(error))
        self.process.get_stdout_pipe().read_bytes_async(count - len(data), GLib.PRIORITY_DEFAULT, self.cancellable, read_ready)

    def call(self, args, callback):
        if self.pending:
            callback('Error / 错误: Authorization session is busy / 授权会话正在处理请求', False); return
        try:
            encoded = [arg.encode('utf-8') for arg in args]
            if not 1 <= len(encoded) <= 3 or any(len(arg) > 4096 for arg in encoded):
                raise ValueError('Invalid session request')
            if self.process is None:
                self._start()
            generation = self.generation
            self.pending = callback
            frame = struct.pack('>I', len(encoded)) + b''.join(struct.pack('>I', len(arg)) + arg for arg in encoded)
            def written(stream, result):
                if generation != self.generation:
                    return
                try:
                    stream.write_all_finish(result)
                except GLib.Error as error:
                    self._fail(generation, str(error)); return
                def header_ready(header):
                    status, length = header[0], struct.unpack('>I', header[1:])[0]
                    if status not in (0, 1) or length > MAX_REPLY:
                        self._fail(generation, 'Invalid session response'); return
                    def body_ready(body):
                        try:
                            text = body.decode('utf-8')
                        except UnicodeError:
                            self._fail(generation, 'Invalid session UTF-8'); return
                        pending = self.pending; self.pending = None
                        if pending:
                            pending(text if status == 0 else 'Error / 错误: ' + text, status == 0)
                    self._read_exact(generation, length, body_ready)
                self._read_exact(generation, 5, header_ready)
            self.process.get_stdin_pipe().write_all_async(frame, GLib.PRIORITY_DEFAULT, self.cancellable, written)
        except (GLib.Error, ValueError, UnicodeError) as error:
            if self.pending:
                self._fail(self.generation, str(error))
            else:
                self.close(); callback('Error / 错误: ' + str(error), False)
