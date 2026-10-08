"""Queue the refiner graph on a running ComfyUI server (standard library only).

    python run_workflow.py --server http://127.0.0.1:8188 --pass1 out/vton.png --mask out/token_mask.png \\
        --scenario softbox --skin deep [--holo-model grating] [--seed 7] [--denoise 0.3] [--wait]

Uploads both images (POST /upload/image), fills them and the options into the API graph from
build_workflow.py, posts it to /prompt and, with --wait, polls /history until the job finishes and
prints the saved file names and the see-through QA report.
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_workflow  # noqa: E402


def _post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or '{}')


def upload(server, path, kind='input'):
    boundary = uuid.uuid4().hex
    name = os.path.basename(path)
    ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    body = b''.join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f'Content-Type: {ctype}\r\n\r\n'.encode(), open(path, 'rb').read(), b'\r\n',
        f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\n{kind}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'.encode(),
        f'--{boundary}--\r\n'.encode(),
    ])
    res = _post(f'{server}/upload/image', body, {'Content-Type': f'multipart/form-data; boundary={boundary}'})
    return res.get('name', name)


def queue(server, graph, client_id):
    data = json.dumps({'prompt': graph, 'client_id': client_id}).encode()
    return _post(f'{server}/prompt', data, {'Content-Type': 'application/json'})


def wait(server, prompt_id, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with urllib.request.urlopen(f'{server}/history/{prompt_id}', timeout=30) as r:
            hist = json.loads(r.read().decode() or '{}')
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(2)
    raise TimeoutError(prompt_id)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', default='http://127.0.0.1:8188')
    ap.add_argument('--pass1', required=True, help='pass-1 VTON output image')
    ap.add_argument('--mask', required=True, help='token mask PNG: R mesh, G lace, B holo, alpha body')
    for k in ('scenario', 'skin', 'holo_model', 'view', 'checkpoint', 'token_lora', 'canny_controlnet', 'tile_controlnet'):
        ap.add_argument('--' + k.replace('_', '-'), default=build_workflow.DEFAULTS[k])
    for k in ('seed', 'steps'):
        ap.add_argument('--' + k, type=int, default=build_workflow.DEFAULTS[k])
    for k in ('denoise', 'cfg', 'canny_strength', 'tile_strength', 'lora_strength', 'open_fraction'):
        ap.add_argument('--' + k.replace('_', '-'), type=float, default=build_workflow.DEFAULTS[k])
    ap.add_argument('--wait', action='store_true')
    a = ap.parse_args(argv)
    server = a.server.rstrip('/')
    params = {k: v for k, v in vars(a).items() if k in build_workflow.DEFAULTS}
    params['pass1_image'] = upload(server, a.pass1)
    params['token_mask'] = upload(server, a.mask)
    graph = build_workflow.graph(params)
    client_id = uuid.uuid4().hex
    res = queue(server, graph, client_id)
    pid = res.get('prompt_id')
    print('queued', pid)
    if a.wait and pid:
        h = wait(server, pid)
        for nid, out in h.get('outputs', {}).items():
            for img in out.get('images', []):
                print('image', img.get('subfolder', ''), img.get('filename'))
            for txt in out.get('text', []):
                print('qa', txt)
    return pid


if __name__ == '__main__':
    main()
