# Iridescent Band Lab

Five rendering approaches for the iridescent knitted underband of a sports bra, built to compare how
each reproduces its colour shift under changing light, viewing angle and stretch, and to generate
labelled training frames.

| # | Approach | Engine | Speed | Role |
|---|----------|--------|-------|------|
| 1 | Stock PBR | three.js `MeshPhysicalMaterial` + glTF `KHR_materials_iridescence` | real time | portable baseline |
| 2 | Spectral layers | custom BRDF in three.js: 81-λ Airy thin film, s/p polarisation, film-transmission diffuse | real time | bulk data generator |
| 3 | Diffraction | custom BRDF: grating equation, spectral dispersion of the environment, Stam lobe | real time | holographic-foil hypothesis |
| 4 | Path traced | three-gpu-pathtracer (WebGL2) with a patched layered BSDF | progressive | validation set |
| 5 | Cycles offline | Blender 5.2 Cycles, layered thin-film nodes, true micro-displacement | ~20 s/frame CPU | gold set + masks |

All five share the same geometry (`src/core/geometry.js`), knit maps (`src/core/band.js`),
optics (`src/core/spectral.js`) and lighting (`src/core/envgen.js`, HDRIs in `assets/hdr`).

## What the reference photo shows

* 12 staggered rows of brick cells, 1.8 mm row pitch, bricks ≈ 3.7 × 1.5 mm on a 4.3 mm pitch, the
  lowest three rows shrink and break up (knitted halftone fade), sage binding on top.
* Pastel colours only (saturation 0.1–0.25). The hue alternates magenta ↔ cream about every 20° of
  surface angle, and the alternation follows the light layout: magenta where a softbox mirrors in the
  band, cream where it does not.
* That is the signature of an interference layer over light yarn: the reflected interference colour
  plus its transmitted complement. Best fit: TiO₂-like film (n = 2.45) of ≈ 106 nm on a 1.58 substrate,
  a 1.6× stacked-platelet reflectance gain, warm ecru ground under the lattice, darker recessed bricks.
* The default studio rig (`envgen.js → studio`) reconstructs the photo's lighting: key softbox about
  40° camera-left, rim strip behind left, weaker fill right, nothing on the camera axis.

A 10-second test on the real garment decides between approaches 2/4/5 and 3: in a dark room, tilt the
band under a phone torch. Smooth magenta ↔ cream shifts mean interference (2/4/5); clean spectral
rainbows mean a diffraction foil (3). The *Flashlight test* lighting preset shows both cases.

## Build and run

```bash
npm install
npm run build          # writes dist/index.html (page with the bundle inlined) + assets
npx http-server dist   # or any static server; open /preview.html
```

`dist/index.html` is the page body as published (the host adds the document skeleton);
`dist/preview.html` wraps it for local viewing. Checks used during development:

```bash
node tools/screenshot.mjs out.png "__lab.use('diffraction')" 1280 800 3000
node tools/fullpage.mjs page.png 390 844 dark        # also reports horizontal overflow
node tools/test-export.mjs 2 export.zip               # end-to-end dataset export through the UI
```

## Offline approach (Blender / Cycles)

```bash
python3 -m venv .venv && .venv/bin/pip install bpy==5.2.2   # Blender as a Python module (Python 3.13)
node tools/export-assets.mjs .cache/blender-assets          # meshes, 4K maps, 16-bit height, HDRIs, scene.json
cd blender
../.venv/bin/python render_sequences.py -- ../.cache/blender-assets ../.cache/cycles-frames grid envs macro stretch
../.venv/bin/python generate_dataset.py -- ../.cache/blender-assets ../.cache/dataset --count 500 --masks
cd .. && python3 tools/pack-cycles.py .cache/cycles-frames assets/cycles
```

`band_scene.py` builds the scene: the band uses a Principled BSDF thin film inside a layered node setup
(platelet gain via additive mixing, transmittance tint via a colour ramp computed by
`spectral.js`), true displacement through adaptive subdivision, the same HDRIs, the same spot light
(power converted so a white Lambertian surface reads the same radiance as in three.js), the
Khronos PBR Neutral view transform and OIDN denoising.

## Training labels

Browser exports (`Training capture` panel) and `generate_dataset.py` write the same schema:

```
images/NNNNN.png, masks/NNNNN.png, labels.jsonl, README.txt
labels.jsonl: { file, mask, approach | renderer, camera: { camera_to_world, world_to_camera, fov_y_deg,
               intrinsics_px, azimuth_deg, elevation_deg, distance_m, ... }, lighting: { environment,
               environment_rotation_deg, key_light }, geometry: { shape, strain }, material: { ... } }
```

Coordinates are metres, Y up, band bottom edge at y = 0, front of the band facing +Z. Matrices are
row-major nested lists; cameras look down their local −Z axis with +Y up.

## Layout

```
src/core        geometry, knit maps (+ worker), spectral optics, environments, viewer, dataset export
src/approaches  a1-physical, a2-spectral, a3-diffraction, a4-pathtracer, a5-cycles, inject (BRDF hook)
src/ui          controls, page copy, measured-colour chart (data sampled from the reference photo)
page/           page template (styles + markup); build.mjs inlines the bundle
blender/        band_scene.py, render_sequences.py, generate_dataset.py, test_render.py
tools/          asset export, PNG/HDR writers, frame packer, screenshot and export tests
assets/         CC0 HDRIs (Poly Haven via the three.js examples), packed Cycles frames
```

The reference photo crop used on the page (`assets/ref/band_reference.jpg`) is not committed; put a
crop of your own photo there before building to show it on the page.

## Credits

three.js (MIT), three-gpu-pathtracer and three-mesh-bvh (MIT), fflate (MIT), Blender (GPL, used as a
tool). HDRIs: Poly Haven, CC0. The garment's brand logo is not reproduced.
