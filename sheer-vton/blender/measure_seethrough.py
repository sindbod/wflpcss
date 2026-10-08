"""How much skin shows through the mesh, measured per pixel in linear light.

    python measure_seethrough.py -- <out.json> [--res 240 300] [--samples 96]

Each case renders the front view twice in scene-linear light (no tone mapping, no denoising): once with the
garment and once without it. Inside the central part of the mesh panel the ratio of the two images is the
panel's see-through factor: skin light that survives the net plus the yarn's own light, relative to bare skin.
The green channel isolates the skin, because the burgundy yarn reflects and transmits almost no green.
Cases: three skin tones under the softbox and the flash; subsurface scattering off (opaque Lambertian skin)
for fair and deep; waist strain 0 / 25 / 40 %.
"""
import json
import os
import sys

import bpy
import bpy_extras
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheer_scene as ss  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    out = argv[0]
    W, H, samples = 240, 300, 96
    if '--res' in argv:
        i = argv.index('--res')
        W, H = int(argv[i + 1]), int(argv[i + 2])
    if '--samples' in argv:
        samples = int(argv[argv.index('--samples') + 1])
    sc = ss.SheerScene(res=(W, H), samples=samples)
    s = sc.scene
    s.view_settings.view_transform = 'Standard'
    s.render.image_settings.file_format = 'OPEN_EXR'
    s.render.image_settings.color_depth = '32'
    s.cycles.use_denoising = False
    s.cycles.use_adaptive_sampling = False
    tmp = os.path.join(os.path.dirname(os.path.abspath(out)), '_seethrough.exr')
    garment = [n for k in ('mesh', 'lace', 'holo') for n in sc.tokens()[k]]
    # region: central front mesh panel between the bands, away from channels and edges
    sc.set_view('front')

    def px(frac, z):
        p, _, _, _ = sc.torso.sample(frac, z)
        co = bpy_extras.object_utils.world_to_camera_view(s, sc.cam, Vector(p))
        return int((1 - co.y) * H), int(co.x * W)

    r0, _ = px(0.0, 0.135)
    r1, _ = px(0.0, 0.03)
    _, c0 = px(-0.16, 0.08)
    _, c1 = px(0.16, 0.08)
    region = (slice(min(r0, r1), max(r0, r1)), slice(c0, c1))

    def render():
        sc.render(tmp)
        img = bpy.data.images.load(tmp, check_existing=False)
        a = np.array(img.pixels[:], np.float32).reshape(H, W, 4)[::-1, :, :3]
        bpy.data.images.remove(img)
        return a

    def measure():
        with_g = render()
        for n in garment:
            sc.objects[n].hide_render = True
        bare = render()
        for n in garment:
            sc.objects[n].hide_render = False
        a, b = with_g[region].reshape(-1, 3), bare[region].reshape(-1, 3)
        ratio = a.mean(0) / np.maximum(b.mean(0), 1e-6)
        return dict(ratio_rgb=[round(float(x), 4) for x in ratio], mesh_rgb=[round(float(x), 4) for x in a.mean(0)],
                    bare_rgb=[round(float(x), 4) for x in b.mean(0)])

    p, w = ss.TULLE['Pitch'], ss.TULLE['BarWidth']
    t = ((p - w) / p) ** 2
    res = dict(open_fraction_face_on=round(t, 4), t_squared=round(t * t, 4), region_px=[region[0].start, region[0].stop,
               region[1].start, region[1].stop], cases=[])
    for rig in ('softbox', 'flash'):
        sc.set_rig(rig)
        sc.set_view('front')
        for tone in ('fair', 'medium', 'deep'):
            sc.set_skin(tone)
            r = dict(rig=rig, skin=tone, sss=True, strain=sc.strain, **measure())
            res['cases'].append(r)
            print(r, flush=True)
    sc.set_rig('softbox')
    sc.set_view('front')
    for tone in ('fair', 'deep'):
        sc.set_skin(tone)
        sc.set_sss(False)
        r = dict(rig='softbox', skin=tone, sss=False, strain=sc.strain, **measure())
        res['cases'].append(r)
        print(r, flush=True)
        sc.set_sss(True)
    sc.set_skin('fair')
    for strain in (0.0, 0.25, 0.40):
        sc.set_strain(strain)
        r = dict(rig='softbox', skin='fair', sss=True, strain=strain, **measure())
        res['cases'].append(r)
        print(r, flush=True)
    sc.set_strain(ss.WAIST_STRAIN)
    json.dump(res, open(out, 'w'), indent=1)
    os.remove(tmp)


if __name__ == '__main__':
    main()
