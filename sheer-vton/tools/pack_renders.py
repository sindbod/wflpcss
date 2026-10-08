"""Packs raw Cycles frames for the page and the repository.

    python pack_renders.py <frames_dir> <out_dir>

PNG frames become JPEG (quality 88, full-resolution chroma: 4:2:0 smears the yarn and lace colours);
token masks are copied and also turned into outline overlays (mesh pink, lace green, holo blue) for the
viewer's "token outlines" switch. manifest.json is copied with file names pointing at the JPEGs.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

COLOURS = {'mesh': (232, 69, 127), 'lace': (63, 164, 90), 'holo': (59, 143, 224)}
MST = {'fair': 5, 'medium': 6, 'deep': 8}  # measured with mst_check.py (frames rendered before that carry 2 / 6 / 9)


def overlay(mask_path, out_path):
    m = np.asarray(Image.open(mask_path).convert('RGBA'), np.float32) / 255.0
    a = m[..., 3]
    out = np.zeros(m.shape[:2] + (4,), np.float32)
    for ch, (tok, col) in enumerate(COLOURS.items()):
        region = (m[..., ch] * a) > 0.5
        edge = region & ~ndimage.binary_erosion(region, iterations=2)
        fill = region & ~edge
        out[fill, :3] = col
        out[fill, 3] = 0.16 * 255
        out[edge, :3] = col
        out[edge, 3] = 255
    Image.fromarray(out.astype(np.uint8), 'RGBA').save(out_path, optimize=True)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    manifest = json.load(open(os.path.join(src, 'manifest.json')))
    n = 0
    for set_name, frames in manifest.items():
        os.makedirs(os.path.join(dst, set_name), exist_ok=True)
        for name, rec in frames.items():
            p = os.path.join(src, rec['file'])
            if set_name == 'masks':
                im = Image.open(p)
                im.save(os.path.join(dst, 'masks', f'{name}.png'), optimize=True)
                os.makedirs(os.path.join(dst, 'overlays'), exist_ok=True)
                overlay(p, os.path.join(dst, 'overlays', f'{name}.png'))
                rec['file'] = f'masks/{name}.png'
            else:
                if 'skin' in rec and rec['skin'].get('tone') in MST:
                    rec['skin']['monk_skin_tone_approx'] = MST[rec['skin']['tone']]
                im = Image.open(p).convert('RGB')
                im.save(os.path.join(dst, set_name, f'{name}.jpg'), quality=88, subsampling=0, optimize=True)
                rec['file'] = f'{set_name}/{name}.jpg'
            n += 1
    json.dump(manifest, open(os.path.join(dst, 'manifest.json'), 'w'), indent=1)
    print(f'packed {n} files into {dst}')


if __name__ == '__main__':
    main()
