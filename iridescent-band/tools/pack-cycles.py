"""Convert rendered Cycles PNG frames to JPEG (q92, 4:4:4 chroma) and write the viewer manifest.

Lossy WebP forces 4:2:0 chroma, which smears the brick-scale interference colours; full-chroma JPEG
keeps them at ~40 KB per 800x500 frame.

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
        rel = info['file'][:-4] + '.jpg'
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.exists(target) or os.path.getmtime(target) < os.path.getmtime(png):
            Image.open(png).convert('RGB').save(target, 'JPEG', quality=92, subsampling=0, optimize=True)
        out.setdefault(set_name, {})[key] = dict(info, file=rel)
json.dump(out, open(os.path.join(dst, 'manifest.json'), 'w'), indent=1)
total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(dst) for f in fs)
print(sum(len(v) for v in out.values()), 'frames,', round(total / 1e6, 1), 'MB')
