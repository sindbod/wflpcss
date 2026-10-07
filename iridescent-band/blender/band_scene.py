"""Blender / Cycles scene for the iridescent underband (approach 5).

Builds the same geometry, maps and lighting as the real-time approaches (exported by
tools/export-assets.mjs) and renders with Cycles' Principled BSDF thin-film layer plus true
micro-displacement from the band height map.

Conventions: assets are three.js Y-up metres; Blender is Z-up, so a three.js point (x, y, z)
maps to (x, -z, y).
"""
import json
import math
import os

import bpy
from mathutils import Vector


def three_to_blender(v):
    x, y, z = v
    return Vector((x, -z, y))


def spherical(center, az_deg, el_deg, dist):
    az, el = math.radians(az_deg), math.radians(el_deg)
    c = center
    return (c[0] + dist * math.sin(az) * math.cos(el),
            c[1] + dist * math.sin(el),
            c[2] + dist * math.cos(az) * math.cos(el))


class BandScene:

    def __init__(self, assets, displacement=True, res=(960, 600), samples=96, layered=True):
        self.assets = assets
        self.meta = json.load(open(os.path.join(assets, 'scene.json')))
        self.center3 = self.meta['bandCenter']
        self.displacement = displacement
        self.layered = layered
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self._render_settings(res, samples)
        self._world()
        self._objects()
        self._camera()
        self._key_light()

    # ------------------------------------------------------------------ setup
    def _render_settings(self, res, samples):
        s = self.scene
        s.render.engine = 'CYCLES'
        s.cycles.device = 'CPU'
        s.cycles.samples = samples
        s.cycles.use_adaptive_sampling = True
        s.cycles.adaptive_threshold = 0.015
        s.cycles.use_denoising = True
        s.cycles.denoiser = 'OPENIMAGEDENOISE'
        s.cycles.max_bounces = 8
        s.cycles.diffuse_bounces = 4
        s.cycles.glossy_bounces = 4
        s.cycles.caustics_reflective = False
        s.cycles.caustics_refractive = False
        s.cycles.sample_clamp_indirect = 8.0
        s.cycles.dicing_rate = 1.0
        s.render.resolution_x, s.render.resolution_y = res
        s.render.resolution_percentage = 100
        s.render.film_transparent = False
        s.render.image_settings.file_format = 'PNG'
        s.render.image_settings.color_mode = 'RGB'
        s.render.threads_mode = 'AUTO'
        try:
            s.view_settings.view_transform = 'Khronos PBR Neutral'
        except TypeError:
            s.view_settings.view_transform = 'Standard'
        s.view_settings.look = 'None'
        s.view_settings.exposure = 0.0
        s.view_settings.gamma = 1.0

    def _world(self):
        world = bpy.data.worlds.new('World')
        self.scene.world = world
        world.use_nodes = True
        nt = world.node_tree
        nt.nodes.clear()
        coord = nt.nodes.new('ShaderNodeTexCoord')
        mapping = nt.nodes.new('ShaderNodeMapping')
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        bg = nt.nodes.new('ShaderNodeBackground')
        out = nt.nodes.new('ShaderNodeOutputWorld')
        nt.links.new(coord.outputs['Generated'], mapping.inputs['Vector'])
        nt.links.new(mapping.outputs['Vector'], env.inputs['Vector'])
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        # camera rays see the same dark studio backdrop as the web viewers; lighting comes from the HDRI
        backdrop = nt.nodes.new('ShaderNodeBackground')
        # Khronos PBR Neutral crushes dark greys (x -> 6.25 x^2); 0.042 lands on the web stage colour #1b1b1a
        backdrop.inputs['Color'].default_value = (0.0420, 0.0420, 0.0412, 1.0)
        path = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(path.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs['Background'], mix.inputs[1])
        nt.links.new(backdrop.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
        self.env_node, self.env_mapping, self.bg_node, self.backdrop_mix = env, mapping, bg, mix
        self.backdrop = backdrop
        self.set_environment('studio.hdr', 0.0)

    def show_environment_background(self, show):
        self.backdrop_mix.inputs['Fac'].default_value = 0.0 if show else 1.0
        links = self.scene.world.node_tree.links
        if show:
            for l in list(links):
                if l.to_node == self.backdrop_mix and l.to_socket == self.backdrop_mix.inputs['Fac']:
                    links.remove(l)

    def set_environment(self, filename, rotation_deg=0.0, strength=1.0):
        path = os.path.join(self.assets, filename)
        img = bpy.data.images.get(filename) or bpy.data.images.load(path)
        img.colorspace_settings.name = 'Linear Rec.709'
        self.env_node.image = img
        # Blender's equirect u = 0.5 - atan2(Y, X)/2pi equals three.js' u = 0.5 + atan2(z, x)/2pi under
        # (x, y, z) -> (x, -z, y), so no offset. three.js looks up R_y(-r)·dir, i.e. Blender R_z(-r)·dir.
        self.env_mapping.inputs['Rotation'].default_value = (0.0, 0.0, -math.radians(rotation_deg))
        self.bg_node.inputs['Strength'].default_value = strength

    def _image(self, name, colorspace):
        img = bpy.data.images.load(os.path.join(self.assets, name))
        img.colorspace_settings.name = colorspace
        return img

    def _band_material(self):
        f = self.meta['film']
        m = bpy.data.materials.new('band')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        N = nt.nodes.new
        uv = N('ShaderNodeUVMap')
        tex = {}
        for key, cs in (('albedo', 'sRGB'), ('normal', 'Non-Color'), ('orm', 'Non-Color'), ('irid', 'Non-Color')):
            t = N('ShaderNodeTexImage')
            t.image = self._image(f'band_{key}.png', cs)
            t.interpolation = 'Cubic' if key == 'normal' else 'Linear'
            t.extension = 'REPEAT'
            nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
            tex[key] = t
        orm = N('ShaderNodeSeparateColor')
        nt.links.new(tex['orm'].outputs['Color'], orm.inputs['Color'])
        irid = N('ShaderNodeSeparateColor')
        nt.links.new(tex['irid'].outputs['Color'], irid.inputs['Color'])
        nmap = N('ShaderNodeNormalMap')
        nmap.space = 'TANGENT'
        nt.links.new(tex['normal'].outputs['Color'], nmap.inputs['Color'])

        # film thickness (nm) = d0 * (1 + spread * (2G - 1) + brickOffset * B)
        def math_node(op, a=None, b=None):
            n = N('ShaderNodeMath')
            n.operation = op
            for i, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    n.inputs[i].default_value = v
                else:
                    nt.links.new(v, n.inputs[i])
            return n.outputs[0]

        dev = math_node('MULTIPLY_ADD', irid.outputs['Green'], 2.0)
        dev.node.inputs[2].default_value = -1.0
        t1 = math_node('MULTIPLY', dev, f['spread'])
        t2 = math_node('MULTIPLY', irid.outputs['Blue'], f['brickOffset'])
        t3 = math_node('ADD', t1, t2)
        t4 = math_node('ADD', t3, 1.0)
        self.thickness_scale = math_node('MULTIPLY', t4, f['d']).node
        thickness = self.thickness_scale.outputs[0]

        def principled(with_film):
            p = N('ShaderNodeBsdfPrincipled')
            nt.links.new(tex['albedo'].outputs['Color'], p.inputs['Base Color'])
            nt.links.new(orm.outputs['Green'], p.inputs['Roughness'])
            nt.links.new(nmap.outputs['Normal'], p.inputs['Normal'])
            p.inputs['IOR'].default_value = f['n3']
            if with_film:
                nt.links.new(thickness, p.inputs['Thin Film Thickness'])
                p.inputs['Thin Film IOR'].default_value = f['n2']
            else:
                p.inputs['Sheen Weight'].default_value = 0.6
                p.inputs['Sheen Roughness'].default_value = 0.55
                p.inputs['Sheen Tint'].default_value = (0.62, 0.74, 0.67, 1.0)
            return p

        plain = principled(False)
        if self.layered:
            # Layered interference model (same physics as approach 2):
            #   film reflection (Principled with black base + thin film) × stacked-platelet gain
            #   + diffuse ground tinted by the film transmittance T(θ_out)·T(θ_in)
            spec = principled(True)
            spec.inputs['Base Color'].default_value = (0, 0, 0, 1)
            if spec.inputs['Base Color'].links:
                nt.links.remove(spec.inputs['Base Color'].links[0])
            black = N('ShaderNodeBsdfDiffuse')
            black.inputs['Color'].default_value = (0, 0, 0, 1)
            g1 = N('ShaderNodeMixShader')
            g1.inputs['Fac'].default_value = min(1.0, f['specGain'] - 1.0)
            nt.links.new(black.outputs['BSDF'], g1.inputs[1])
            nt.links.new(spec.outputs['BSDF'], g1.inputs[2])
            g2 = N('ShaderNodeMixShader')
            extra = f['specGain'] * (f['brickGloss'] - 1.0)
            fac2 = math_node('MULTIPLY', irid.outputs['Blue'], min(1.0, extra))
            nt.links.new(fac2, g2.inputs['Fac'])
            nt.links.new(black.outputs['BSDF'], g2.inputs[1])
            nt.links.new(spec.outputs['BSDF'], g2.inputs[2])
            add1 = N('ShaderNodeAddShader')
            nt.links.new(spec.outputs['BSDF'], add1.inputs[0])
            nt.links.new(g1.outputs['Shader'], add1.inputs[1])
            add2 = N('ShaderNodeAddShader')
            nt.links.new(add1.outputs['Shader'], add2.inputs[0])
            nt.links.new(g2.outputs['Shader'], add2.inputs[1])
            # cos θ_out from the shading normal and the incoming ray
            geo = N('ShaderNodeNewGeometry')
            dot = N('ShaderNodeVectorMath')
            dot.operation = 'DOT_PRODUCT'
            nt.links.new(nmap.outputs['Normal'], dot.inputs[0])
            nt.links.new(geo.outputs['Incoming'], dot.inputs[1])
            cosv = math_node('ABSOLUTE', dot.outputs['Value'])
            ramp = N('ShaderNodeValToRGB')
            els = ramp.color_ramp.elements
            stops = f['flopRamp']
            els[0].position, els[0].color = stops[0]['pos'], (*stops[0]['color'], 1)
            els[1].position, els[1].color = stops[-1]['pos'], (*stops[-1]['color'], 1)
            for st in stops[1:-1]:
                e = els.new(st['pos'])
                e.color = (*st['color'], 1)
            nt.links.new(cosv, ramp.inputs['Fac'])
            tint = N('ShaderNodeMix')
            tint.data_type = 'RGBA'
            tint.blend_type = 'MULTIPLY'
            tint.inputs['Factor'].default_value = 1.0
            nt.links.new(tex['albedo'].outputs['Color'], tint.inputs['A'])
            nt.links.new(ramp.outputs['Color'], tint.inputs['B'])
            diff = N('ShaderNodeBsdfDiffuse')
            nt.links.new(tint.outputs['Result'], diff.inputs['Color'])
            nt.links.new(nmap.outputs['Normal'], diff.inputs['Normal'])
            film = N('ShaderNodeAddShader')
            nt.links.new(add2.outputs['Shader'], film.inputs[0])
            nt.links.new(diff.outputs['BSDF'], film.inputs[1])
            film_out = film.outputs['Shader']
            self.film_nodes = (spec,)
        else:
            film = principled(True)
            film_out = film.outputs['BSDF']
            self.film_nodes = (film,)
        mix = N('ShaderNodeMixShader')
        nt.links.new(irid.outputs['Red'], mix.inputs['Fac'])
        nt.links.new(plain.outputs['BSDF'], mix.inputs[1])
        nt.links.new(film_out, mix.inputs[2])
        out = N('ShaderNodeOutputMaterial')
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
        if self.displacement:
            h = N('ShaderNodeTexImage')
            h.image = self._image('band_height16.png', 'Non-Color')
            h.interpolation = 'Cubic'
            nt.links.new(uv.outputs['UV'], h.inputs['Vector'])
            disp = N('ShaderNodeDisplacement')
            hmin, hmax = self.meta['heightRangeMM']
            disp.inputs['Scale'].default_value = (hmax - hmin) / 1000.0
            disp.inputs['Midlevel'].default_value = 0.0
            nt.links.new(h.outputs['Color'], disp.inputs['Height'])
            nt.links.new(disp.outputs['Displacement'], out.inputs['Displacement'])
            m.displacement_method = 'BOTH'
        return m

    def set_film(self, n2=None, d=None):
        film = self.film_nodes[0]
        if n2 is not None:
            film.inputs['Thin Film IOR'].default_value = n2
        if d is not None:
            self.thickness_scale.inputs[1].default_value = d

    def _simple_material(self, name, color, roughness, sheen=0.0, sheen_tint=(1, 1, 1, 1)):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes['Principled BSDF']
        p.inputs['Base Color'].default_value = (*color, 1.0)
        p.inputs['Roughness'].default_value = roughness
        p.inputs['Sheen Weight'].default_value = sheen
        p.inputs['Sheen Tint'].default_value = sheen_tint
        return m

    def _import(self, filename):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=os.path.join(self.assets, filename), forward_axis='NEGATIVE_Z', up_axis='Y')
        obj = [o for o in bpy.data.objects if o not in before][0]
        return obj

    def _objects(self):
        self.band = self._import('band_ring.obj')
        self.band.data.materials.clear()
        self.band.data.materials.append(self._band_material())
        if self.displacement:
            mod = self.band.modifiers.new('dice', 'SUBSURF')
            mod.subdivision_type = 'SIMPLE'
            mod.levels = 0
            mod.render_levels = 1
            try:
                mod.use_adaptive_subdivision = True
                mod.adaptive_pixel_size = 1.0
            except AttributeError:
                pass
        self.form = self._import('form.obj')
        self.form.data.materials.clear()
        self.form.data.materials.append(self._simple_material('form', (0.456, 0.254, 0.155), 0.62, 0.25, (0.85, 0.6, 0.5, 1)))
        for p in self.form.data.polygons:
            p.use_smooth = True
        bpy.ops.mesh.primitive_circle_add(vertices=96, radius=8.0, fill_type='NGON', location=(0, 0, -0.30))
        self.floor = bpy.context.active_object
        self.floor.data.materials.append(self._simple_material('floor', (0.012, 0.0115, 0.0105), 0.95))
        self.target = bpy.data.objects.new('target', None)
        self.target.location = three_to_blender(self.center3)
        self.scene.collection.objects.link(self.target)

    def _camera(self):
        cam_data = bpy.data.cameras.new('cam')
        cam_data.sensor_fit = 'VERTICAL'
        cam_data.lens_unit = 'FOV'
        cam_data.angle = math.radians(self.meta['camera']['fovY'])
        cam_data.clip_start = 0.005
        cam = bpy.data.objects.new('cam', cam_data)
        self.scene.collection.objects.link(cam)
        con = cam.constraints.new('TRACK_TO')
        con.target = self.target
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        self.scene.camera = cam
        self.cam = cam
        c = self.meta['camera']
        self.set_camera(c['azimuth'], c['elevation'], c['distance'])

    def set_camera(self, az, el, dist, fov=None):
        self.cam.location = three_to_blender(spherical(self.center3, az, el, dist))
        if fov:
            self.cam.data.angle = math.radians(fov)

    def _key_light(self):
        light = bpy.data.lights.new('key', 'SPOT')
        light.spot_size = 0.84
        light.spot_blend = 0.8
        obj = bpy.data.objects.new('key', light)
        self.scene.collection.objects.link(obj)
        con = obj.constraints.new('TRACK_TO')
        con.target = self.target
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        self.key = obj
        k = self.meta['key']
        self.set_key(k['azimuth'], k['elevation'], k['lux'], k['radius'])

    def set_key(self, az, el, lux, radius=0.1, on=True):
        d = self.meta['key']['distance']
        self.key.location = three_to_blender(spherical(self.center3, az, el, d))
        # three.js: white Lambertian radiance = lux  ->  irradiance pi*lux  ->  P = 4 pi^2 d^2 lux
        self.key.data.energy = 4 * math.pi ** 2 * d * d * lux if on else 0.0
        self.key.data.shadow_soft_size = radius
        self.key.hide_render = not on

    def stretch(self, strain):
        k = 1 + strain
        self.band.scale = (k, k, 1)
        self.form.scale = (k, k, 1)
        self.set_film(d=self.meta['film']['d'] / (1 + 0.45 * strain))

    def render(self, path):
        self.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
