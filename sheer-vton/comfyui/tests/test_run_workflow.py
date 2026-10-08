"""run_workflow.py against a mock ComfyUI server (upload, queue, history)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import run_workflow


class Mock(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        Mock.seen.append((self.path, self.headers['Content-Type'], body))
        if self.path == '/upload/image':
            name = body.split(b'filename="')[1].split(b'"')[0].decode()
            self._send({'name': 'up_' + name, 'subfolder': '', 'type': 'input'})
        else:
            self._send({'prompt_id': 'p1', 'number': 0})

    def do_GET(self):
        self._send({'p1': {'outputs': {'20': {'images': [{'filename': 'refined_00001_.png', 'subfolder': 'sheer_vton'}]},
                                       '24': {'text': ['green see-through ratio 0.31']}}}})


def test_uploads_queues_and_waits(tmp_path, capsys):
    srv = HTTPServer(('127.0.0.1', 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    p1, mk = tmp_path / 'vton.png', tmp_path / 'mask.png'
    p1.write_bytes(b'\x89PNG fake')
    mk.write_bytes(b'\x89PNG fake2')
    pid = run_workflow.main(['--server', f'http://127.0.0.1:{srv.server_port}', '--pass1', str(p1), '--mask', str(mk),
                             '--scenario', 'rim', '--skin', 'deep', '--denoise', '0.3', '--wait'])
    srv.shutdown()
    assert pid == 'p1'
    paths = [s[0] for s in Mock.seen]
    assert paths == ['/upload/image', '/upload/image', '/prompt']
    graph = json.loads(Mock.seen[2][2])['prompt']
    assert graph['1']['inputs']['image'] == 'up_vton.png' and graph['2']['inputs']['image'] == 'up_mask.png'
    assert graph['4']['inputs']['scenario'] == 'rim' and graph['4']['inputs']['skin'] == 'deep'
    assert graph['16']['inputs']['denoise'] == 0.3
    out = capsys.readouterr().out
    assert 'refined_00001_.png' in out and 'see-through ratio' in out
