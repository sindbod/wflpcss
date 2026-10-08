"""Randomised, token-captioned training frames for the [PROD_mesh] / [PROD_lace] / [PROD_holo] LoRA.

    python generate_dataset.py -- <out_dir> [--count 200] [--seed 1] [--res 512 640] [--samples 48]

Per frame: skin tone (continuous between the fair, medium-olive and deep anchors), lighting rig (the four
scenarios, rotated and scaled), camera (mostly front to three-quarter, some side views and close-ups),
holographic model (diffraction foil, glitter foil, thin film over metal) and the net's tension.
Writes, in kohya / diffusers layout:
    images/00000.png      render (Khronos PBR Neutral view transform)
    images/00000.txt      short caption: the three tokens plus the conditions (lighting, view, skin tone),
                          inside CLIP's 77-token window; the physics wording belongs in inference prompts
    masks/00000.png       token mask: R [PROD_mesh], G [PROD_lace], B [PROD_holo], A body
    labels.jsonl          full scene description per frame (camera matrices in the three.js convention)
Frames already on disk are skipped, so the job resumes.
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'comfyui'))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import sheer_scene as ss  # noqa: E402
from comfyui_sheer_vton import prompts  # noqa: E402

# Blender (X, Y, Z) -> three.js (x, y, z) = (X, Z, -Y)
B2T = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
ANCHORS = ('fair', 'medium', 'deep')
MST = (5, 6, 8)  # nearest Monk Skin Tone of the three anchors (tools/mst_check.py)


def skin_at(s):
    """Albedo for a continuous tone s in [0, 2] (0 fair, 1 medium olive, 2 deep), log-linear between anchors."""
    i = min(int(s), 1)
    f = s - i
    a = np.log(np.array(ss.SKINS[ANCHORS[i]]['albedo']))
    b = np.log(np.array(ss.SKINS[ANCHORS[i + 1]]['albedo']))
    return tuple(np.exp(a * (1 - f) + b * f)), ANCHORS[int(round(s))], int(round(np.interp(s, [0, 1, 2], MST)))


def vary_rig(sc, rng):
    """Rotate the rig's lights (not the flash, which follows the camera) and scale their power."""
    rot = math.radians(rng.uniform(-25, 25))
    gain = rng.uniform(0.75, 1.3)
    R = Matrix.Rotation(rot, 4, 'Z')
    tgt = Vector((0, 0, 0.16))
    for ob in [o for o in bpy.data.objects if o.type == 'LIGHT' and o.name != 'flash']:
        ob.location = tgt + (R @ (ob.location - tgt))
        ob.rotation_euler = (tgt - ob.location).to_track_quat('-Z', 'Y').to_euler()
        ob.data.energy *= gain
    fl = bpy.data.objects.get('flash')
    if fl:
        fl.data.energy *= gain
    return math.degrees(rot), gain


def camera_labels(sc, w, h):
    bpy.context.view_layer.update()
    world_t = B2T @ sc.cam.matrix_world
    fy = 0.5 * h / math.tan(sc.cam.data.angle_y / 2) if sc.cam.data.sensor_fit == 'VERTICAL' else 0.5 * h / math.tan(sc.cam.data.angle / 2)
    return dict(camera_to_world=[list(r) for r in world_t], world_to_camera=[list(r) for r in world_t.inverted()],
                intrinsics_px=dict(fx=fy, fy=fy, cx=w / 2, cy=h / 2))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = argv[0]
    count, seed, res, samples = 200, 1, (512, 640), 48
    if '--count' in argv:
        count = int(argv[argv.index('--count') + 1])
    if '--seed' in argv:
        seed = int(argv[argv.index('--seed') + 1])
    if '--res' in argv:
        i = argv.index('--res')
        res = (int(argv[i + 1]), int(argv[i + 2]))
    if '--samples' in argv:
        samples = int(argv[argv.index('--samples') + 1])
    for d in ('images', 'masks'):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    rng = random.Random(seed)
    sc = ss.SheerScene(res=res, samples=samples)
    labels = open(os.path.join(out, 'labels.jsonl'), 'a')
    for i in range(count):
        # draw every random number even for frames on disk, so a resumed run continues the same sequence
        tone = rng.uniform(0, 2)
        rig = rng.choice(list(ss.SheerScene.RIGS))
        holo = rng.choices(['grating', 'grating_pixel', 'film'], [0.6, 0.25, 0.15])[0]
        strain = rng.uniform(0.0, 0.3)
        kind = rng.random()
        if kind < 0.15:
            az, el, dist, focal, view = rng.uniform(-50, 50), rng.uniform(-5, 10), rng.uniform(0.28, 0.5), 100.0, 'closeup'
            tgt = sc.surface_target(rng.uniform(-0.45, 0.45), rng.uniform(0.02, 0.28))
        else:
            az = rng.uniform(70, 95) * rng.choice([-1, 1]) if kind > 0.85 else rng.uniform(-60, 60)
            el, dist, focal = rng.uniform(-8, 12), rng.uniform(1.05, 1.6), rng.uniform(70, 100)
            view = 'side' if abs(az) >= 70 else ('front' if abs(az) < 20 else 'three_quarter')
            tgt = (0.0, 0.0, rng.uniform(0.12, 0.2))
        name = f'{i:05d}'
        img = os.path.join(out, 'images', name + '.png')
        if os.path.exists(img):
            continue
        albedo, anchor, mst = skin_at(tone)
        sc.set_skin(anchor)
        sc.skin_rgb.outputs[0].default_value = (*albedo, 1)
        sc.set_holo(holo)
        sc.set_strain(strain)
        sc.set_rig(rig)
        sc.set_camera(az, el, dist, focal, tgt)
        sc.view = view
        state = random.Random(seed * 100003 + i)
        rot, gain = vary_rig(sc, state)
        sc.render(img)
        sc.render_masks(os.path.join(out, 'masks', name + '.png'))
        meta = sc.describe()
        meta['skin'].update(albedo_linear=[round(float(a), 4) for a in albedo], tone_param=round(tone, 3),
                            monk_skin_tone_approx=mst)
        meta['rig'].update(rotation_deg=round(rot, 1), power_gain=round(gain, 3))
        cap = prompts.training_caption(meta, style='short')
        open(os.path.join(out, 'images', name + '.txt'), 'w').write(cap + '\n')
        rec = dict(file=f'images/{name}.png', mask=f'masks/{name}.png', caption=cap,
                   caption_long=prompts.training_caption(meta), **meta,
                   camera=camera_labels(sc, *res))
        labels.write(json.dumps(rec) + '\n')
        labels.flush()
        print(f'{name} {anchor} {rig} {view} {holo}', flush=True)
    sc.set_strain(ss.WAIST_STRAIN)


if __name__ == '__main__':
    main()
