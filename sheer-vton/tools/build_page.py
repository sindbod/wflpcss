"""Assembles the results page (dist/) from the packed renders, measurements and code.

    python build_page.py [--dataset <sample_dir>]

Reads assets/renders (pack_renders.py), assets/measured.json, assets/coverage_curve.json,
assets/seethrough.json, assets/freqsep/ (eval_freqsep.py) and writes:
  dist/index.html          page content (the artifact host adds the document skeleton)
  dist/preview.html        the same with a skeleton, for local screenshots
  dist/renders/...         frames, masks, overlays
  dist/fs/...              frequency-separation crops
  dist/data/...            workflow, prompt matrix, code bundles for the in-page zip downloads
  dist/dataset/...         training sample (when --dataset is given)
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'comfyui'))
from comfyui_sheer_vton import prompts as P  # noqa: E402

DIST = os.path.join(ROOT, 'dist')
SKINS = [dict(id='fair', short='Fair', label='Fair / porcelain (Monk 2)'),
         dict(id='medium', short='Medium olive', label='Medium / olive (Monk 6)'),
         dict(id='deep', short='Deep', label='Deep / espresso (Monk 9)')]
RIGS = [dict(id='flash', short='A flash', label='A · on-camera flash at dusk'),
        dict(id='strobe', short='A′ strobe', label='A′ · bare strobe 45° left'),
        dict(id='softbox', short='B softbox', label='B · large softboxes'),
        dict(id='rim', short='C rim', label='C · rim / backlight')]
VIEWS = [dict(id='front', short='Front', label='Front'), dict(id='three_quarter', short='¾', label='Three-quarter'),
         dict(id='side', short='Side', label='Side'), dict(id='macro', short='Macro', label='Macro close-up')]
TEXT_EXT = ('.py', '.osl', '.json', '.md', '.txt', '.jsonl')


def text_bundle(base, rel_dirs, extra=None):
    out = {}
    for d in rel_dirs:
        for dirpath, dirnames, files in os.walk(os.path.join(base, d)):
            dirnames[:] = [x for x in dirnames if x not in ('__pycache__', '.pytest_cache')]
            for f in sorted(files):
                if f.endswith(TEXT_EXT):
                    p = os.path.join(dirpath, f)
                    out[os.path.relpath(p, base)] = open(p, encoding='utf-8').read()
    out.update(extra or {})
    return out


def main():
    args = sys.argv[1:]
    dataset = args[args.index('--dataset') + 1] if '--dataset' in args else None
    renders = os.path.join(ROOT, 'assets', 'renders')
    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(os.path.join(DIST, 'data'))
    shutil.copytree(renders, os.path.join(DIST, 'renders'))
    fs_dir = os.path.join(ROOT, 'assets', 'freqsep')
    fs = None
    if os.path.isdir(fs_dir):
        os.makedirs(os.path.join(DIST, 'fs'))
        for f in os.listdir(fs_dir):
            if f.endswith('.jpg'):
                shutil.copy(os.path.join(fs_dir, f), os.path.join(DIST, 'fs', f))
        fs = json.load(open(os.path.join(fs_dir, 'freqsep_eval.json')))
    manifest = json.load(open(os.path.join(renders, 'manifest.json')))
    measured = json.load(open(os.path.join(ROOT, 'assets', 'measured.json')))
    coverage = json.load(open(os.path.join(ROOT, 'assets', 'coverage_curve.json')))
    st_path = os.path.join(ROOT, 'assets', 'seethrough.json')
    see = json.load(open(st_path)) if os.path.exists(st_path) else None

    # prompts for every viewer state, and the full matrix for download
    corrected, briefing = {}, {}
    for r in RIGS:
        for s in SKINS:
            for v in VIEWS:
                pos, neg = P.inference_prompt(r['id'], s['id'], 'grating', v['id'])
                corrected[f"{r['id']}|{s['id']}|{v['id']}"] = dict(positive=pos, negative=neg)
            if r['id'] in P.BRIEFING:
                pos, neg = P.inference_prompt(r['id'], s['id'], style='briefing')
                briefing[f"{r['id']}|{s['id']}"] = dict(positive=pos, negative=neg)
    matrix = dict(tokens=P.TOKENS, briefing=dict(caption=P.BRIEFING_CAPTION, scenarios=P.BRIEFING, skin=P.BRIEFING_SKIN),
                  corrected={})
    for r in P.SCENARIOS:
        for s in P.SKIN:
            for h in P.HOLO:
                for v in P.VIEWS:
                    pos, neg = P.inference_prompt(r, s, h, v)
                    matrix['corrected'][f'{r}|{s}|{h}|{v}'] = dict(positive=pos, negative=neg)
    json.dump(matrix, open(os.path.join(DIST, 'data', 'prompt_matrix.json'), 'w'), indent=1, ensure_ascii=False)

    frames = {}
    for set_name in ('matrix', 'macro'):
        for name, rec in manifest.get(set_name, {}).items():
            v = rec['view']
            key = f"{rec['rig']['id']}|{rec['skin']['tone']}|{'macro' if set_name == 'macro' else v['id']}"
            frames[key] = dict(file=rec['file'], az=round(v['azimuth_deg'], 1), el=round(v['elevation_deg'], 1),
                               dist=round(v['distance_m'], 2), focal=round(v['focal_mm']), res='640×800', samples=80)
    strain = [dict(file=f'{n}.jpg', pct=int(round(r['waist_strain'] * 100))) for n, r in sorted(manifest.get('strain', {}).items())]

    nums = dict(frames=dict(count=str(sum(len(v) for k, v in manifest.items() if k != 'masks'))))
    p, w = 0.6, 0.155
    t = ((p - w) / p) ** 2
    nums.update(t=f'{t:.2f}', t2=f'{t * t:.2f}', find=dict(t2=f'≈ {t * t:.2f}'))
    if see:
        def g(rig, skin, ch=1, sss=True):
            for c in see['cases']:
                if c['rig'] == rig and c['skin'] == skin and c['sss'] == sss and abs(c['strain'] - see['cases'][0]['strain']) < 1e-6:
                    return f"{c['ratio_rgb'][ch]:.2f}"
            return None
        nums['see'] = dict(fair_flash=g('flash', 'fair'), fair_softbox=g('softbox', 'fair'),
                           deep_softbox_r=g('softbox', 'deep', 0), medium_softbox=g('softbox', 'medium'))
    if fs:
        v = fs['variants']
        add = v['additive luminance, holo excluded']['mesh']['detail_rms']
        mul = v['multiplicative luminance + guard, holo excluded (node default)']['mesh']['detail_rms']
        nums['fs_ratio'] = f'{add / max(mul, 1e-9):.1f}×'
        nums['find']['fs'] = nums['fs_ratio']
    meta = dict(skin=dict(tone='fair'), rig=dict(id='flash'), view=dict(id='front'), holo='grating')
    nums['caption_short'] = P.training_caption(meta, style='short')

    photo = measured['photo']
    labels = dict(white_cat='White cat (exposure reference)', bare_skin_keyhole='Bare skin, keyhole',
                  bare_skin_thigh='Bare skin, thigh', mesh_over_skin_belly='Mesh over skin, belly',
                  mesh_over_skin_lower_belly='Mesh over skin, lower belly (turned away)', satin_belt='Satin waist belt',
                  satin_belt_highlight_p90='Satin belt highlight (90th percentile)', lace_cup='Lace on the cup',
                  dusk_sky='Dusk sky')
    data = dict(
        skins=SKINS, rigs=RIGS, views=VIEWS, prompts=dict(corrected=corrected, briefing=briefing), frames=frames,
        strain=strain, coverage=coverage, seethrough=see, fs=fs, film=measured['thin_film_on_metal']['rows'],
        photo=[dict(label=labels[k], rgb=photo[k]) for k in labels if k in photo],
        fits=measured['calibration']['fits'], target_mesh=measured['calibration']['target_mesh'], nums=nums,
    )

    # downloads: workflow, prompt matrix, code bundles (zipped in the page)
    shutil.copy(os.path.join(ROOT, 'comfyui', 'workflows', 'sheer_vton_refiner.api.json'),
                os.path.join(DIST, 'data', 'sheer_vton_refiner.api.json'))
    readme = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read() if os.path.exists(os.path.join(ROOT, 'README.md')) else ''
    json.dump(dict(text=text_bundle(os.path.join(ROOT, 'comfyui'), ['comfyui_sheer_vton', 'tests', 'workflows'],
                                    {**{f: open(os.path.join(ROOT, 'comfyui', f), encoding='utf-8').read()
                                        for f in ('build_workflow.py', 'validate_workflow.py', 'run_workflow.py', 'eval_freqsep.py')},
                                     'README.md': readme})),
              open(os.path.join(DIST, 'data', 'bundle_comfyui.json'), 'w'))
    json.dump(dict(text=text_bundle(ROOT, ['blender', 'tools'], {'README.md': readme,
                                                               'assets/measured.json': json.dumps(measured, indent=1)})),
              open(os.path.join(DIST, 'data', 'bundle_blender.json'), 'w'))
    fetch = {}
    for dirpath, _, files in os.walk(os.path.join(DIST, 'renders')):
        for f in files:
            rel = os.path.relpath(os.path.join(dirpath, f), DIST)
            fetch[rel.replace('renders/', '', 1)] = rel
    json.dump(dict(text={}, fetch=fetch), open(os.path.join(DIST, 'data', 'bundle_frames.json'), 'w'))
    if dataset and os.path.isdir(dataset):
        dfetch, dtext = {}, {}
        for sub in ('images', 'masks'):
            os.makedirs(os.path.join(DIST, 'dataset', sub), exist_ok=True)
            for f in sorted(os.listdir(os.path.join(dataset, sub))):
                src = os.path.join(dataset, sub, f)
                if f.endswith('.txt'):
                    dtext[f'{sub}/{f}'] = open(src, encoding='utf-8').read()
                else:
                    shutil.copy(src, os.path.join(DIST, 'dataset', sub, f))
                    dfetch[f'{sub}/{f}'] = f'dataset/{sub}/{f}'
        dtext['labels.jsonl'] = open(os.path.join(dataset, 'labels.jsonl'), encoding='utf-8').read()
        json.dump(dict(text=dtext, fetch=dfetch), open(os.path.join(DIST, 'data', 'bundle_dataset.json'), 'w'))
    else:
        json.dump(dict(text={'README.txt': 'Render the sample with blender/generate_dataset.py.\n'}, fetch={}),
                  open(os.path.join(DIST, 'data', 'bundle_dataset.json'), 'w'))

    page = open(os.path.join(ROOT, 'page', 'index.html'), encoding='utf-8').read()
    claims = open(os.path.join(ROOT, 'page', 'claims.html'), encoding='utf-8').read()
    blob = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    page = page.replace('<!--CLAIMS-->', claims).replace('/*DATA*/', blob)
    open(os.path.join(DIST, 'index.html'), 'w', encoding='utf-8').write(page)
    open(os.path.join(DIST, 'preview.html'), 'w', encoding='utf-8').write(
        '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,'
        'viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0;font:14px system-ui,sans-serif;background:#f6f6f4}'
        'img{max-width:100%}[hidden]{display:none!important}</style></head><body>' + page + '</body></html>')
    n = sum(len(f) for _, _, f in os.walk(DIST))
    print(f'built dist/index.html ({len(page) // 1024} KB), {n} files')


if __name__ == '__main__':
    main()
