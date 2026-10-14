"""Turn renders/turntable/frame_*.png into an animated WebP (transparent) and a GIF on brand purple."""
import glob
import os
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frames = [Image.open(f).convert('RGBA').resize((720, 480), Image.LANCZOS) for f in sorted(glob.glob(os.path.join(HERE, 'renders', 'turntable', 'frame_*.png')))]
ms = 70
webp = os.path.join(HERE, 'renders', 'micro-check-3d-logo-sway.webp')
frames[0].save(webp, save_all=True, append_images=frames[1:], duration=ms, loop=0, quality=82, method=2)

purple = []
for f in frames:
    bg = Image.new('RGBA', f.size, (102, 51, 204, 255))
    bg.alpha_composite(f)
    purple.append(bg.convert('RGB'))
pal = [p.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) for p in purple]
gif = os.path.join(HERE, 'renders', 'micro-check-3d-logo-sway.gif')
pal[0].save(gif, save_all=True, append_images=pal[1:], duration=ms, loop=0, optimize=True)
for p in (webp, gif):
    print(os.path.basename(p), len(frames), 'frames', os.path.getsize(p) // 1024, 'KB')
