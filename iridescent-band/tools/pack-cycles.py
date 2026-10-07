"""Convert rendered Cycles PNG frames to WebP and write the viewer manifest.

    python3 tools/pack-cycles.py .cache/cycles-frames assets/cycles
"""
import json
import os
import sys

from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
manifest = json.load(open(os.path.join(src, 'manifest.json')))
out = {}
for set_name, frames in manifest.items():
    for key, info in frames.items():
        png = os.path.join(src, info['file'])
        if not os.path.exists(png):
            continue
        rel = info['file'][:-4] + '.webp'
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.exists(target) or os.path.getmtime(target) < os.path.getmtime(png):
            Image.open(png).convert('RGB').save(target, 'WEBP', quality=86, method=6)
        out.setdefault(set_name, {})[key] = dict(info, file=rel)
json.dump(out, open(os.path.join(dst, 'manifest.json'), 'w'), indent=1)
total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(dst) for f in fs)
print(sum(len(v) for v in out.values()), 'frames,', round(total / 1e6, 1), 'MB')
