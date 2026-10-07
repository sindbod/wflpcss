"""Domain-randomised training data for the iridescent band (Cycles).

    python generate_dataset.py -- <assets_dir> <out_dir> [--count 100] [--seed 1]
                                  [--res 768 768] [--samples 48] [--masks]

Each sample randomises camera (azimuth, elevation, distance, field of view), lighting environment
and its rotation, the key light (on/off, direction, intensity, size), knit strain and the film
thickness (±4 %). Output:
    images/00000.png         beauty render (Khronos PBR Neutral view transform)
    masks/00000.png          band mask (white = band), when --masks is given
    labels.jsonl             one JSON object per frame (same schema as the browser exports)
Camera matrices are given in the three.js convention (Y up, metres) so labels from the browser
approaches and from Cycles are interchangeable.
"""
import argparse
import json
import math
import os
import random
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from band_scene import BandScene, spherical  # noqa: E402

ENVS = [
    ('studio.hdr', dict(p_key=0.9)),
    ('darkroom.hdr', dict(p_key=1.0)),
    ('neon.hdr', dict(p_key=0.2)),
    ('venice_sunset_1k.hdr', dict(p_key=0.2)),
    ('pedestrian_overpass_1k.hdr', dict(p_key=0.3)),
    ('quarry_01_1k.hdr', dict(p_key=0.1)),
]

# Blender (X, Y, Z) -> three.js (x, y, z) = (X, Z, -Y)
B2T = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))


def camera_labels(sc, width, height):
    cam = sc.cam
    bpy.context.view_layer.update()
    world_b = cam.matrix_world.copy()
    world_t = B2T @ world_b @ B2T.inverted()
    fov_y = cam.data.angle
    fy = 0.5 * height / math.tan(fov_y / 2)
    return dict(
        camera_to_world=[list(r) for r in world_t],
        world_to_camera=[list(r) for r in world_t.inverted()],
        fov_y_deg=math.degrees(fov_y),
        intrinsics_px=dict(fx=fy, fy=fy, cx=width / 2, cy=height / 2),
    )


def set_mask_mode(sc, on):
    """Swap every material for flat emission so a 1-spp render gives a clean band mask."""
    if on:
        sc._saved = {o.name: list(o.data.materials) for o in (sc.band, sc.form, sc.floor)}
        white = bpy.data.materials.get('mask_white') or _emission('mask_white', 1.0)
        black = bpy.data.materials.get('mask_black') or _emission('mask_black', 0.0)
        for o, m in ((sc.band, white), (sc.form, black), (sc.floor, black)):
            o.data.materials.clear()
            o.data.materials.append(m)
        sc.scene.cycles.samples = 1
        sc.scene.cycles.use_denoising = False
        sc.scene.view_settings.view_transform = 'Standard'
        sc.backdrop.inputs['Color'].default_value = (0, 0, 0, 1)
    else:
        for o in (sc.band, sc.form, sc.floor):
            o.data.materials.clear()
            for m in sc._saved[o.name]:
                o.data.materials.append(m)
        sc.backdrop.inputs['Color'].default_value = (0.0420, 0.0420, 0.0412, 1.0)
        try:
            sc.scene.view_settings.view_transform = 'Khronos PBR Neutral'
        except TypeError:
            pass


def _emission(name, value):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (value, value, value, 1)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs['Emission'], out.inputs['Surface'])
    return m


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('assets')
    ap.add_argument('out')
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--res', type=int, nargs=2, default=(768, 768))
    ap.add_argument('--samples', type=int, default=48)
    ap.add_argument('--masks', action='store_true')
    a = ap.parse_args(argv)

    rng = random.Random(a.seed)
    os.makedirs(os.path.join(a.out, 'images'), exist_ok=True)
    if a.masks:
        os.makedirs(os.path.join(a.out, 'masks'), exist_ok=True)
    sc = BandScene(a.assets, displacement=True, res=tuple(a.res), samples=a.samples)
    base_d = sc.meta['film']['d']
    labels = open(os.path.join(a.out, 'labels.jsonl'), 'a')

    for i in range(a.count):
        name = f'{i:05d}'
        img_path = os.path.join(a.out, 'images', name + '.png')
        if os.path.exists(img_path):
            continue
        env_file, env_opts = rng.choice(ENVS)
        env_rot = rng.uniform(0, 360)
        sc.set_environment(env_file, env_rot, strength=rng.uniform(0.7, 1.3))
        key_on = rng.random() < env_opts['p_key']
        key = dict(azimuth_deg=rng.uniform(-180, 180), elevation_deg=rng.uniform(-5, 60),
                   illuminance=rng.uniform(0.2, 1.4), radius_m=math.exp(rng.uniform(math.log(0.003), math.log(0.15))))
        sc.set_key(key['azimuth_deg'], key['elevation_deg'], key['illuminance'], key['radius_m'], key_on)
        az, el = rng.uniform(0, 360), rng.uniform(-8, 32)
        dist = math.exp(rng.uniform(math.log(0.1), math.log(0.6)))
        fov = rng.uniform(18, 40)
        sc.set_camera(az, el, dist, fov)
        strain = rng.uniform(0, 0.10)
        sc.stretch(strain)
        d = base_d / (1 + 0.45 * strain) * rng.uniform(0.96, 1.04)
        sc.set_film(d=d)
        sc.render(img_path)
        if a.masks:
            set_mask_mode(sc, True)
            sc.render(os.path.join(a.out, 'masks', name + '.png'))
            set_mask_mode(sc, False)
            sc.scene.cycles.samples = a.samples
            sc.scene.cycles.use_denoising = True
        rec = dict(
            file=f'images/{name}.png',
            mask=f'masks/{name}.png' if a.masks else None,
            renderer='Blender Cycles (layered thin-film nodes, micro-displacement)',
            camera=dict(azimuth_deg=az, elevation_deg=el, distance_m=dist, **camera_labels(sc, *a.res)),
            lighting=dict(environment=env_file, environment_rotation_deg=env_rot, key_light=key if key_on else None),
            geometry=dict(shape='ring', strain=strain),
            material=dict(film_index=sc.meta['film']['n2'], substrate_index=sc.meta['film']['n3'], film_thickness_nm=d),
        )
        labels.write(json.dumps(rec) + '\n')
        labels.flush()
        print(f'{name} done', flush=True)


if __name__ == '__main__':
    main()
