"""Ground-truth Cycles scene for the sheer-mesh / lace / holo VTON study.

A dress-form torso section (waist, hips to lower ribs) with skin that scatters light below the surface
(random-walk subsurface, three tones), dressed in:
  [PROD_mesh]  micro-dot tulle as a real net: OSL coverage shader with yarn thickness and flocked dots,
               0.5 mm off the skin, stretched by the body (more open where the body is wider)
  [PROD_lace]  burgundy embroidered lace side panels and a scalloped lace border (texture maps from
               lace_maps.py over a finer tulle ground) plus satin boning channels
  [PROD_holo]  elastic tension bands: diffraction-grating foil (OSL lobes) or thin film over metal
Lighting rigs follow the briefing's scenarios: on-camera flash at dusk (A, as in the example photo), an
off-axis bare strobe (A', the light the briefing's shadow wording actually needs), large softboxes (B) and
rim/backlight (C).

Blender coordinates: Z up, the front of the body faces -Y, metres. Garment material coordinates (UVs)
are millimetres.

    import sheer_scene as ss
    sc = ss.SheerScene(res=(800, 1000), samples=128)
    sc.set_skin('deep'); sc.set_rig('flash'); sc.set_view('three_quarter'); sc.render('out.png')
"""
import glob
import math
import os
import sys

# pip bpy keeps oslquery (needed by OSL script nodes) in the bundled interpreter's site-packages
sys.path += glob.glob(os.path.join(sys.prefix, 'lib', 'python3*', 'site-packages', 'bpy', '*', 'python', 'lib',
                                   'python3*', 'site-packages'))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------------------------------
# Calibration (see assets/measured.json). Linear sRGB. The flash-lit white cat in the photo reads 0.85,
# so scene irradiance is set to pi (a white Lambertian of albedo 1 renders 1.0). Skin albedos are diffuse
# albedos: under the on-axis flash the scene renders fair skin at the photo's reading (0.76, 0.49, 0.38)
# because the skin's own specular sheen and the dusk sky add to the albedo.
SKINS = {
    'fair': dict(label='fair / porcelain', albedo=(0.545, 0.325, 0.235), mole=(0.45, 0.32, 0.26), mst=2),
    'medium': dict(label='medium / olive', albedo=(0.30, 0.185, 0.085), mole=(0.52, 0.42, 0.36), mst=6),
    'deep': dict(label='deep / espresso', albedo=(0.09, 0.045, 0.026), mole=(0.6, 0.55, 0.5), mst=9),
}
SKIN_ROUGHNESS = 0.5
# dyed nylon yarn: reflectance from the flash-lit satin; bar width and translucency fitted so the scene
# renders the photo's mesh-over-skin colour (0.376, 0.188, 0.171) next to its bare skin
YARN = dict(reflect=(0.10, 0.010, 0.016), transmit=(0.20, 0.004, 0.10))
FLOCK = (0.062, 0.006, 0.011)
SATIN = (0.10, 0.009, 0.016)
LACE_THREAD = (0.115, 0.012, 0.019)

TULLE = dict(Pitch=0.60, BarWidth=0.155, BarThick=0.09, DotPitchU=9.0, DotPitchV=9.0, DotRadius=0.85, DotHeight=0.35)
LACE_NET = dict(Pitch=0.50, BarWidth=0.10, BarThick=0.06)

# torso cross-section half-axes along the height (m): A = half width, BF/BB = front/back half depth
Z_KN = np.array([-0.12, -0.05, 0.00, 0.08, 0.16, 0.26, 0.34, 0.42, 0.50])
A_KN = np.array([0.178, 0.168, 0.158, 0.139, 0.124, 0.132, 0.143, 0.149, 0.152])
BF_KN = np.array([0.108, 0.106, 0.105, 0.101, 0.093, 0.094, 0.100, 0.106, 0.108])
BB_KN = np.array([0.122, 0.114, 0.104, 0.090, 0.084, 0.088, 0.095, 0.099, 0.101])
SUPER_N = 2.4

Z_MIN, Z_MAX, DZ = -0.12, 0.50, 0.002
N_AROUND = 768

# garment layout: heights (m) and panel edges as fractions of the half circumference (0 = centre front)
LAYOUT = dict(
    bottom_band=(0.000, 0.014), waist_band=(0.150, 0.168), panels=(0.010, 0.262), border=(0.248, 0.300),
    front=0.285, side=(0.275, 0.615), back=0.605, channels=(0.28, 0.61),
)
OFFSETS = dict(mesh=0.0005, lace=0.0008, border=0.0009, channel=0.0006, band=0.0007)
WAIST_STRAIN = 0.12

MOLES = [(-0.05, 0.085, 0.0016), (0.11, 0.205, 0.0013), (-0.16, 0.335, 0.0018), (0.42, 0.115, 0.0014),
         (0.03, 0.022, 0.0011)]  # (fraction of half circumference, z, radius m)


def catmull(zk, vk, z):
    z = np.asarray(z, dtype=np.float64)
    i = np.clip(np.searchsorted(zk, z) - 1, 0, len(zk) - 2)
    t = (z - zk[i]) / (zk[i + 1] - zk[i])
    p0 = vk[np.clip(i - 1, 0, len(vk) - 1)]
    p1, p2 = vk[i], vk[i + 1]
    p3 = vk[np.clip(i + 2, 0, len(vk) - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def section(z, n=N_AROUND, dense=4096):
    """Arc-length-uniform cross-section at height z: n points starting at centre front, running towards +X."""
    A, BF, BB = (float(catmull(Z_KN, k, z)) for k in (A_KN, BF_KN, BB_KN))
    phi = np.linspace(0, 2 * np.pi, dense + 1)
    s, c = np.sin(phi), np.cos(phi)
    e = 2.0 / SUPER_N
    x = A * np.sign(s) * np.abs(s) ** e
    y = -np.where(c > 0, BF, BB) * np.sign(c) * np.abs(c) ** e
    seg = np.hypot(np.diff(x), np.diff(y))
    cum = np.concatenate([[0], np.cumsum(seg)])
    C = cum[-1]
    t = np.arange(n) * C / n
    return np.stack([np.interp(t, cum, x), np.interp(t, cum, y)], 1), C


class Torso:
    def __init__(self):
        self.z = np.arange(Z_MIN, Z_MAX + 1e-9, DZ)
        R = len(self.z)
        P = np.zeros((R, N_AROUND, 3))
        self.C = np.zeros(R)
        for i, z in enumerate(self.z):
            xy, C = section(z)
            P[i, :, :2] = xy
            P[i, :, 2] = z
            self.C[i] = C
        self.P = P
        ta = np.roll(P, -1, 1) - np.roll(P, 1, 1)
        tu = np.zeros_like(P)
        tu[1:-1] = P[2:] - P[:-2]
        tu[0], tu[-1] = P[1] - P[0], P[-1] - P[-2]
        Nrm = np.cross(ta, tu)
        self.N = Nrm / np.linalg.norm(Nrm, axis=2, keepdims=True)
        self.Ta = ta / np.linalg.norm(ta, axis=2, keepdims=True)
        self.Tu = tu / np.linalg.norm(tu, axis=2, keepdims=True)
        # signed fraction of the half circumference for every column (row independent by construction)
        j = np.arange(N_AROUND)
        self.frac = np.where(j <= N_AROUND // 2, j, j - N_AROUND) / (N_AROUND / 2)

    def rows(self, z0, z1):
        return np.where((self.z >= z0 - 1e-9) & (self.z <= z1 + 1e-9))[0]

    def cols(self, f0, f1):
        """Columns with f0 <= frac <= f1 in running order (f0 may be > f1 to wrap through the back)."""
        j = np.arange(N_AROUND)
        f = self.frac
        if f0 <= f1:
            sel = j[(f >= f0 - 1e-9) & (f <= f1 + 1e-9)]
            return sel[np.argsort(f[sel])]
        sel = j[(f >= f0 - 1e-9) | (f <= f1 + 1e-9)]
        key = np.where(f[sel] >= f0 - 1e-9, f[sel], f[sel] + 2.0)
        return sel[np.argsort(key)]

    def sample(self, frac, z):
        """Position, normal, around-tangent, up-tangent at a fractional column and height (bilinear)."""
        fj = (frac * (N_AROUND / 2)) % N_AROUND
        j0 = int(np.floor(fj)) % N_AROUND
        j1 = (j0 + 1) % N_AROUND
        tj = fj - np.floor(fj)
        fi = (z - Z_MIN) / DZ
        i0 = int(np.clip(np.floor(fi), 0, len(self.z) - 2))
        ti = fi - i0
        out = []
        for arr in (self.P, self.N, self.Ta, self.Tu):
            a = (arr[i0, j0] * (1 - tj) + arr[i0, j1] * tj) * (1 - ti) + (arr[i0 + 1, j0] * (1 - tj) + arr[i0 + 1, j1] * tj) * ti
            out.append(a)
        p, n, ta, tu = out
        return p, n / np.linalg.norm(n), ta / np.linalg.norm(ta), tu / np.linalg.norm(tu)


# ---------------------------------------------------------------------------------------------------
def build_grid_mesh(name, P, uv=None, uv_right=None, wrap=False, attrs=None, smooth=True):
    """Quad grid mesh from P (R, C, 3).

    uv (R, C, 2) gives every face's left corners; uv_right (R, C, 2) its right corners (defaults to the next
    column), so a wrapped grid can keep its texture continuous across the seam face."""
    R, C, _ = P.shape
    cols = C if wrap else C - 1
    ii, jj = np.meshgrid(np.arange(R - 1), np.arange(cols), indexing='ij')
    ii, jj = ii.ravel(), jj.ravel()
    jn = (jj + 1) % C
    quads = np.stack([ii * C + jj, ii * C + jn, (ii + 1) * C + jn, (ii + 1) * C + jj], 1)
    me = bpy.data.meshes.new(name)
    me.vertices.add(R * C)
    me.vertices.foreach_set('co', P.reshape(-1).astype(np.float32))
    me.loops.add(quads.size)
    me.loops.foreach_set('vertex_index', quads.reshape(-1).astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', (np.arange(len(quads)) * 4).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(quads), 4, np.int32))
    me.update(calc_edges=True)
    if uv is not None:
        if uv_right is None:
            uv_right = np.roll(uv, -1, axis=1)
        lay = me.uv_layers.new(name='UVMap')
        luv = np.stack([uv[ii, jj], uv_right[ii, jj], uv_right[ii + 1, jj], uv[ii + 1, jj]], 1).reshape(-1, 2)
        lay.data.foreach_set('uv', luv.astype(np.float32).reshape(-1))
    if attrs:
        for k, v in attrs.items():
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', np.asarray(v, np.float32).reshape(-1))
    me.polygons.foreach_set('use_smooth', np.full(len(quads), smooth))
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def rounded_rect(w, h, k=6, r=None):
    """Closed rounded-rectangle outline (x across, y up from 0 to h), counter-clockwise, 4k points,
    starting at the middle of the bottom (y = 0) side so a tube's seam lies against the body."""
    r = min(w, h) * 0.32 if r is None else r
    cs = [(w / 2 - r, h - r), (-w / 2 + r, h - r), (-w / 2 + r, r), (w / 2 - r, r)]
    pts = []
    for q, (cx, cy) in enumerate(cs):
        for t in np.linspace(0, np.pi / 2, k, endpoint=False):
            a = q * np.pi / 2 + t
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    pts = np.array(pts)
    start = int(np.argmin(pts[:, 1] * 10 + np.abs(pts[:, 0])))
    return np.roll(pts, -start, axis=0)


def link(nt, a, b):
    nt.links.new(a, b)


class SheerScene:
    def __init__(self, res=(800, 1000), samples=128, holo='grating', waist_strain=WAIST_STRAIN):
        self.res, self.samples = res, samples
        self.reset()
        self.torso = Torso()
        self.osl = {}
        self.objects = {}
        self.strain = waist_strain
        self._build_materials()
        self._build_geometry()
        self.set_holo(holo)
        self.set_skin('fair')
        self._build_camera()
        self.set_rig('flash')
        self.set_view('front')

    # -------------------------------------------------------------------------------------------
    def reset(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        s = self.scene = bpy.context.scene
        s.render.engine = 'CYCLES'
        s.cycles.device = 'CPU'
        s.cycles.shading_system = True  # OSL (CPU)
        s.cycles.samples = self.samples
        s.cycles.use_adaptive_sampling = True
        s.cycles.adaptive_threshold = 0.01
        s.cycles.use_denoising = True
        s.cycles.denoiser = 'OPENIMAGEDENOISE'
        s.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        s.cycles.max_bounces = 12
        s.cycles.diffuse_bounces = 4
        s.cycles.glossy_bounces = 6
        s.cycles.transmission_bounces = 8
        s.cycles.transparent_max_bounces = 32
        s.cycles.use_light_tree = True
        s.cycles.filter_width = 1.2
        s.cycles.sample_clamp_indirect = 8.0
        s.render.resolution_x, s.render.resolution_y = self.res
        s.render.resolution_percentage = 100
        s.render.image_settings.file_format = 'PNG'
        s.render.image_settings.color_mode = 'RGB'
        s.render.image_settings.color_depth = '8'
        s.render.film_transparent = False
        try:
            s.view_settings.view_transform = 'Khronos PBR Neutral'
        except TypeError:
            s.view_settings.view_transform = 'Standard'
        s.view_settings.look = 'None'
        s.view_settings.exposure = 0.0
        w = bpy.data.worlds.new('world')
        s.world = w

    def _osl(self, nt, name):
        if name not in self.osl:
            self.osl[name] = bpy.data.texts.load(os.path.join(HERE, 'osl', name + '.osl'))
        n = nt.nodes.new('ShaderNodeScript')
        n.mode = 'INTERNAL'
        n.script = self.osl[name]
        if not n.outputs:
            raise RuntimeError(f'OSL shader {name} failed to compile')
        return n

    # ------------------------------------------------------------------ materials
    def _material(self, name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        m.node_tree.nodes.clear()
        out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
        return m, m.node_tree, out

    def _build_materials(self):
        self.mats = {}
        self._skin_material()
        self.mats['mesh'] = self._tulle_material('mesh', dots=True, **TULLE)
        self.mats['lace'] = self._lace_material('lace', 'allover')
        self.mats['border'] = self._lace_material('border', 'edging')
        self.mats['satin'] = self._satin_material()
        self.mats['holo_grating'] = self._holo_grating_material()
        self.mats['holo_film'] = self._holo_film_material()
        self.mats['cap'] = self._cap_material()

    def _skin_material(self):
        m, nt, out = self._material('skin')
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        b.subsurface_method = 'RANDOM_WALK_SKIN'
        b.inputs['Subsurface Weight'].default_value = 1.0
        b.inputs['Subsurface Radius'].default_value = (3.67, 1.37, 0.68)
        b.inputs['Subsurface Scale'].default_value = 0.001
        b.inputs['Subsurface IOR'].default_value = 1.4
        b.inputs['IOR'].default_value = 1.4
        b.inputs['Roughness'].default_value = SKIN_ROUGHNESS
        b.inputs['Sheen Weight'].default_value = 0.06
        b.inputs['Sheen Roughness'].default_value = 0.35
        tc = nt.nodes.new('ShaderNodeTexCoord')
        # tone with mottling (low frequency) and moles
        base = nt.nodes.new('ShaderNodeRGB')
        self.skin_rgb = base
        mott = nt.nodes.new('ShaderNodeTexNoise')
        mott.inputs['Scale'].default_value = 9.0
        mott.inputs['Detail'].default_value = 3.0
        link(nt, tc.outputs['Object'], mott.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = 0.94
        mr.inputs['To Max'].default_value = 1.05
        link(nt, mott.outputs['Fac'], mr.inputs['Value'])
        tint = nt.nodes.new('ShaderNodeMix')
        tint.data_type = 'RGBA'
        tint.blend_type = 'MULTIPLY'
        tint.inputs['Factor'].default_value = 1.0
        link(nt, base.outputs[0], tint.inputs['A'])
        link(nt, mr.outputs['Result'], tint.inputs['B'])
        # moles: union of soft discs around fixed surface points
        mole_mask = None
        for k, (f, z, r) in enumerate(MOLES):
            p, n, _, _ = self.torso_sample(f, z)
            d = nt.nodes.new('ShaderNodeVectorMath')
            d.operation = 'DISTANCE'
            link(nt, tc.outputs['Object'], d.inputs[0])
            d.inputs[1].default_value = tuple(p)
            mm = nt.nodes.new('ShaderNodeMapRange')
            mm.inputs['From Min'].default_value = r
            mm.inputs['From Max'].default_value = r * 0.55
            link(nt, d.outputs['Value'], mm.inputs['Value'])
            if mole_mask is None:
                mole_mask = mm.outputs['Result']
            else:
                mx = nt.nodes.new('ShaderNodeMath')
                mx.operation = 'MAXIMUM'
                link(nt, mole_mask, mx.inputs[0])
                link(nt, mm.outputs['Result'], mx.inputs[1])
                mole_mask = mx.outputs[0]
        mole_col = nt.nodes.new('ShaderNodeMix')
        mole_col.data_type = 'RGBA'
        mole_col.blend_type = 'MULTIPLY'
        self.skin_mole_rgb = mole_col
        link(nt, mole_mask, mole_col.inputs['Factor'])
        link(nt, tint.outputs['Result'], mole_col.inputs['A'])
        link(nt, mole_col.outputs['Result'], b.inputs['Base Color'])
        # pores + fine relief
        vor = nt.nodes.new('ShaderNodeTexVoronoi')
        vor.feature = 'F1'
        vor.inputs['Scale'].default_value = 1500.0  # cells ~0.7 mm
        vor.inputs['Randomness'].default_value = 0.9
        link(nt, tc.outputs['Object'], vor.inputs['Vector'])
        pore = nt.nodes.new('ShaderNodeMapRange')
        pore.inputs['From Min'].default_value = 0.0
        pore.inputs['From Max'].default_value = 0.18
        pore.inputs['To Min'].default_value = -1.0
        pore.inputs['To Max'].default_value = 0.0
        link(nt, vor.outputs['Distance'], pore.inputs['Value'])
        fine = nt.nodes.new('ShaderNodeTexNoise')
        fine.inputs['Scale'].default_value = 600.0
        fine.inputs['Detail'].default_value = 4.0
        link(nt, tc.outputs['Object'], fine.inputs['Vector'])
        hsum = nt.nodes.new('ShaderNodeMath')
        hsum.operation = 'MULTIPLY_ADD'
        link(nt, fine.outputs['Fac'], hsum.inputs[0])
        hsum.inputs[1].default_value = 0.6
        link(nt, pore.outputs['Result'], hsum.inputs[2])
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.35
        bump.inputs['Distance'].default_value = 0.00004
        link(nt, hsum.outputs[0], bump.inputs['Height'])
        link(nt, bump.outputs['Normal'], b.inputs['Normal'])
        link(nt, b.outputs[0], out.inputs['Surface'])
        self.mats['skin'] = m

    def torso_sample(self, frac, z):
        if not hasattr(self, 'torso'):
            self.torso = Torso()
        return self.torso.sample(frac, z)

    def _tulle_node(self, nt, dots, **params):
        sn = self._osl(nt, 'tulle')
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        tan = nt.nodes.new('ShaderNodeTangent')
        tan.direction_type = 'UV_MAP'
        tan.uv_map = 'UVMap'
        link(nt, uvn.outputs['UV'], sn.inputs['UV'])
        link(nt, tan.outputs['Tangent'], sn.inputs['Tangent'])
        for attr, sock in (('su', 'StretchU'), ('sv', 'StretchV')):
            a = nt.nodes.new('ShaderNodeAttribute')
            a.attribute_name = attr
            link(nt, a.outputs['Fac'], sn.inputs[sock])
        sn.inputs['Dots'].default_value = 1 if dots else 0
        for k, v in params.items():
            sn.inputs[k].default_value = v
        return sn

    def _yarn_bsdf(self, nt, normal_socket):
        y = nt.nodes.new('ShaderNodeBsdfPrincipled')
        y.inputs['Base Color'].default_value = (*YARN['reflect'], 1)
        y.inputs['Roughness'].default_value = 0.5
        y.inputs['IOR'].default_value = 1.53
        y.inputs['Sheen Weight'].default_value = 0.2
        y.inputs['Sheen Roughness'].default_value = 0.4
        y.inputs['Specular Tint'].default_value = (1.0, 0.6, 0.65, 1.0)
        link(nt, normal_socket, y.inputs['Normal'])
        tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
        tl.inputs['Color'].default_value = (*YARN['transmit'], 1)
        link(nt, normal_socket, tl.inputs['Normal'])
        add = nt.nodes.new('ShaderNodeAddShader')
        link(nt, y.outputs[0], add.inputs[0])
        link(nt, tl.outputs[0], add.inputs[1])
        return add.outputs[0]

    def _tulle_material(self, name, dots, **params):
        m, nt, out = self._material(name)
        sn = self._tulle_node(nt, dots, **params)
        yarn = self._yarn_bsdf(nt, sn.outputs['YarnNormal'])
        flock = nt.nodes.new('ShaderNodeBsdfPrincipled')
        flock.inputs['Base Color'].default_value = (*FLOCK, 1)
        flock.inputs['Roughness'].default_value = 0.85
        flock.inputs['Sheen Weight'].default_value = 0.9
        flock.inputs['Sheen Roughness'].default_value = 0.5
        link(nt, sn.outputs['YarnNormal'], flock.inputs['Normal'])
        fab = nt.nodes.new('ShaderNodeMixShader')
        link(nt, sn.outputs['Dot'], fab.inputs['Fac'])
        link(nt, yarn, fab.inputs[1])
        link(nt, flock.outputs[0], fab.inputs[2])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        link(nt, sn.outputs['Alpha'], mix.inputs['Fac'])
        link(nt, tr.outputs[0], mix.inputs[1])
        link(nt, fab.outputs[0], mix.inputs[2])
        link(nt, mix.outputs[0], out.inputs['Surface'])
        self.tulle_nodes = getattr(self, 'tulle_nodes', []) + [sn]
        return m

    def _lace_material(self, name, kind):
        """Embroidered lace: thread mass from texture maps (lace_maps.py) over a fine tulle ground."""
        m, nt, out = self._material(name)
        net = self._tulle_node(nt, False, **LACE_NET)
        tex_dir = os.path.join(ROOT, 'assets', 'lace')
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        meta = {}
        mp = os.path.join(tex_dir, f'{kind}.json')
        if os.path.exists(mp):
            import json
            meta = json.load(open(mp))
        tile = meta.get('tile_mm', (64.0, 64.0))
        mapping = nt.nodes.new('ShaderNodeMapping')
        mapping.inputs['Scale'].default_value = (1.0 / tile[0], 1.0 / tile[1], 1.0)
        mapping.inputs['Location'].default_value = (meta.get('u0', 0.0), meta.get('v0', 0.0), 0)
        link(nt, uvn.outputs['UV'], mapping.inputs['Vector'])

        def img(file, colorspace='Non-Color', ext='REPEAT'):
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = bpy.data.images.load(os.path.join(tex_dir, file), check_existing=True)
            t.image.colorspace_settings.name = colorspace
            t.extension = ext
            t.interpolation = 'Cubic'
            link(nt, mapping.outputs['Vector'], t.inputs['Vector'])
            return t

        ext = 'REPEAT' if kind == 'allover' else 'EXTEND'
        if kind == 'edging':
            # repeat along U only: wrap U in the mapping, clamp V by EXTEND
            sep = nt.nodes.new('ShaderNodeSeparateXYZ')
            link(nt, mapping.outputs['Vector'], sep.inputs[0])
            fr = nt.nodes.new('ShaderNodeMath')
            fr.operation = 'FRACT'
            link(nt, sep.outputs['X'], fr.inputs[0])
            comb = nt.nodes.new('ShaderNodeCombineXYZ')
            link(nt, fr.outputs[0], comb.inputs['X'])
            link(nt, sep.outputs['Y'], comb.inputs['Y'])
            uvsrc = comb.outputs[0]
        else:
            uvsrc = mapping.outputs['Vector']
        a = img(f'{kind}_mask.png', ext=ext)
        a.name = 'trim_mask'
        nrm = img(f'{kind}_normal.png', ext=ext)
        for t in (a, nrm):
            link(nt, uvsrc, t.inputs['Vector'])
        # R = thread coverage, G = cord, B = cavity (darkening), A = scallop cut (1 inside the trim)
        sepm = nt.nodes.new('ShaderNodeSeparateColor')
        link(nt, a.outputs['Color'], sepm.inputs['Color'])
        nmap = nt.nodes.new('ShaderNodeNormalMap')
        nmap.space = 'TANGENT'
        nmap.uv_map = 'UVMap'
        nmap.inputs['Strength'].default_value = 1.0
        link(nt, nrm.outputs['Color'], nmap.inputs['Color'])
        thread = nt.nodes.new('ShaderNodeBsdfPrincipled')
        col = nt.nodes.new('ShaderNodeMix')
        col.data_type = 'RGBA'
        col.blend_type = 'MULTIPLY'
        col.inputs['A'].default_value = (*LACE_THREAD, 1)
        cav = nt.nodes.new('ShaderNodeMapRange')
        cav.inputs['To Min'].default_value = 1.0
        cav.inputs['To Max'].default_value = 0.45
        link(nt, sepm.outputs['Blue'], cav.inputs['Value'])
        link(nt, cav.outputs['Result'], col.inputs['B'])
        col.inputs['Factor'].default_value = 1.0
        link(nt, col.outputs['Result'], thread.inputs['Base Color'])
        rough = nt.nodes.new('ShaderNodeMapRange')
        rough.inputs['To Min'].default_value = 0.42
        rough.inputs['To Max'].default_value = 0.30
        link(nt, sepm.outputs['Green'], rough.inputs['Value'])
        link(nt, rough.outputs['Result'], thread.inputs['Roughness'])
        thread.inputs['Sheen Weight'].default_value = 0.4
        thread.inputs['Sheen Roughness'].default_value = 0.35
        thread.inputs['IOR'].default_value = 1.55
        thread.inputs['Specular Tint'].default_value = (1.0, 0.55, 0.6, 1.0)
        link(nt, nmap.outputs['Normal'], thread.inputs['Normal'])
        thread_tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
        thread_tl.inputs['Color'].default_value = (0.06, 0.001, 0.06, 1)
        th_add = nt.nodes.new('ShaderNodeAddShader')
        link(nt, thread.outputs[0], th_add.inputs[0])
        link(nt, thread_tl.outputs[0], th_add.inputs[1])
        yarn = self._yarn_bsdf(nt, net.outputs['YarnNormal'])
        # coverage: thread mass where the map says so, the tulle ground elsewhere, nothing outside the trim
        cov = nt.nodes.new('ShaderNodeMath')
        cov.operation = 'MAXIMUM'
        link(nt, sepm.outputs['Red'], cov.inputs[0])
        link(nt, net.outputs['Alpha'], cov.inputs[1])
        inside = nt.nodes.new('ShaderNodeMath')
        inside.operation = 'MULTIPLY'
        link(nt, cov.outputs[0], inside.inputs[0])
        link(nt, a.outputs['Alpha'], inside.inputs[1])
        fab = nt.nodes.new('ShaderNodeMixShader')
        link(nt, sepm.outputs['Red'], fab.inputs['Fac'])
        link(nt, yarn, fab.inputs[1])
        link(nt, th_add.outputs[0], fab.inputs[2])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        link(nt, inside.outputs[0], mix.inputs['Fac'])
        link(nt, tr.outputs[0], mix.inputs[1])
        link(nt, fab.outputs[0], mix.inputs[2])
        link(nt, mix.outputs[0], out.inputs['Surface'])
        self.tulle_nodes = getattr(self, 'tulle_nodes', []) + [net]
        return m

    def _satin_material(self):
        m, nt, out = self._material('satin')
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        b.inputs['Base Color'].default_value = (*SATIN, 1)
        b.inputs['Roughness'].default_value = 0.24
        b.inputs['Anisotropic'].default_value = 0.65
        b.inputs['IOR'].default_value = 1.55
        b.inputs['Specular Tint'].default_value = (1.0, 0.5, 0.55, 1)
        b.inputs['Sheen Weight'].default_value = 0.15
        tan = nt.nodes.new('ShaderNodeTangent')
        tan.direction_type = 'UV_MAP'
        tan.uv_map = 'UVMap'
        link(nt, tan.outputs['Tangent'], b.inputs['Tangent'])
        # weave: fine ribs across the strip
        tc = nt.nodes.new('ShaderNodeUVMap')
        tc.uv_map = 'UVMap'
        wave = nt.nodes.new('ShaderNodeTexWave')
        wave.wave_type = 'BANDS'
        wave.bands_direction = 'Y'
        wave.inputs['Scale'].default_value = 1.0 / 0.25 / 1.0
        wave.inputs['Distortion'].default_value = 0.6
        link(nt, tc.outputs['UV'], wave.inputs['Vector'])
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.12
        bump.inputs['Distance'].default_value = 0.00002
        link(nt, wave.outputs['Fac'], bump.inputs['Height'])
        link(nt, bump.outputs['Normal'], b.inputs['Normal'])
        link(nt, b.outputs[0], out.inputs['Surface'])
        return m

    def _band_bump(self, nt):
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        # elastic knit under the foil: ribs along the band plus mild waviness
        wave = nt.nodes.new('ShaderNodeTexWave')
        wave.wave_type = 'BANDS'
        wave.bands_direction = 'X'
        wave.inputs['Scale'].default_value = 1.0 / 0.9
        wave.inputs['Distortion'].default_value = 1.5
        link(nt, uvn.outputs['UV'], wave.inputs['Vector'])
        noise = nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 0.35
        noise.inputs['Detail'].default_value = 2.0
        link(nt, uvn.outputs['UV'], noise.inputs['Vector'])
        h = nt.nodes.new('ShaderNodeMath')
        h.operation = 'MULTIPLY_ADD'
        h.inputs[1].default_value = 0.35
        link(nt, wave.outputs['Fac'], h.inputs[0])
        link(nt, noise.outputs['Fac'], h.inputs[2])
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.45
        bump.inputs['Distance'].default_value = 0.00005
        link(nt, h.outputs[0], bump.inputs['Height'])
        return bump.outputs['Normal'], uvn

    def _holo_grating_material(self):
        m, nt, out = self._material('holo_grating')
        nrm, uvn = self._band_bump(nt)
        g = self._osl(nt, 'holo_grating')
        tan = nt.nodes.new('ShaderNodeTangent')
        tan.direction_type = 'UV_MAP'
        tan.uv_map = 'UVMap'
        link(nt, nrm, g.inputs['Normal'])
        link(nt, tan.outputs['Tangent'], g.inputs['Tangent'])
        link(nt, uvn.outputs['UV'], g.inputs['UV'])
        g.inputs['Period'].default_value = 1100.0
        g.inputs['Roughness'].default_value = 0.22
        self.grating = g
        link(nt, g.outputs['BSDF'], out.inputs['Surface'])
        return m

    def _holo_film_material(self):
        """Thin dielectric film over metal (the briefing's literal 'conductive metal thin-film')."""
        m, nt, out = self._material('holo_film')
        nrm, _ = self._band_bump(nt)
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        b.inputs['Base Color'].default_value = (0.91, 0.92, 0.92, 1)
        b.inputs['Metallic'].default_value = 1.0
        b.inputs['Roughness'].default_value = 0.16
        # best case for colour on a bright metal: high-index (TiO2-like) film on aluminium
        b.inputs['Thin Film Thickness'].default_value = 250.0
        b.inputs['Thin Film IOR'].default_value = 2.4
        link(nt, nrm, b.inputs['Normal'])
        link(nt, b.outputs[0], out.inputs['Surface'])
        self.film_bsdf = b
        return m

    def _cap_material(self):
        m, nt, out = self._material('cap')
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        b.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1)
        b.inputs['Roughness'].default_value = 0.7
        link(nt, b.outputs[0], out.inputs['Surface'])
        return m

    # ------------------------------------------------------------------ geometry
    def _stretch(self, rows):
        Cw = float(np.interp(0.16, self.torso.z, self.torso.C))
        C0 = Cw / (1.0 + self.strain)
        su = self.torso.C[rows] / C0
        sv = 1.0 / (1.0 + 0.35 * (su - 1.0))
        return su, sv

    def _panel(self, name, rows, cols, offset, mat, material_uv=True):
        T = self.torso
        P = T.P[np.ix_(rows, cols)] + offset * T.N[np.ix_(rows, cols)]
        R, Cn = len(rows), len(cols)
        s = T.frac[cols][None, :] * (T.C[rows][:, None] / 2)  # signed arc length (m)
        su, sv = self._stretch(rows)
        if material_uv:
            u = s / su[:, None] * 1000.0
            v = (T.z[rows] * 1000.0 / sv)[:, None] * np.ones((1, Cn))
        else:
            u = s * 1000.0
            v = (T.z[rows] * 1000.0)[:, None] * np.ones((1, Cn))
        uv = np.stack([u, v], 2)
        attrs = dict(su=np.repeat(su, Cn), sv=np.repeat(sv, Cn))
        ob = build_grid_mesh(name, P, uv, wrap=False, attrs=attrs)
        ob.data.materials.append(mat)
        self.objects[name] = ob
        return ob

    def _ring(self, name, rows, offset, mat):
        """Full ring of garment surface; U = arc length from centre front (mm, seam at the back)."""
        T = self.torso
        P = T.P[rows] + offset * T.N[rows]
        Cn = N_AROUND
        C = T.C[rows][:, None]
        s = T.frac[None, :] * C / 2
        step = np.broadcast_to(C / Cn, s.shape)
        su, sv = self._stretch(rows)
        v = (T.z[rows] * 1000.0)[:, None] * np.ones((1, Cn))
        uv = np.stack([s * 1000.0, v], 2)
        uv_r = np.stack([(s + step) * 1000.0, v], 2)
        attrs = dict(su=np.repeat(su, Cn), sv=np.repeat(sv, Cn))
        ob = build_grid_mesh(name, P, uv, uv_r, wrap=True, attrs=attrs)
        ob.data.materials.append(mat)
        self.objects[name] = ob
        return ob

    def _sweep_vertical(self, name, frac, z0, z1, width, thick, offset, mat):
        """Strip running up the body at a fixed fraction of the half circumference (closed ends).
        U runs along the strip (mm), V across the profile (mm)."""
        T = self.torso
        zs = np.arange(z0, z1 + 1e-9, DZ)
        prof = rounded_rect(width, thick, k=4)
        K = len(prof)
        per = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(np.vstack([prof, prof[:1]]), axis=0).T))])
        rows = []
        for z in zs:
            p, n, ta, tu = T.sample(frac, z)
            rows.append(np.array([p + ta * x + n * (offset + y) for x, y in prof]))
        P = np.array(rows)
        # close the ends by collapsing the profile to its centre
        P = np.concatenate([P[:1].mean(1, keepdims=True).repeat(K, 1), P, P[-1:].mean(1, keepdims=True).repeat(K, 1)], 0)
        zz = np.concatenate([[zs[0]], zs, [zs[-1]]])
        u = np.broadcast_to((zz * 1000.0)[:, None], (len(zz), K))
        v = np.broadcast_to((per[:K] * 1000.0)[None, :], (len(zz), K))
        v_r = np.broadcast_to((per[1:K + 1] * 1000.0)[None, :], (len(zz), K))
        uv = np.stack([u, v], 2)
        uv_r = np.stack([u, v_r], 2)
        n = P.shape[0] * K
        ob = build_grid_mesh(name, P, uv, uv_r, wrap=True, attrs=dict(su=np.ones(n), sv=np.ones(n)))
        ob.data.materials.append(mat)
        self.objects[name] = ob
        return ob

    def _sweep_ring(self, name, z0, z1, thick, offset, mat):
        """Band running around the body between heights z0 and z1 (rounded profile). Rows follow the
        profile (seam against the body), columns run around; U = arc length (mm), V across (mm)."""
        T = self.torso
        prof = rounded_rect(z1 - z0, thick, k=4)
        K = len(prof)
        zc = 0.5 * (z0 + z1)
        C = float(np.interp(zc, T.z, T.C))
        P = np.zeros((K + 1, N_AROUND, 3))
        for j in range(N_AROUND):
            p, n, ta, tu = T.sample(T.frac[j], zc)
            for k, (x, y) in enumerate(prof):
                P[k, j] = p + tu * x + n * (offset + y)
        P[K] = P[0]
        per = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(np.vstack([prof, prof[:1]]), axis=0).T))])
        s = T.frac * C / 2
        u = np.broadcast_to((s * 1000.0)[None, :], (K + 1, N_AROUND))
        u_r = u + C / N_AROUND * 1000.0
        v = np.broadcast_to(((per - per[K // 2]) * 1000.0)[:, None], (K + 1, N_AROUND))
        uv = np.stack([u, v], 2)
        uv_r = np.stack([u_r, v], 2)
        n = (K + 1) * N_AROUND
        ob = build_grid_mesh(name, P, uv, uv_r, wrap=True, attrs=dict(su=np.ones(n), sv=np.ones(n)))
        ob.data.materials.append(mat)
        self.objects[name] = ob
        return ob

    def _build_geometry(self):
        T, L, O = self.torso, LAYOUT, OFFSETS
        # form (skin) + caps
        R = len(T.z)
        form = build_grid_mesh('form', T.P, wrap=True)
        form.data.materials.append(self.mats['skin'])
        self.objects['form'] = form
        for name, i, sgn in (('cap_bottom', 0, -1), ('cap_top', R - 1, 1)):
            ring = T.P[i]
            ctr = ring.mean(0)
            me = bpy.data.meshes.new(name)
            verts = [tuple(ctr)] + [tuple(p) for p in ring]
            faces = [(0, 1 + (k + 1) % N_AROUND, 1 + k) if sgn > 0 else (0, 1 + k, 1 + (k + 1) % N_AROUND) for k in range(N_AROUND)]
            me.from_pydata(verts, [], faces)
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(ob)
            ob.data.materials.append(self.mats['skin'])
            self.objects[name] = ob
        pr = T.rows(*L['panels'])
        self._panel('mesh_front', pr, T.cols(-L['front'], L['front']), O['mesh'], self.mats['mesh'])
        self._panel('mesh_back', pr, T.cols(L['back'], -L['back']), O['mesh'], self.mats['mesh'])
        self._panel('lace_right', pr, T.cols(L['side'][0], L['side'][1]), O['lace'], self.mats['lace'], material_uv=False)
        self._panel('lace_left', pr, T.cols(-L['side'][1], -L['side'][0]), O['lace'], self.mats['lace'], material_uv=False)
        self._ring('lace_border', T.rows(*L['border']), O['border'], self.mats['border'])
        for k, f in enumerate((L['channels'][0], L['channels'][1], -L['channels'][0], -L['channels'][1])):
            self._sweep_vertical(f'channel_{k}', f, L['panels'][0] + 0.002, L['panels'][1] - 0.004, 0.0065, 0.0012,
                                 O['channel'], self.mats['satin'])
        self._sweep_ring('band_bottom', *L['bottom_band'], 0.0010, O['band'], self.mats['holo_grating'])
        self._sweep_ring('band_waist', *L['waist_band'], 0.0010, O['band'], self.mats['holo_grating'])

    def tokens(self):
        """Object names per briefing token (for masks and captions)."""
        return dict(
            mesh=['mesh_front', 'mesh_back'],
            lace=['lace_right', 'lace_left', 'lace_border'] + [f'channel_{k}' for k in range(4)],
            holo=['band_bottom', 'band_waist'],
            skin=['form', 'cap_bottom', 'cap_top'],
        )

    # ------------------------------------------------------------------ state
    def set_skin(self, tone):
        sk = SKINS[tone]
        self.skin = tone
        self.skin_rgb.outputs[0].default_value = (*sk['albedo'], 1)
        self.skin_mole_rgb.inputs['B'].default_value = (*sk['mole'], 1)

    def set_holo(self, kind):
        self.holo = kind
        mat = self.mats['holo_grating' if kind.startswith('grating') else 'holo_film']
        if kind.startswith('grating'):
            self.grating.inputs['Cell'].default_value = 0.8 if kind == 'grating_pixel' else 0.0
        for n in self.tokens()['holo']:
            ob = self.objects[n]
            ob.data.materials.clear()
            ob.data.materials.append(mat)

    def set_sss(self, on=True):
        """Skin with subsurface scattering (default) or as an opaque Lambertian surface (for the t vs t^2 probe)."""
        b = [n for n in self.mats['skin'].node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
        b.inputs['Subsurface Weight'].default_value = 1.0 if on else 0.0
        self.sss = on

    def surface_target(self, frac, z, lift=0.0):
        p, n, _, _ = self.torso.sample(frac, z)
        return tuple(p + n * lift)

    def set_strain(self, waist_strain):
        """Rebuild the net's stretch attributes (pattern circumference = waist / (1 + strain))."""
        self.strain = waist_strain
        T = self.torso
        for n in ('mesh_front', 'mesh_back'):
            me = self.objects[n].data
            co = np.zeros(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            z = co.reshape(-1, 3)[:, 2]
            rows = np.clip(np.round((z - Z_MIN) / DZ).astype(int), 0, len(T.z) - 1)
            su, sv = self._stretch(rows)
            # material UVs scale with the pattern: recompute U from the stretch ratio
            old = me.attributes['su'].data
            prev = np.zeros(len(me.vertices), np.float32)
            old.foreach_get('value', prev)
            me.attributes['su'].data.foreach_set('value', su.astype(np.float32))
            me.attributes['sv'].data.foreach_set('value', sv.astype(np.float32))
            lay = me.uv_layers['UVMap'].data
            luv = np.zeros(len(lay) * 2, np.float32)
            lay.foreach_get('uv', luv)
            luv = luv.reshape(-1, 2)
            vi = np.zeros(len(me.loops), np.int32)
            me.loops.foreach_get('vertex_index', vi)
            luv[:, 0] *= prev[vi] / su[vi]
            lay.foreach_set('uv', luv.reshape(-1))
            me.update()

    # ------------------------------------------------------------------ lights
    def _clear_lights(self):
        for ob in [o for o in bpy.data.objects if o.type == 'LIGHT']:
            bpy.data.objects.remove(ob)

    def _area(self, name, pos, target, size, irradiance, shape='RECTANGLE', spread=180.0, color=(1, 1, 1)):
        """Area light whose on-axis irradiance at the target is `irradiance` x pi (so white albedo 1 -> 1.0)."""
        ld = bpy.data.lights.new(name, 'AREA')
        ld.shape = shape
        if shape in ('RECTANGLE', 'ELLIPSE'):
            ld.size, ld.size_y = size
        else:
            ld.size = size[0]
        d = (Vector(target) - Vector(pos)).length
        ld.energy = math.pi ** 2 * d * d * irradiance
        ld.spread = math.radians(spread)
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
        return ob

    def _world(self, zenith, horizon, ground, backdrop, strength=1.0):
        w = self.scene.world
        w.use_nodes = True
        nt = w.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        link(nt, tc.outputs['Generated'], sep.inputs[0])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.0, (*ground, 1)
        cr.elements[1].position, cr.elements[1].color = 1.0, (*zenith, 1)
        e = cr.elements.new(0.47)
        e.color = (*ground, 1)
        e = cr.elements.new(0.52)
        e.color = (*horizon, 1)
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = -1.0
        mr.inputs['From Max'].default_value = 1.0
        link(nt, sep.outputs['Z'], mr.inputs['Value'])
        link(nt, mr.outputs['Result'], ramp.inputs['Fac'])
        bg = nt.nodes.new('ShaderNodeBackground')
        bg.inputs['Strength'].default_value = strength
        link(nt, ramp.outputs['Color'], bg.inputs['Color'])
        bd = nt.nodes.new('ShaderNodeBackground')
        bd.inputs['Color'].default_value = (*backdrop, 1)
        self.backdrop = bd
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        link(nt, lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        link(nt, bg.outputs[0], mix.inputs[1])
        link(nt, bd.outputs[0], mix.inputs[2])
        out = nt.nodes.new('ShaderNodeOutputWorld')
        link(nt, mix.outputs[0], out.inputs['Surface'])

    RIGS = {
        'flash': 'A: on-camera flash at dusk (as in the example photo)',
        'strobe': "A': bare strobe 45 degrees camera-left (hard, off-axis)",
        'softbox': 'B: large softboxes, catalogue',
        'rim': 'C: twin strip lights behind, rim / backlight',
    }

    def set_rig(self, rig):
        self.rig = rig
        self._clear_lights()
        tgt = (0.0, 0.0, 0.16)
        if rig == 'flash':
            # sky ~2.5 stops under the flash, blue; dark garden ground
            self._world(zenith=(0.10, 0.17, 0.30), horizon=(0.17, 0.21, 0.27), ground=(0.025, 0.03, 0.025),
                        backdrop=(0.035, 0.045, 0.06))
            self.flash = self._area('flash', (0, 0, 0), tgt, (0.07, 0.04), 1.0, color=(1.0, 0.97, 0.93))
        elif rig == 'strobe':
            self._world(zenith=(0.03, 0.03, 0.03), horizon=(0.03, 0.03, 0.03), ground=(0.02, 0.02, 0.02),
                        backdrop=(0.03, 0.03, 0.03))
            az, el, d = math.radians(-45), math.radians(30), 1.8
            pos = (d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), tgt[2] + d * math.sin(el))
            self._area('strobe', pos, tgt, (0.12, 0.12), 1.0, shape='DISK', color=(1.0, 0.98, 0.95))
        elif rig == 'softbox':
            self._world(zenith=(0.30, 0.30, 0.30), horizon=(0.26, 0.26, 0.26), ground=(0.18, 0.18, 0.18),
                        backdrop=(0.62, 0.62, 0.61))
            for name, az, el, d, size, irr in (('soft_key', -40, 20, 1.5, (1.2, 0.9), 0.55),
                                               ('soft_fill', 48, 12, 1.6, (1.2, 0.9), 0.32),
                                               ('soft_top', 0, 62, 1.4, (1.4, 0.8), 0.28)):
                a, e = math.radians(az), math.radians(el)
                pos = (d * math.cos(e) * math.sin(a), -d * math.cos(e) * math.cos(a), tgt[2] + d * math.sin(e))
                self._area(name, pos, tgt, size, irr, spread=110.0)
        elif rig == 'rim':
            self._world(zenith=(0.004, 0.004, 0.004), horizon=(0.006, 0.006, 0.006), ground=(0.003, 0.003, 0.003),
                        backdrop=(0.004, 0.004, 0.004))
            for name, az in (('rim_left', -142), ('rim_right', 142)):
                a, e, d = math.radians(az), math.radians(6), 1.3
                pos = (d * math.cos(e) * math.sin(a), -d * math.cos(e) * math.cos(a), tgt[2] + d * math.sin(e))
                self._area(name, pos, tgt, (0.25, 1.4), 1.6, spread=70.0)
            self._area('front_fill', (0.0, -2.5, 0.4), tgt, (1.0, 1.0), 0.025)
        else:
            raise ValueError(rig)
        self._sync_flash()

    def _sync_flash(self):
        """On-camera flash: 5.3 degrees above and 1.3 degrees left of the lens axis as seen from the subject
        (a speedlight 12 cm above the lens at 1.3 m), so close-ups keep the photo's near-coaxial geometry."""
        if getattr(self, 'rig', None) == 'flash' and hasattr(self, 'view_target'):
            fl = bpy.data.objects.get('flash')
            if not fl:
                return
            m = self.cam.matrix_world
            tgt = Vector(self.view_target)
            to_cam = m.translation - tgt
            d = max(to_cam.length, 1.3)
            up = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
            right = (m.to_3x3() @ Vector((1, 0, 0))).normalized()
            dirn = (to_cam.normalized() + up * math.tan(math.radians(5.3)) - right * math.tan(math.radians(1.3))).normalized()
            pos = tgt + dirn * d
            fl.location = pos
            fl.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
            fl.data.energy = math.pi ** 2 * d * d * 1.0

    # ------------------------------------------------------------------ camera
    def _build_camera(self):
        cd = bpy.data.cameras.new('cam')
        cd.sensor_fit = 'VERTICAL'
        cd.sensor_height = 36.0
        cd.sensor_width = 36.0
        cd.clip_start = 0.01
        self.cam = bpy.data.objects.new('cam', cd)
        bpy.context.scene.collection.objects.link(self.cam)
        self.scene.camera = self.cam

    VIEWS = {
        'front': dict(az=0.0, el=0.0, dist=1.30, focal=85.0, target=(0.0, 0.0, 0.165)),
        'three_quarter': dict(az=40.0, el=0.0, dist=1.30, focal=85.0, target=(0.0, 0.0, 0.165)),
        'side': dict(az=78.0, el=0.0, dist=1.30, focal=85.0, target=(0.0, 0.0, 0.165)),
        'macro': dict(az=16.0, el=4.0, dist=0.20, focal=100.0, target=None),
    }

    def set_view(self, view, **over):
        v = dict(self.VIEWS[view], **over)
        tgt = v['target']
        if tgt is None:
            # close-up where mesh, channel, lace and the waist band meet (front-right channel)
            p, n, _, _ = self.torso.sample(LAYOUT['channels'][0] - 0.012, 0.172)
            tgt = tuple(p)
        self.set_camera(v['az'], v['el'], v['dist'], v['focal'], tgt)
        self.view = view

    def set_camera(self, az, el, dist, focal, target):
        a, e = math.radians(az), math.radians(el)
        t = Vector(target)
        pos = t + Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e)))
        if Vector((pos.x, pos.y)).length < 0.2:
            raise ValueError('camera inside the form')
        self.cam.location = pos
        self.cam.rotation_euler = (t - pos).to_track_quat('-Z', 'Y').to_euler()
        self.cam.data.lens = focal
        self.view_target = tuple(t)
        self.cam_params = dict(azimuth_deg=az, elevation_deg=el, distance_m=dist, focal_mm=focal, target=list(t))
        bpy.context.view_layer.update()
        self._sync_flash()

    # ------------------------------------------------------------------ output
    def render(self, path):
        self.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)

    def render_masks(self, path, samples=24):
        """RGBA PNG: R = [PROD_mesh] panel, G = [PROD_lace] (lace + channels), B = [PROD_holo], A = body+garment.
        Garment layers are treated as opaque regions (a net panel's mask covers its openings too)."""
        s = self.scene
        saved = {n: list(ob.data.materials) for n, ob in self.objects.items()}
        keep = dict(samples=s.cycles.samples, den=s.cycles.use_denoising, vt=s.view_settings.view_transform,
                    cm=s.render.image_settings.color_mode, ft=s.render.film_transparent,
                    adapt=s.cycles.use_adaptive_sampling)
        cols = dict(mesh=(1, 0, 0), lace=(0, 1, 0), holo=(0, 0, 1), skin=(0, 0, 0))
        mats = {}
        for tok, c in cols.items():
            m, nt, out = self._material('mask_' + tok)
            e = nt.nodes.new('ShaderNodeEmission')
            e.inputs['Color'].default_value = (*c, 1)
            link(nt, e.outputs[0], out.inputs['Surface'])
            mats[tok] = m
        for tok, names in self.tokens().items():
            for n in names:
                ob = self.objects[n]
                ob.data.materials.clear()
                ob.data.materials.append(mats[tok])
        # the scalloped border: keep its trim (texture alpha) so the mask follows the scallops
        border = self.mats['border']
        bt = border.node_tree
        trim = bt.nodes['trim_mask']
        out = [n for n in bt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'][0]
        prev = out.inputs['Surface'].links[0].from_socket
        em = bt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (0, 1, 0, 1)
        tr = bt.nodes.new('ShaderNodeBsdfTransparent')
        mx = bt.nodes.new('ShaderNodeMixShader')
        link(bt, trim.outputs['Alpha'], mx.inputs['Fac'])
        link(bt, tr.outputs[0], mx.inputs[1])
        link(bt, em.outputs[0], mx.inputs[2])
        link(bt, mx.outputs[0], out.inputs['Surface'])
        ob = self.objects['lace_border']
        ob.data.materials.clear()
        ob.data.materials.append(border)
        temp_nodes = (em, tr, mx)
        hidden = [o for o in bpy.data.objects if o.type == 'LIGHT']
        for o in hidden:
            o.hide_render = True
        s.cycles.samples = samples
        s.cycles.use_adaptive_sampling = False
        s.cycles.use_denoising = False
        s.view_settings.view_transform = 'Standard'
        s.render.image_settings.color_mode = 'RGBA'
        s.render.film_transparent = True
        try:
            self.render(path)
        finally:
            for n, ms in saved.items():
                ob = self.objects[n]
                ob.data.materials.clear()
                for m in ms:
                    ob.data.materials.append(m)
            link(bt, prev, out.inputs['Surface'])
            for n in temp_nodes:
                bt.nodes.remove(n)
            for tok in mats.values():
                bpy.data.materials.remove(tok)
            for o in hidden:
                o.hide_render = False
            s.cycles.samples = keep['samples']
            s.cycles.use_adaptive_sampling = keep['adapt']
            s.cycles.use_denoising = keep['den']
            s.view_settings.view_transform = keep['vt']
            s.render.image_settings.color_mode = keep['cm']
            s.render.film_transparent = keep['ft']

    def describe(self):
        return dict(
            skin=dict(tone=self.skin, label=SKINS[self.skin]['label'], albedo_linear=SKINS[self.skin]['albedo'],
                      monk_skin_tone_approx=SKINS[self.skin]['mst']),
            rig=dict(id=self.rig, label=self.RIGS[self.rig]),
            view=dict(id=self.view, **self.cam_params),
            mesh=dict(TULLE, waist_strain=self.strain, offset_mm=OFFSETS['mesh'] * 1000, yarn=YARN),
            holo=self.holo,
            skin_subsurface=getattr(self, 'sss', True),
        )
