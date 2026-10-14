"""Render a specimen image for each built font."""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.dirname(HERE)
LABEL = ImageFont.truetype('arial.ttf', 22)

LINES = [
    ('ABCDEFGHIJKLM', 96),
    ('NOPQRSTUVWXYZ', 96),
    ('0123456789 £', 96),
    ('. , : ; - ! ? \' " / ( ) + =', 96),
    ('MICRO CHECK COMPUTERS', 64),
    ('WELLINGTON, SOMERSET', 64),
    ('Repairs from £20 - call 01823 664943!', 48),
    ('micro-check.co.uk', 48),
]


def specimen(style, out):
    font_path = os.path.join(FONTS, 'MicroCheck-%s.otf' % style)
    width = 2200
    rows = []
    for text, size in LINES:
        f = ImageFont.truetype(font_path, size)
        rows.append((text, f, size))
    height = 90 + sum(int(s * 1.45) + 10 for _, _, s in rows)
    img = Image.new('RGB', (width, height), 'white')
    d = ImageDraw.Draw(img)
    d.text((30, 25), 'MicroCheck %s' % style, font=LABEL, fill='#888')
    y = 80
    for text, f, size in rows:
        d.text((30, y), text, font=f, fill='black')
        y += int(size * 1.45) + 10
    img.save(out)


if __name__ == '__main__':
    out_dir = sys.argv[1]
    for style in ('Micro', 'Check', 'Computers'):
        specimen(style, os.path.join(out_dir, 'specimen_%s.png' % style))
        print('ok', style)
