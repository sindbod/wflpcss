"""Re-renders the rim-light holo probes from the side, where the rim lights catch the waist band.

    python render_holo_rim.py -- <frames_dir> [--res 640 800] [--samples 80]

From the front, rim light leaves the band's face dark and its highlights sit at the silhouette, outside a
close-up's frame. This camera looks at the band's right side (100 degrees round from the front), where the
right-hand strip light reflects in it. Frames replace holo/<kind>_rim.png; manifest.json is updated.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheer_scene as ss  # noqa: E402

VIEW = (0.52, 0.159, 100.0, 2.0, 0.42, 85.0)  # frac, z, azimuth, elevation, distance, focal


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = argv[0]
    res, samples = (640, 800), 80
    if '--res' in argv:
        i = argv.index('--res')
        res = (int(argv[i + 1]), int(argv[i + 2]))
    if '--samples' in argv:
        samples = int(argv[argv.index('--samples') + 1])
    mpath = os.path.join(out, 'manifest.json')
    manifest = json.load(open(mpath))
    sc = ss.SheerScene(res=res, samples=samples)
    sc.set_skin('fair')
    sc.set_rig('rim')
    frac, z, az, el, dist, focal = VIEW
    for kind in ('grating', 'grating_pixel', 'film'):
        sc.set_holo(kind)
        sc.set_camera(az, el, dist, focal, sc.surface_target(frac, z))
        sc.view = 'band_side'
        rel = f'holo/{kind}_rim.png'
        sc.render(os.path.join(out, rel))
        manifest.setdefault('holo', {})[f'{kind}_rim'] = dict(file=rel, **sc.describe())
        print('rendered', rel, flush=True)
    json.dump(manifest, open(mpath, 'w'), indent=1)


if __name__ == '__main__':
    main()
