"""Measure stroke thickness in the original logo letters (development aid)."""
import sys
from PIL import Image, ImageDraw
from pspshapes import letters

SCALE = 4


def flatten(paths, steps=24):
    polys = []
    for sp in paths:
        pts = []
        cur = None
        for seg in sp:
            if seg[0] in ('M', 'L'):
                cur = seg[1]
                pts.append(cur)
            else:
                (x0, y0), (x1, y1), (x2, y2), (x3, y3) = cur, seg[1], seg[2], seg[3]
                for i in range(1, steps + 1):
                    t = i / steps
                    mt = 1 - t
                    pts.append((mt ** 3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * x3,
                                mt ** 3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * y3))
                cur = seg[3]
        polys.append(pts)
    return polys


def raster(shape):
    x0, y0, x1, y1 = shape['bbox']
    w, h = int((x1 - x0) * SCALE) + 4, int((y1 - y0) * SCALE) + 4
    img = Image.new('L', (w, h), 0)
    for poly in flatten(shape['paths']):
        # even-odd: XOR each contour in
        layer = Image.new('L', (w, h), 0)
        ImageDraw.Draw(layer).polygon([((x - x0) * SCALE + 2, (y - y0) * SCALE + 2) for x, y in poly], fill=255)
        img = Image.eval(Image.merge('LA', (img, layer)).convert('L'), lambda v: v) if False else _xor(img, layer)
    return img


def _xor(a, b):
    from PIL import ImageChops
    return ImageChops.logical_xor(a.convert('1'), b.convert('1')).convert('L')


def runs_row(img, fy):
    y = int(img.height * fy)
    row = [img.getpixel((x, y)) > 0 for x in range(img.width)]
    return _runs(row)


def runs_col(img, fx):
    x = int(img.width * fx)
    col = [img.getpixel((x, y)) > 0 for y in range(img.height)]
    return _runs(col)


def _runs(bits):
    out, start = [], None
    for i, b in enumerate(bits + [False]):
        if b and start is None:
            start = i
        elif not b and start is not None:
            out.append(round((i - start) / SCALE, 1))
            start = None
    return out


if __name__ == '__main__':
    L = letters(sys.argv[1])
    for word in ('micro', 'check', 'computers'):
        print(word)
        for ch, s in L[word].items():
            img = raster(s)
            h = (s['bbox'][3] - s['bbox'][1])
            print('  %s  h=%.0f w=%.0f | row50 %s | row25 %s | col50 %s | col25 %s | col75 %s' % (
                ch, h, s['bbox'][2] - s['bbox'][0], runs_row(img, .5), runs_row(img, .25),
                runs_col(img, .5), runs_col(img, .25), runs_col(img, .75)))
