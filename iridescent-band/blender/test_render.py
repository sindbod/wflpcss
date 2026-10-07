"""Quick single-frame render to check the Blender scene and timing."""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))
from band_scene import BandScene

assets, out = sys.argv[sys.argv.index('--') + 1:][:2]
args = sys.argv[sys.argv.index('--') + 1:]
samples = int(args[2]) if len(args) > 2 else 64
disp = (args[3] != '0') if len(args) > 3 else True
t = time.time()
sc = BandScene(assets, displacement=disp, res=(960, 600), samples=samples)
print('view transform:', sc.scene.view_settings.view_transform, 'setup', round(time.time() - t, 1), 's')
t = time.time()
sc.render(out)
print('render', round(time.time() - t, 1), 's')
