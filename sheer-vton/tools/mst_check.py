"""Nearest Monk Skin Tone swatch for the rendered bare skin (softbox, front view).

    python mst_check.py <frames_dir>

Samples the bare skin above the lace border at the centre front of matrix/<tone>_softbox_front.png (display
sRGB after the view transform, like a photo) and finds the nearest of the ten MST swatches in CIELAB.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

MST = ['#f6ede4', '#f3e7db', '#f7ead0', '#eadaba', '#d7bd96', '#a07e56', '#825c43', '#604134', '#3a312a', '#292420']


def srgb_to_lab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def main():
    frames = sys.argv[1]
    sw = [srgb_to_lab([int(h[i:i + 2], 16) for i in (1, 3, 5)]) for h in MST]
    out = {}
    for tone in ('fair', 'medium', 'deep'):
        im = np.asarray(Image.open(os.path.join(frames, 'matrix', f'{tone}_softbox_front.png')).convert('RGB'), np.float64)
        h, w = im.shape[:2]
        patch = im[int(h * 0.10):int(h * 0.17), int(w * 0.44):int(w * 0.56)].reshape(-1, 3)
        rgb = np.median(patch, 0)
        lab = srgb_to_lab(rgb)
        d = [float(np.linalg.norm(lab - s)) for s in sw]
        k = int(np.argmin(d))
        out[tone] = dict(srgb=[int(x) for x in rgb], lab=[round(float(x), 1) for x in lab], mst=k + 1, delta_e=round(d[k], 1),
                         runner_up=int(np.argsort(d)[1]) + 1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
