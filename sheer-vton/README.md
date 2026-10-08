# Sheer VTON ground truth

A physics check of the "Photorealistic Sheer Mesh & Metallic Holographic Lingerie VTON Pipeline" briefing,
plus the parts of that pipeline that can be built and tested without a GPU:

* **Ground-truth renders** (Blender Cycles, CPU, OSL): a dress-form torso with subsurface-scattering skin in
  three tones, wearing the briefing's three materials, under the briefing's lights. The mesh, yarn and fair
  skin are calibrated to the example photo.
* **A claim-by-claim review** of the briefing against those renders (on the results page).
* **ComfyUI**: a custom node pack (frequency-separation detail restore, token prompts, mask split,
  see-through QA), the two-pass refiner graph in API format, a static validator that checks the graph
  against ComfyUI's own node definitions, and a runner for a ComfyUI server.
* **Training data**: a randomised, token-captioned frame generator with per-token masks for a
  `[PROD_mesh]` / `[PROD_lace]` / `[PROD_holo]` LoRA.

No diffusion model ran here: the sandbox has no GPU and its network policy blocks Hugging Face and
Civitai. The refiner settings are therefore untested; the graph is checked for structure only.

## Findings in short

| Briefing says | Renders show |
|---|---|
| Hard flash gives sharp shadows under the lace seams | On-camera flash casts none (shadows fall behind the edge, as seen from the lens; the photo has none). A bare strobe 45° off-axis gives 1–2 mm lines: the garment lies within 2 mm of the skin. |
| Skin shows "cleanly" through ~40 % opaque mesh; sheer fabric is a subtractive layer | Light crosses the net twice. The net is 50 % open face-on (dots included), yet fair skin behind it keeps 21 % of its light under softboxes (in and out pass unrelated openings: about t²) and 32 % under on-camera flash (both crossings could share an opening; skin's sideways scattering decorrelates them, opaque skin would keep 42 %). An alpha blend at 50 % makes mesh panels too light. |
| Rim light: opacity shifts with fabric tension | Viewing angle dominates: 45 % coverage face-on, 85 % at 75°, 93 % at 80°. 40 % stretch only opens it from 50 % to 44 %. |
| `[PROD_holo]` is a conductive metal thin film; white glare fading to violet and magenta | White glare with violet nearest is a diffraction grating (zeroth + first order). A clear film over aluminium stays near silver (best case 0.98 / 0.82 / 0.82). |
| Frequency separation restores threads from the client asset | Only from a pixel-registered source (the pass-1 output; 1 px off is already worse than no restore), with the holo excluded (its detail is lighting), and with the detail scaled to the refined image's local brightness. Over 18 lighting changes on the renders: plain additive split −4.8 dB mean / −21 dB worst against no restore; log-luminance split −1.3 / −5.8 dB; level-matched (the node's default) +2.2 / −0.9 dB. |

## Layout

```
blender/
  sheer_scene.py         the scene: torso, skin, garment layers, materials, lighting rigs, cameras, token masks
  osl/tulle.osl          hex net + flocked dots as a coverage mask with yarn thickness (grazing angles close it)
  osl/holo_grating.osl   diffraction foil as zeroth + first-order microfacet lobes (8 wavelength bins)
  lace_maps.py           procedural embroidered rose lace (allover + scalloped edging) -> assets/lace/
  render_matrix.py       frame sets: matrix, macro, shadow, strain, holo, sss, masks (resumable, manifest.json)
  measure_seethrough.py  see-through ratios in linear light (front panel with vs without the garment)
  measure_transmission.py  the same with the net made black: skin light only (flash vs softbox, scattering vs opaque skin)
  generate_dataset.py    randomised token-captioned training frames + masks + labels.jsonl
comfyui/
  comfyui_sheer_vton/    the node pack (copy into ComfyUI/custom_nodes/)
  build_workflow.py      writes workflows/sheer_vton_refiner.api.json
  validate_workflow.py   checks a graph against ComfyUI's node definitions (ast, nothing executed)
  run_workflow.py        uploads inputs and queues the graph on a ComfyUI server
  eval_freqsep.py        scores frequency-separation variants on ground-truth renders
  tests/                 pytest (27 tests; the workflow tests need COMFYUI_SRC)
page/                    results page template (index.html) and the claim-by-claim review (claims.html)
tools/                   pack_renders.py, build_page.py, shot.mjs
assets/                  measured.json (photo), coverage_curve.json, seethrough.json, lace maps, renders/, freqsep/
```

## Running it

Blender as a Python module (`pip install bpy==5.2.*`, Python 3.13). OSL script nodes need the `oslquery`
module that ships inside the bpy wheel; `sheer_scene.py` puts it on `sys.path`.

```bash
python blender/lace_maps.py                                   # ~1 min, writes assets/lace/
python blender/render_matrix.py -- out/frames                 # all sets, ~1.7 min per frame on 4 CPU cores
python blender/measure_seethrough.py -- assets/seethrough.json
python blender/measure_transmission.py -- assets/transmission.json
python blender/generate_dataset.py -- out/dataset --count 200 --res 768 960 --samples 64
python tools/pack_renders.py out/frames assets/renders
python comfyui/eval_freqsep.py out/frames assets/freqsep             # raw PNG frames: JPEG noise would bias the scores
python tools/build_page.py --dataset out/dataset              # dist/ for the results page
```

ComfyUI:

```bash
cp -r comfyui/comfyui_sheer_vton ComfyUI/custom_nodes/
python comfyui/build_workflow.py
python -I comfyui/validate_workflow.py /path/to/ComfyUI comfyui/workflows/sheer_vton_refiner.api.json
python comfyui/run_workflow.py --pass1 vton.png --mask token_mask.png --scenario softbox --skin deep --wait
COMFYUI_SRC=/path/to/ComfyUI python -m pytest comfyui/tests
```

The graph expects an SDXL checkpoint, the token LoRA, and SDXL canny and tile ControlNets under the names in
`build_workflow.DEFAULTS` (change them there or with the runner's flags). The token mask is an RGBA PNG:
R `[PROD_mesh]`, G `[PROD_lace]`, B `[PROD_holo]`, alpha the body; `render_matrix.py masks` and the dataset
generator write them for the renders, and a segmentation model trained on those masks can write them for
photos.

## Calibration

`assets/measured.json` holds the photo's linear-sRGB readings (the photo itself is not stored). Scene
irradiance is set so a white Lambertian surface renders 1.0; the white cat in the photo reads 0.85 under
the flash. Fair-skin albedo (0.545, 0.325, 0.235) renders the photo's bare skin (0.76, 0.49, 0.38) under the
on-axis flash; the net (0.6 mm cells, 0.155 mm yarn) with yarn translucency (0.20, 0.004, 0.10) renders the
photo's mesh-over-skin (0.376, 0.188, 0.171) to within 2 %. Medium and deep albedos are estimates.

## Consent

Try-on of intimate apparel should only run on images of adult models who agreed to that use. Keep the
pipeline away from arbitrary uploaded photos of people.
