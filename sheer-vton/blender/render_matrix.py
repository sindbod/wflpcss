"""Renders the ground-truth frame sets for the sheer VTON study (Cycles, CPU).

    python render_matrix.py -- <out_dir> [set ...] [--res 640 800] [--samples 80]

Sets:
  matrix  3 skin tones x 4 lighting rigs x 3 views (front, three-quarter, side)
  macro   3 skin tones x 4 rigs, close-up where mesh, satin channel, lace and the waist band meet
  shadow  on-camera flash vs off-axis strobe at the lace border (does the lace cast visible shadows?)
  strain  the net at 0 / 12 / 25 / 40 % waist strain (tension opens the net)
  holo    waist band close-up: grating, pixelated grating and thin film over metal, under flash and rim
  sss     mesh over skin with and without subsurface scattering (t vs t^2 attenuation)
  masks   token masks (R mesh, G lace, B holo, A body) for every camera used above
Frames already on disk are skipped; manifest.json records the scene description of every frame.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheer_scene as ss  # noqa: E402

SKINS = ('fair', 'medium', 'deep')
RIGS = ('flash', 'strobe', 'softbox', 'rim')
VIEWS = ('front', 'three_quarter', 'side')
# bottom band, the left satin channel's foot, mesh edge and bare skin below, lit by the strobe at 45 deg left
SHADOW_VIEW = (-0.28, 0.012, -30.0, 6.0, 0.16, 100.0)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    res, samples = (640, 800), 80
    if '--res' in args:
        i = args.index('--res')
        res = (int(args[i + 1]), int(args[i + 2]))
        del args[i:i + 3]
    if '--samples' in args:
        i = args.index('--samples')
        samples = int(args[i + 1])
        del args[i:i + 2]
    out = args[0]
    sets = args[1:] or ['matrix', 'macro', 'shadow', 'strain', 'holo', 'sss', 'masks']
    os.makedirs(out, exist_ok=True)
    mpath = os.path.join(out, 'manifest.json')
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    sc = ss.SheerScene(res=res, samples=samples)
    cams = {}

    def frame(set_name, name, extra=None):
        rel = f'{set_name}/{name}.png'
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            t = time.time()
            sc.render(path)
            print(f'[{set_name}] {name} {time.time() - t:.0f}s', flush=True)
        manifest.setdefault(set_name, {})[name] = dict(file=rel, **sc.describe(), **(extra or {}))
        cams[sc.view] = dict(sc.cam_params)
        json.dump(manifest, open(mpath, 'w'), indent=1)

    def probe_view(name, frac, z, az, el, dist, focal):
        sc.set_camera(az, el, dist, focal, sc.surface_target(frac, z))
        sc.view = name

    if 'matrix' in sets:
        for view in VIEWS:
            sc.set_view(view)
            for skin in SKINS:
                sc.set_skin(skin)
                for rig in RIGS:
                    sc.set_rig(rig)
                    sc.set_view(view)
                    frame('matrix', f'{skin}_{rig}_{view}')
    if 'macro' in sets:
        for skin in SKINS:
            sc.set_skin(skin)
            for rig in RIGS:
                sc.set_rig(rig)
                sc.set_view('macro')
                frame('macro', f'{skin}_{rig}')
    if 'shadow' in sets:
        for skin in ('fair', 'deep'):
            sc.set_skin(skin)
            for rig in ('flash', 'strobe'):
                sc.set_rig(rig)
                probe_view('shadow', *SHADOW_VIEW)
                frame('shadow', f'{skin}_{rig}')
    if 'strain' in sets:
        sc.set_skin('fair')
        sc.set_rig('softbox')
        for strain in (0.0, 0.12, 0.25, 0.40):
            sc.set_strain(strain)
            probe_view('strain', 0.0, 0.085, 0.0, 0.0, 0.42, 85.0)
            frame('strain', f'strain_{int(round(strain * 100)):02d}', dict(waist_strain=strain))
        sc.set_strain(ss.WAIST_STRAIN)
    if 'holo' in sets:
        sc.set_skin('fair')
        for kind in ('grating', 'grating_pixel', 'film'):
            sc.set_holo(kind)
            for rig in ('flash', 'rim'):
                sc.set_rig(rig)
                probe_view('band', 0.0, 0.159, 0.0, 2.0, 0.42, 85.0)
                frame('holo', f'{kind}_{rig}')
        sc.set_holo('grating')
    if 'sss' in sets:
        sc.set_rig('softbox')
        for skin in ('fair', 'deep'):
            sc.set_skin(skin)
            for on in (True, False):
                sc.set_sss(on)
                probe_view('sss', 0.0, 0.10, 0.0, 0.0, 0.40, 85.0)
                frame('sss', f'{skin}_{"sss" if on else "lambert"}')
        sc.set_sss(True)
    if 'masks' in sets:
        views = dict((v, None) for v in VIEWS + ('macro',))
        probes = {'shadow': SHADOW_VIEW,
                  'strain': (0.0, 0.085, 0.0, 0.0, 0.42, 85.0), 'band': (0.0, 0.159, 0.0, 2.0, 0.42, 85.0),
                  'sss': (0.0, 0.10, 0.0, 0.0, 0.40, 85.0)}
        for v in views:
            sc.set_view(v)
            p = os.path.join(out, 'masks', f'{v}.png')
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if not os.path.exists(p):
                sc.render_masks(p)
                print(f'[masks] {v}', flush=True)
            manifest.setdefault('masks', {})[v] = dict(file=f'masks/{v}.png', camera=dict(sc.cam_params))
        for v, a in probes.items():
            probe_view(v, *a)
            p = os.path.join(out, 'masks', f'{v}.png')
            if not os.path.exists(p):
                sc.render_masks(p)
                print(f'[masks] {v}', flush=True)
            manifest.setdefault('masks', {})[v] = dict(file=f'masks/{v}.png', camera=dict(sc.cam_params))
        json.dump(manifest, open(mpath, 'w'), indent=1)
    print('done', flush=True)


if __name__ == '__main__':
    main()
