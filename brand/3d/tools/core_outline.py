"""Work out a smooth outline that hugs the logo AND its back-to-front copy.

The double-sided model puts the logo on the front and a copy turned round on
the back; this outline becomes the slim core between them, so neither side's
reversed letters can be seen through the gaps.

writes core_outline.json: [[x, y], ...] in logo pixels
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'fonts', 'tools'))
from pspshapes import read_shapes  # noqa: E402
from measure import flatten  # noqa: E402

PSP = os.path.join(HERE, '..', '..', 'vectorlogo.psp')
CX = 616.0          # model centre (logo px); the back copy is turned round this line
S = 2               # raster pixels per logo pixel
PAD = 80            # logo px of margin around the drawing
MARGIN = 16         # how far the outline sits outside the letters (logo px)
BRIDGE = 34         # gaps narrower than about this get filled in (logo px)


def main(preview=None):
    shapes = read_shapes(PSP)
    polys = [p for s in shapes for p in flatten(s['paths'])]
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    x0 = min(min(xs), 2 * CX - max(xs)) - PAD
    y0 = min(ys) - PAD
    w = int((max(max(xs), 2 * CX - min(xs)) + PAD - x0) * S)
    h = int((max(ys) + PAD - y0) * S)

    img = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(img)
    for p in polys:
        d.polygon([((x - x0) * S, (y - y0) * S) for x, y in p], fill=255)
        d.polygon([((2 * CX - x - x0) * S, (y - y0) * S) for x, y in p], fill=255)

    # close gaps (grow, then shrink), then grow by the margin; Gaussian growth keeps curves smooth
    def grow(im, r):
        return im.filter(ImageFilter.GaussianBlur(r * S / 2)).point(lambda v: 255 if v > 12 else 0)

    def shrink(im, r):
        return im.filter(ImageFilter.GaussianBlur(r * S / 2)).point(lambda v: 255 if v > 243 else 0)

    closed = shrink(grow(img, BRIDGE), BRIDGE)
    final = grow(Image.composite(closed, img, closed), MARGIN)
    final = final.filter(ImageFilter.GaussianBlur(3 * S)).point(lambda v: 255 if v > 127 else 0)

    # fill any holes: flood the outside from a corner
    flood = final.copy()
    ImageDraw.floodfill(flood, (0, 0), 128)
    mask = np.array(flood) != 128

    contour = trace(mask)
    contour = simplify(contour, 0.8 * S)
    pts = [((x / S) + x0, (y / S) + y0) for x, y in contour]
    pts = chaikin(pts, 2)
    out = os.path.join(HERE, 'core_outline.json')
    json.dump([[round(x, 2), round(y, 2)] for x, y in pts], open(out, 'w'))
    print('outline points', len(pts), '->', out)

    if preview:
        sc = 0.5
        pv = Image.new('RGB', (int(w / S * sc * S / 2) * 2, int(h / S * sc * S / 2) * 2), 'white')
        pd = ImageDraw.Draw(pv)
        t = lambda x, y: ((x - x0) * sc, (y - y0) * sc)
        pd.polygon([t(x, y) for x, y in pts], fill=(30, 30, 30))
        for p in polys:
            pd.polygon([t(2 * CX - x, y) for x, y in p], outline=(90, 140, 255))
        for s in shapes:
            col = {'#ff0000': (255, 40, 40), '#ffffff': (245, 245, 245), '#c7e0eb': (199, 224, 235)}[s['fill']]
            for p in flatten(s['paths']):
                pd.polygon([t(x, y) for x, y in p], fill=col)
        pv.save(preview)


def trace(mask):
    """Moore-neighbour boundary trace of the single filled region."""
    ys, xs = np.nonzero(mask)
    start = (xs[np.argmin(ys * 100000 + xs)], ys.min())
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    h, w = mask.shape
    inside = lambda x, y: 0 <= x < w and 0 <= y < h and mask[y, x]
    pts = [start]
    cur, back = start, 4  # we arrived from the left
    for _ in range(4 * (w + h) * 10):
        for i in range(8):
            d = (back + 1 + i) % 8
            nx, ny = cur[0] + dirs[d][0], cur[1] + dirs[d][1]
            if inside(nx, ny):
                back = (d + 4) % 8
                cur = (nx, ny)
                break
        if cur == start:
            break
        pts.append(cur)
    return pts


def simplify(pts, tol):
    """Douglas-Peucker on a closed polyline."""
    def dp(seq):
        if len(seq) < 3:
            return seq
        (x1, y1), (x2, y2) = seq[0], seq[-1]
        dx, dy = x2 - x1, y2 - y1
        n = (dx * dx + dy * dy) ** 0.5 or 1
        dists = [abs(dy * (x - x1) - dx * (y - y1)) / n for x, y in seq[1:-1]]
        i = max(range(len(dists)), key=dists.__getitem__)
        if dists[i] > tol:
            return dp(seq[:i + 2])[:-1] + dp(seq[i + 1:])
        return [seq[0], seq[-1]]
    half = len(pts) // 2
    return dp(pts[:half + 1])[:-1] + dp(pts[half:] + [pts[0]])[:-1]


def chaikin(pts, rounds):
    for _ in range(rounds):
        out = []
        for i in range(len(pts)):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
            out += [(ax * .75 + bx * .25, ay * .75 + by * .25), (ax * .25 + bx * .75, ay * .25 + by * .75)]
        pts = out
    return pts


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
