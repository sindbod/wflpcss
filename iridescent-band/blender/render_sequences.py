"""Renders the pre-computed frame sets shown for approach 5 (Cycles).

    python render_sequences.py -- <assets_dir> <out_dir> [set ...]

Sets:
  grid    24 camera azimuths x 6 light-rig rotations (studio), the scrubbable "light field"
  envs    6 lighting environments x 12 camera azimuths
  macro   close-up, light rig rotating in 15 degree steps
  stretch knit strain 0..12 % (film thins, pattern widens)
Frames already on disk are skipped, so the job can be resumed. A manifest.json describes every frame.
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from band_scene import BandScene  # noqa: E402

ENVS = {
    'studio': dict(file='studio.hdr', key=dict(lux=0.35, radius=0.1, az=-16, el=14)),
    'darkroom': dict(file='darkroom.hdr', key=dict(lux=1.3, radius=0.004, az=-14, el=-12)),
    'neon': dict(file='neon.hdr', key=None),
    'sunset': dict(file='venice_sunset_1k.hdr', key=None),
    'overcast': dict(file='pedestrian_overpass_1k.hdr', key=None),
    'sun': dict(file='quarry_01_1k.hdr', key=None),
}


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    assets, out = args[0], args[1]
    sets = args[2:] or ['grid', 'envs', 'macro', 'stretch']
    os.makedirs(out, exist_ok=True)
    manifest_path = os.path.join(out, 'manifest.json')
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    res = (800, 500)
    sc = BandScene(assets, displacement=True, res=res, samples=40)
    meta = sc.meta

    def light(env_id, rot):
        e = ENVS[env_id]
        sc.set_environment(e['file'], rot)
        k = e['key']
        if k:
            sc.set_key(k['az'] + rot, k['el'], k['lux'], k['radius'], True)
        else:
            sc.set_key(0, 30, 0, 0.1, False)

    def frame(set_name, name, info):
        rel = f'{set_name}/{name}.png'
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            t = time.time()
            sc.render(path)
            print(f'[{set_name}] {name} {time.time() - t:.1f}s', flush=True)
        manifest.setdefault(set_name, {})[name] = dict(file=rel, **info)
        json.dump(manifest, open(manifest_path, 'w'), indent=1)

    cam = meta['camera']
    if 'grid' in sets:
        for li, rot in enumerate(range(0, 360, 60)):
            light('studio', rot)
            for ci, az in enumerate(range(0, 360, 15)):
                sc.set_camera(az, 6, 0.5)
                frame('grid', f'c{ci:02d}_l{li}', dict(camera_azimuth=az, camera_elevation=6, distance=0.5, light_rotation=rot, environment='studio'))
    if 'envs' in sets:
        for env_id in ENVS:
            light(env_id, 0)
            for ci, az in enumerate(range(0, 360, 30)):
                sc.set_camera(az, 6, 0.5)
                frame('envs', f'{env_id}_c{ci:02d}', dict(camera_azimuth=az, camera_elevation=6, distance=0.5, light_rotation=0, environment=env_id))
    if 'macro' in sets:
        # distances are from the band's centre axis; the torso radius is 0.106-0.137 m, so 0.17 m keeps
        # the camera about 6 cm off the band
        sc.set_camera(cam['azimuth'], 3, 0.17)
        for li, rot in enumerate(range(0, 360, 15)):
            light('studio', rot)
            frame('macro', f'l{li:02d}', dict(camera_azimuth=cam['azimuth'], camera_elevation=3, distance=0.17, light_rotation=rot, environment='studio'))
    if 'stretch' in sets:
        light('studio', 0)
        sc.set_camera(cam['azimuth'], 5, 0.3)
        for i, strain in enumerate([0, 0.03, 0.06, 0.09, 0.12]):
            sc.stretch(strain)
            frame('stretch', f's{i}', dict(strain=strain, camera_azimuth=cam['azimuth'], camera_elevation=5, distance=0.3, environment='studio'))
        sc.stretch(0)
    print('done', flush=True)


if __name__ == '__main__':
    main()
