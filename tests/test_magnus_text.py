import ctypes
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def image_bytes():
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00\xff')) + chunk(b'IEND', b''))


class MagnusTextTests(unittest.TestCase):
    def test_actual_preview_control_treats_markup_literally_without_network_or_file_reads(self):
        runner = next((str(path) for path in (Path('/usr/lib/qt6/bin/qmltestrunner'),
                                            Path('/usr/lib/x86_64-linux-gnu/qt6/bin/qmltestrunner')) if path.is_file()),
                      shutil.which('qmltestrunner'))
        if not runner:
            self.fail('Qt 6 qmltestrunner is required for the Magnus resource-boundary regression')
        # Watch only synthetic image files. No tenant files or credentials are read.
        libc = ctypes.CDLL(None, use_errno=True)
        descriptor = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        self.assertGreaterEqual(descriptor, 0)
        self.addCleanup(os.close, descriptor)
        seen = []
        png = image_bytes()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.end_headers()
                self.wfile.write(png)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='rock-arch-magnus-text-') as temporary:
                folder = Path(temporary)
                # Use the production control itself, not a copied TextArea approximation.
                control = ROOT / 'plugin/oneall.rock-arch/RockArchPlainTextArea.qml'
                shutil.copyfile(control, folder / control.name)
                panel = (ROOT / 'plugin/oneall.rock-arch/RockArchMagnusPanel.qml').read_text()
                self.assertIn('RockArchPlainTextArea {', panel)
                plain_file = folder / 'plain.png'
                rich_file = folder / 'rich.png'
                plain_file.write_bytes(png)
                rich_file.write_bytes(png)
                plain_watch = libc.inotify_add_watch(descriptor, os.fsencode(plain_file), 0x20)
                rich_watch = libc.inotify_add_watch(descriptor, os.fsencode(rich_file), 0x20)
                self.assertGreaterEqual(plain_watch, 0)
                self.assertGreaterEqual(rich_watch, 0)
                base = f'http://127.0.0.1:{server.server_port}'
                plain = '<b>literal</b><img src="' + base + '/plain.png"><img src="' + plain_file.as_uri() + '">'
                rich = '<b>control</b><img src="' + base + '/rich.png"><img src="' + rich_file.as_uri() + '">'
                qml = '''import QtQuick
import QtQuick.Controls as QQC
import QtTest
TestCase {
  name: "MagnusResourceBoundary"
  when: windowShown
  width: 500; height: 300
  property string plainPayload: PLAIN_PAYLOAD
  property string richPayload: RICH_PAYLOAD
  RockArchPlainTextArea { id: preview; width: 500; height: 100 }
  QQC.TextArea { id: control; y: 120; width: 500; height: 100; textFormat: TextEdit.AutoText }
  function test_plaintext_is_literal() {
    compare(preview.textFormat, TextEdit.PlainText)
    preview.text = plainPayload
    wait(300)
    preview.selectAll()
    compare(preview.selectedText, plainPayload)
    compare(preview.length, plainPayload.length)
  }
  function test_richtext_positive_control_loads_resources() {
    control.text = richPayload
    wait(700)
    control.selectAll()
    verify(control.selectedText !== richPayload)
  }
}
'''.replace('PLAIN_PAYLOAD', json.dumps(plain)).replace('RICH_PAYLOAD', json.dumps(rich))
                (folder / 'tst_Preview.qml').write_text(qml)
                env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
                       'QT_QUICK_CONTROLS_STYLE': 'Basic'}
                result = subprocess.run([runner, '-input', str(folder / 'tst_Preview.qml')],
                                        capture_output=True, text=True, env=env, timeout=20, check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                try:
                    events = os.read(descriptor, 65536)
                except BlockingIOError:
                    events = b''
                watched = set()
                while events:
                    watch, _mask, _cookie, length = struct.unpack('iIII', events[:16])
                    watched.add(watch)
                    events = events[16 + length:]
                self.assertNotIn('/plain.png', seen)
                self.assertNotIn(plain_watch, watched)
                # Positive controls prove both the HTTP and file-read observers work.
                self.assertIn('/rich.png', seen)
                self.assertIn(rich_watch, watched)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
