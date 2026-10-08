"""Scores the frequency-separation step on ground-truth renders (same camera, different lighting).

    python eval_freqsep.py <frames_dir> <out_dir> [--skin fair] [--source flash] [--target softbox]

source  = macro render under the source lighting (stands in for the pass-1 output: right garment detail,
          old lighting)
target  = the same camera under the target lighting (what a perfect refiner would produce)
refined = target with the weave blurred away (a refiner that fixed the light but lost the threads)
Each variant restores detail from source into refined and is scored against target, per token region
(token mask of the same camera): RMS error of the detail band, and PSNR.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfyui_sheer_vton import freqsep as fs  # noqa: E402


def load(p):
    if not os.path.exists(p) and p.endswith('.png'):
        p = p[:-4] + '.jpg'  # packed renders
    return np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0


def region_masks(path, shape):
    m = np.asarray(Image.open(path).convert('RGBA').resize(shape[1::-1], Image.BILINEAR), np.float32) / 255.0
    a = m[..., 3]
    return {'mesh': m[..., 0] * a, 'lace': m[..., 1] * a, 'holo': m[..., 2] * a}


def detail(img, sigma):
    y = fs.luma(img)
    return y - fs.blur(y, sigma)


def score(out, target, regions, sigma):
    res = {}
    for k, m in regions.items():
        sel = fs.blur(m, 1.0) > 0.98  # stay off region borders
        if sel.sum() < 100:
            continue
        d = detail(out, sigma)[sel] - detail(target, sigma)[sel]
        mse = float(((out - target)[sel] ** 2).mean())
        res[k] = dict(detail_rms=round(float(np.sqrt((d ** 2).mean())), 5),
                      psnr=round(float(10 * np.log10(1.0 / max(mse, 1e-10))), 2))
    return res


def sweep(frames, skins=('fair', 'medium', 'deep'),
          pairs=(('flash', 'softbox'), ('softbox', 'flash'), ('strobe', 'softbox'), ('softbox', 'rim'),
                 ('flash', 'rim'), ('rim', 'softbox'))):
    """Mesh PSNR gain over no restore for each mode, over every skin tone and lighting change."""
    modes = {'additive RGB': dict(mode='additive'), 'log-luminance': dict(mode='multiplicative', luminance_only=True),
             'level-matched (default)': dict(mode='matched')}
    gains = {k: [] for k in modes}
    for skin in skins:
        for a, b in pairs:
            src = load(os.path.join(frames, 'macro', f'{skin}_{a}.png'))
            tgt = load(os.path.join(frames, 'macro', f'{skin}_{b}.png'))
            reg = region_masks(os.path.join(frames, 'masks', 'macro.png'), tgt.shape)
            garment = np.clip(reg['mesh'] + reg['lace'] + reg['holo'], 0, 1)
            ml = np.clip(reg['mesh'] + reg['lace'], 0, 1)
            period = fs.estimate_period(src, reg['mesh'])
            sigma = max(0.6, 0.5 * period)
            refined = fs.blur(tgt, 0.9 * period / 2.0)
            refined = garment[..., None] * refined + (1 - garment[..., None]) * tgt
            base = score(refined, tgt, {'mesh': reg['mesh']}, sigma)['mesh']['psnr']
            for k, kw in modes.items():
                out = fs.restore_detail(refined, src, ml, sigma, guard=3.0, feather=1.5, **kw)[0]
                gains[k].append(score(out, tgt, {'mesh': reg['mesh']}, sigma)['mesh']['psnr'] - base)
    return {k: dict(mean_gain_db=round(float(np.mean(v)), 2), worst_gain_db=round(float(np.min(v)), 2),
                    best_gain_db=round(float(np.max(v)), 2), cases=len(v)) for k, v in gains.items()}


def main():
    frames, out = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    opt = dict(skin='fair', source='flash', target='softbox')
    for k in opt:
        if '--' + k in args:
            opt[k] = args[args.index('--' + k) + 1]
    os.makedirs(out, exist_ok=True)
    src = load(os.path.join(frames, 'macro', f"{opt['skin']}_{opt['source']}.png"))
    tgt = load(os.path.join(frames, 'macro', f"{opt['skin']}_{opt['target']}.png"))
    regions = region_masks(os.path.join(frames, 'masks', 'macro.png'), tgt.shape)
    garment = np.clip(regions['mesh'] + regions['lace'] + regions['holo'], 0, 1)
    period = fs.estimate_period(src, regions['mesh'])
    sigma = max(0.6, 0.5 * period)
    # the refiner proxy loses everything finer than about one weave period
    refined = fs.blur(tgt, 0.9 * period / 2.0)
    refined = garment[..., None] * refined + (1 - garment[..., None]) * tgt
    mesh_lace = np.clip(regions['mesh'] + regions['lace'], 0, 1)
    variants = {
        'refined (no restore)': refined,
        'briefing: additive RGB, holo included': fs.restore_detail(
            refined, src, garment, sigma, guard=0, feather=1.5, mode='additive')[0],
        'additive RGB, holo excluded': fs.restore_detail(
            refined, src, mesh_lace, sigma, guard=3.0, feather=1.5, mode='additive')[0],
        'log-luminance (multiplicative), holo excluded': fs.restore_detail(
            refined, src, mesh_lace, sigma, guard=3.0, feather=1.5, mode='multiplicative', luminance_only=True)[0],
        'level-matched, holo excluded (node default)': fs.restore_detail(
            refined, src, mesh_lace, sigma, guard=3.0, feather=1.5)[0],
        'level-matched, holo included': fs.restore_detail(refined, src, garment, sigma, guard=3.0, feather=1.5)[0],
    }
    for shift in (1, 2, 3):
        variants[f'node default, source shifted {shift} px'] = fs.restore_detail(
            refined, np.roll(src, shift, axis=1), mesh_lace, sigma, guard=3.0, feather=1.5)[0]
    results = dict(setup=dict(opt, weave_period_px=round(period, 2), sigma_px=round(sigma, 2)), variants={})
    for name, img in variants.items():
        results['variants'][name] = score(img, tgt, regions, sigma)
    results['sweep'] = sweep(frames)
    # crops for the page: source / refined / restored / target, plus the holo stale-glint case
    # crops for the page (centre of the macro: mesh, satin channel and the holo band), pixels doubled
    h, w = tgt.shape[:2]
    ch, cw = int(h * 0.36), int(w * 0.36)
    y0, x0 = int(h * 0.5) - ch // 2, int(w * 0.5) - cw // 2
    for name, img in (('source', src), ('target', tgt), ('refined', refined),
                      ('restored', variants['level-matched, holo excluded (node default)']),
                      ('briefing', variants['briefing: additive RGB, holo included']),
                      ('shift2', variants['node default, source shifted 2 px'])):
        crop = (np.clip(img[y0:y0 + ch, x0:x0 + cw], 0, 1) * 255 + 0.5).astype(np.uint8)
        Image.fromarray(crop).resize((cw * 2, ch * 2), Image.NEAREST).save(os.path.join(out, f'fs_{name}.png'))
    results['setup']['crop_px'] = [y0, x0, ch, cw]
    json.dump(results, open(os.path.join(out, 'freqsep_eval.json'), 'w'), indent=1)
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
