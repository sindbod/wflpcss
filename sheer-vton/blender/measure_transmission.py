"""How much skin light gets through the net, with the yarn's own light removed.

    python measure_transmission.py -- <out.json> [--res 240 300] [--samples 128]

The net is made black (it absorbs, reflects and transmits nothing) so the front panel shows only skin light
that passed it. The ratio to the bare skin (rendered without the garment) is the net's effective
transmission for that skin under that light. Compared with the net's open fraction t seen straight on:
  t     the light reaching each visible patch of skin came in through the same opening the camera looks
        through (light from the lens, skin that does not scatter internally)
  t^2   the way in and the way out cross the net at unrelated openings (light from elsewhere, or skin that
        carries light sideways under its surface)
Cases: on-camera flash and softboxes, skin with and without subsurface scattering, fair and deep.
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
    W, H, samples = 240, 300, 128
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
    tmp = os.path.join(os.path.dirname(os.path.abspath(out)), '_transmission.exr')
    # black net: the fabric branch of the mesh material becomes a zero emission
    nt = sc.mats['mesh'].node_tree
    mix = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeMixShader' and n.inputs['Fac'].links
           and n.inputs['Fac'].links[0].from_socket.name == 'Alpha'][0]
    black = nt.nodes.new('ShaderNodeEmission')
    black.inputs['Strength'].default_value = 0.0
    nt.links.new(black.outputs[0], mix.inputs[2])
    garment = [n for k in ('lace', 'holo') for n in sc.tokens()[k]]
    for n in garment:  # only the net matters in the measured region
        sc.objects[n].hide_render = True
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

    def ratio():
        with_net = render()
        for n in sc.tokens()['mesh']:
            sc.objects[n].hide_render = True
        bare = render()
        for n in sc.tokens()['mesh']:
            sc.objects[n].hide_render = False
        lum = np.array([0.2126, 0.7152, 0.0722])
        return float((with_net[region] @ lum).mean() / max((bare[region] @ lum).mean(), 1e-9))

    p, w = ss.TULLE['Pitch'], ss.TULLE['BarWidth']
    t = ((p - w) / p) ** 2
    res = dict(open_fraction_face_on=round(t, 4), t_squared=round(t * t, 4), cases=[])
    for rig in ('flash', 'softbox'):
        sc.set_rig(rig)
        sc.set_view('front')
        for tone in ('fair', 'deep'):
            sc.set_skin(tone)
            for sss in (True, False):
                sc.set_sss(sss)
                r = dict(rig=rig, skin=tone, sss=sss, transmission=round(ratio(), 4))
                res['cases'].append(r)
                print(r, flush=True)
    sc.set_sss(True)
    json.dump(res, open(out, 'w'), indent=1)
    os.remove(tmp)


if __name__ == '__main__':
    main()
