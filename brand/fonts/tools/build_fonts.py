"""Build the Micro-Check logo fonts.

Letters that appear in the logo are taken straight from brand/vectorlogo.psp.
Every other character is constructed from the same parts the logo letters are
made of (stems, bars, rounded corners, counters), using measurements taken
from the logo for each style. Shapes are merged with Inkscape's boolean ops.

usage: python build_fonts.py            (writes ../MicroCheck-*.otf/.ttf and ../web/*.woff)
"""
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

from pspshapes import letters

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
PSP = os.path.join(HERE, '..', '..', 'vectorlogo.psp')
INKSCAPE = r'C:\Program Files\Inkscape\bin\inkscape.com'
WORK = os.path.join(HERE, 'work')

UPM, CAP = 1000, 700
K = 0.5523  # circle approximation for rounded corners

# Measured from the logo (pixels), converted to font units by CAP / height.
STYLES = {
    'Micro': dict(word='micro', top=110, base=470, sv=53, sh=34, xb=42, rb=50, rs=7, rc=8,
                  ap=0.31, w=168, gap=43, mid=0.52, dot=0.45),
    'Check': dict(word='check', top=495, base=681, sv=50, sh=48, xb=45, rb=32, rs=5, rc=4,
                  ap=0.43, w=170, gap=40, mid=0.5, dot=0.12),
    'Computers': dict(word='computers', top=729, base=796.5, sv=25, sh=5.6, xb=6.8, rb=16, rs=3, rc=2.5,
                      ap=0.30, w=87, gap=23.5, mid=0.5, dot=0.12),
}


# ---------------------------------------------------------------- geometry

class P:
    """Style parameters in font units."""

    def __init__(self, name, s):
        k = CAP / (s['base'] - s['top'])
        self.name, self.k = name, k
        self.H = CAP
        self.SV, self.SH, self.XB = s['sv'] * k, s['sh'] * k, s['xb'] * k
        self.RB, self.RS, self.RC = s['rb'] * k, s['rs'] * k, s['rc'] * k
        self.AP = s['ap'] * CAP
        self.W = s['w'] * k
        self.SB = s['gap'] * k / 2
        self.MID = s['mid'] * CAP
        self.TW = self.SV * 1.18          # horizontal thickness of diagonals
        self.D = self.SV                  # dot width
        self.DH = self.SV if self.SV < 0.3 * CAP else CAP * 0.17  # dot height (shorter in the wide style)
        self.DR = s['dot'] * self.SV * 2  # dot corner radius
        self.SHT = min(self.SH * 1.45, self.SV)


def _corner(path, a, c, b, r):
    """Edge has arrived at a; turn the corner c and finish at b."""
    if r > 0:
        path.append('C%.1f %.1f %.1f %.1f %.1f %.1f' % (
            a[0] + (c[0] - a[0]) * K, -(a[1] + (c[1] - a[1]) * K),
            b[0] + (c[0] - b[0]) * K, -(b[1] + (c[1] - b[1]) * K), b[0], -b[1]))
    elif r < 0:
        path.append('L%.1f %.1f' % (b[0], -b[1]))
    else:
        path.append('L%.1f %.1f' % (c[0], -c[1]))


def rr(x0, y0, x1, y1, tl=0, tr=None, br=None, bl=None):
    """Rounded rectangle (y up). Radius > 0 rounds, < 0 chamfers."""
    if tr is None:
        tr = br = bl = tl
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    lim = min(x1 - x0, y1 - y0) / 2
    tl, tr, br, bl = [math.copysign(min(abs(r), lim), r) if r else 0 for r in (tl, tr, br, bl)]
    a = abs
    p = ['M%.1f %.1f' % (x0 + a(tl), -y1), 'L%.1f %.1f' % (x1 - a(tr), -y1)]
    _corner(p, (x1 - a(tr), y1), (x1, y1), (x1, y1 - a(tr)), tr)
    p.append('L%.1f %.1f' % (x1, -(y0 + a(br))))
    _corner(p, (x1, y0 + a(br)), (x1, y0), (x1 - a(br), y0), br)
    p.append('L%.1f %.1f' % (x0 + a(bl), -y0))
    _corner(p, (x0 + a(bl), y0), (x0, y0), (x0, y0 + a(bl)), bl)
    p.append('L%.1f %.1f' % (x0, -(y1 - a(tl))))
    _corner(p, (x0, y1 - a(tl)), (x0, y1), (x0 + a(tl), y1), tl)
    return ''.join(p) + 'Z'


def poly(*pts):
    return 'M' + 'L'.join('%.1f %.1f' % (x, -y) for x, y in pts) + 'Z'


def para(xb, yb, xt, yt, tw):
    """Diagonal stroke with flat (horizontal) ends."""
    return poly((xb, yb), (xb + tw, yb), (xt + tw, yt), (xt, yt))


# ---------------------------------------------------------------- letters
# Each recipe returns (width, ops); ops are ('a'dd | 's'ubtract | 'p'ost-add, path).

def recipes(p):
    H, SV, SH, XB, RB, RS, RC, W, MID, TW = p.H, p.SV, p.SH, p.XB, p.RB, p.RS, p.RC, p.W, p.MID, p.TW
    lo, hi = MID - XB / 2, MID + XB / 2
    WIDE = W * 1.62
    IN = RC + 2  # how far side notches reach into a counter, past its rounded corner

    def stub(top):
        """Length of a C-style terminal stub in a half-height bowl, or None if there's no room."""
        room = (H - SH - hi) if top else (lo - SH)
        length = SH + room * 0.4
        return length if room - (length - SH) > SV * 0.35 else None

    R = {}

    def O(w=W):
        return [('a', rr(0, 0, w, H, RB)), ('s', rr(SV, SH, w - SV, H - SH, RC))]

    R['O'] = lambda: (W, O())
    R['C'] = lambda: (W, O() + [('s', rr(W - SV - IN, p.AP, W + 1, H - p.AP))])
    R['A'] = lambda: (W, [('a', rr(0, 0, W, H, RB, RB, RS, RS)),
                          ('s', rr(SV, hi, W - SV, H - SH, RC)),
                          ('s', rr(SV, -1, W - SV, lo, RC, RC, 0, 0))])
    R['B'] = lambda: (W, [('a', rr(0, 0, W, H, RS, RB, RB, RS)),
                          ('s', rr(SV, hi, W - SV, H - SH, RC)),
                          ('s', rr(SV, SH, W - SV, lo, RC)),
                          ('s', poly((W + 1, MID + XB * .75), (W - SV * .4, MID), (W + 1, MID - XB * .75)))])
    R['D'] = lambda: (W, [('a', rr(0, 0, W, H, RS, RB, RB, RS)), ('s', rr(SV, SH, W - SV, H - SH, RC))])
    R['E'] = lambda: (W * .94, [('a', rr(0, 0, W * .94, H, RS)),
                                ('s', rr(SV, hi, W + 1, H - SH, 0, 0, 0, RC)),
                                ('s', rr(SV, SH, W + 1, lo, RC, 0, 0, 0)),
                                ('s', rr(W * .94 * .84, lo - 1, W + 1, hi + 1))])
    R['F'] = lambda: (W * .9, [('a', rr(0, 0, W * .9, H, RS)),
                               ('s', rr(SV, hi, W + 1, H - SH, 0, 0, 0, RC)),
                               ('s', rr(SV, -1, W + 1, lo, RC, 0, 0, 0)),
                               ('s', rr(W * .9 * .84, lo - 1, W + 1, hi + 1))])

    def G():
        st = stub(True)
        ops = O() + [('s', rr(W - SV - IN, hi, W + 1, H - (st or SH)))]
        ops.append(('p', rr(W * .5, lo, W - SV / 2, hi, RS, 0, 0, RS)))
        return W, ops

    R['G'] = G
    R['H'] = lambda: (W, [('a', rr(0, 0, W, H, RS)),
                          ('s', rr(SV, hi, W - SV, H + 1, 0, 0, RC, RC)),
                          ('s', rr(SV, -1, W - SV, lo, RC, RC, 0, 0))])
    R['I'] = lambda: (SV, [('a', rr(0, 0, SV, H, RS))])
    R['J'] = lambda: (W * .9, [('a', rr(0, 0, W * .9, H, RS, RS, RB, RB)),
                               ('s', rr(SV, SH, W * .9 - SV, H + 1, 0, 0, RC, RC)),
                               ('s', rr(-1, H * .33, SV + 1, H + 1))])
    R['K'] = lambda: (W, [('a', rr(0, 0, SV, H, RS)),
                          ('a', para(SV * .55, lo, W - TW, H, TW)),
                          ('a', para(W - TW, 0, SV * .55, hi, TW))])
    R['L'] = lambda: (W * .86, [('a', rr(0, 0, W * .86, H, RS)), ('s', rr(SV, SH, W + 1, H + 1, 0, 0, 0, RC))])
    R['M'] = lambda: (WIDE, [('a', rr(0, 0, WIDE, H, RB, RB, RS, RS)),
                             ('s', rr(SV, -1, WIDE / 2 - SV / 2, H - SH, RC, RC, 0, 0)),
                             ('s', rr(WIDE / 2 + SV / 2, -1, WIDE - SV, H - SH, RC, RC, 0, 0))])
    R['N'] = lambda: (W, [('a', rr(0, 0, SV, H, RS)), ('a', rr(W - SV, 0, W, H, RS)),
                          ('a', para(W - TW, 0, 0, H, TW))])

    def Pp():
        return W, [('a', rr(0, 0, SV, H, RS)),
                   ('a', rr(0, lo, W, H, RS, RB, RB, 0)),
                   ('s', rr(SV, hi, W - SV, H - SH, RC))]

    R['P'] = Pp
    R['Q'] = lambda: (W, O() + [('p', rr(W * .58, -H * .1, W * .58 + SV * .85, SH + 1, 0, 0, RS, RS))])
    R['R'] = lambda: (W, [('a', rr(0, 0, W, H, RS, RB, RS, RS)),
                          ('s', rr(SV, hi, W - SV, H - SH, RC)),
                          ('s', rr(SV, -1, W - SV, lo, RC, RC, 0, 0)),
                          ('s', poly((W + 1, MID + XB * .6), (W - SV * .3, MID), (W + 1, MID - XB * .6)))])

    def S():
        ops = [('a', rr(0, 0, W, H, RB)),
               ('s', rr(SV, hi, W - SV, H - SH, RC)), ('s', rr(SV, SH, W - SV, lo, RC))]
        st_t, st_b = stub(True), stub(False)
        ops.append(('s', rr(W - SV - IN, hi, W + 1, H - (st_t or SH))))
        ops.append(('s', rr(-1, st_b or SH, SV + IN, lo)))
        return W, ops

    R['S'] = S
    R['T'] = lambda: (W, [('a', rr(0, H - p.SHT, W, H, RS)),
                          ('a', rr(W / 2 - SV / 2, 0, W / 2 + SV / 2, H, 0, 0, RS, RS))])
    R['U'] = lambda: (W, [('a', rr(0, 0, W, H, RS, RS, RB, RB)), ('s', rr(SV, SH, W - SV, H + 1, 0, 0, RC, RC))])

    def V():
        c, ys = W * .3, H * .38
        return W, [('a', poly((0, H), (W, H), (W, ys), (W - c, 0), (c, 0), (0, ys))),
                   ('s', poly((SV, H + 1), (W - SV, H + 1), (W - SV, ys + SV * .42),
                              (W - c - SV * .42, SH), (c + SV * .42, SH), (SV, ys + SV * .42)))]

    R['V'] = V
    R['W'] = lambda: (WIDE, [('a', rr(0, 0, WIDE, H, RS, RS, RB, RB)),
                             ('s', rr(SV, SH, WIDE / 2 - SV / 2, H + 1, 0, 0, RC, RC)),
                             ('s', rr(WIDE / 2 + SV / 2, SH, WIDE - SV, H + 1, 0, 0, RC, RC))])
    R['X'] = lambda: (W, [('a', para(0, 0, W - TW, H, TW)), ('a', para(W - TW, 0, 0, H, TW))])
    R['Y'] = lambda: (W, [('a', rr(0, lo, W, H, RS, RS, RB, RB)),
                          ('s', rr(SV, hi, W - SV, H + 1, 0, 0, RC, RC)),
                          ('a', rr(W / 2 - SV / 2, 0, W / 2 + SV / 2, MID, 0, 0, RS, RS))])
    R['Z'] = lambda: (W, [('a', rr(0, H - SH, W, H, RS)), ('a', rr(0, 0, W, SH, RS)),
                          ('a', para(0, 0, W - TW * 1.05, H, TW * 1.05))])

    # digits
    DW = W * .92
    R['zero'] = lambda: (DW, O(DW))
    R['one'] = lambda: (DW * .62, [('a', rr(DW * .62 - SV, 0, DW * .62, H, RS)),
                                   ('a', rr(0, H - SH * 1.25 - XB * .4, DW * .62 - SV / 2, H, RS, 0, 0, RS))])

    def two():
        st = stub(True)
        return DW, [('a', rr(0, 0, DW, H, RB, RB, RS, RS)),
                    ('s', rr(SV, hi, DW - SV, H - SH, RC)),
                    ('s', rr(-1, hi, SV + IN, H - (st or SH))),
                    ('s', rr(SV, SH, DW + 1, lo, RC, 0, 0, RC))]

    R['two'] = two
    R['three'] = lambda: (DW, [('a', rr(0, 0, DW, H, RS, RB, RB, RS)),
                               ('s', rr(-1, hi, DW - SV, H - SH, 0, RC, RC, 0)),
                               ('s', rr(-1, SH, DW - SV, lo, 0, RC, RC, 0)),
                               ('s', rr(-1, lo - 1, DW * .22, hi + 1))])
    R['four'] = lambda: (DW, [('a', rr(0, 0, DW, H, RS)),
                              ('s', rr(SV, lo + XB, DW - SV, H + 1, 0, 0, RC, RC)),
                              ('s', rr(-1, -1, DW - SV, lo, 0, RC, 0, 0))])

    def five():
        st = stub(False)
        return DW, [('a', rr(0, 0, DW, H, RS, RS, RB, RB)),
                    ('s', rr(SV, hi, DW + 1, H - SH, 0, 0, 0, RC)),
                    ('s', rr(SV, SH, DW - SV, lo, RC)),
                    ('s', rr(-1, st or SH, SV + IN, lo))]

    def six():
        st = stub(True)
        return DW, [('a', rr(0, 0, DW, H, RB)),
                    ('s', rr(SV, hi, DW - SV, H - SH, RC)), ('s', rr(SV, SH, DW - SV, lo, RC)),
                    ('s', rr(DW - SV - IN, hi, DW + 1, H - (st or SH)))]

    def nine():
        st = stub(False)
        return DW, [('a', rr(0, 0, DW, H, RB)),
                    ('s', rr(SV, hi, DW - SV, H - SH, RC)), ('s', rr(SV, SH, DW - SV, lo, RC)),
                    ('s', rr(-1, st or SH, SV + IN, lo))]

    R['five'], R['six'], R['nine'] = five, six, nine
    R['seven'] = lambda: (DW, [('a', rr(0, 0, DW, H, RS, RB, RS, RS)), ('s', rr(-1, -1, DW - SV, H - SH, 0, RC, 0, 0))])
    R['eight'] = lambda: (DW, [('a', rr(0, 0, DW, H, RB)),
                               ('s', rr(SV, hi, DW - SV, H - SH, RC)), ('s', rr(SV, SH, DW - SV, lo, RC))])

    # punctuation
    D, DH, DR = p.D, p.DH, p.DR
    dot = lambda x=0, y=0: rr(x, y, x + D, y + DH, min(DR, DH / 2))
    R['period'] = lambda: (D, [('a', dot())])
    R['comma'] = lambda: (D, [('a', dot()), ('a', para(D * .15, -DH * .75, D * .45, DH * .5, D * .55))])
    R['colon'] = lambda: (D, [('a', dot()), ('a', dot(0, MID))])
    R['semicolon'] = lambda: (D, [('a', dot(0, MID)), ('a', dot()), ('a', para(D * .15, -DH * .75, D * .45, DH * .5, D * .55))])
    R['hyphen'] = lambda: (W * .55, [('a', rr(0, lo, W * .55, hi, RS))])
    R['exclam'] = lambda: (SV, [('a', rr(0, DH * 1.6, SV, H, RS)), ('a', dot())])

    def question():
        st = stub(True)
        cx = DW / 2
        return DW, [('a', rr(0, lo, DW, H, RB, RB, RB, 0)),
                    ('s', rr(SV, hi, DW - SV, H - SH, RC)),
                    ('s', rr(-1, lo - 1, max(cx - SV / 2, SV + IN), H - (st or SH))),
                    ('p', rr(cx - SV / 2, DH * 1.6, cx + SV / 2, hi, 0, 0, RS, RS)),
                    ('p', dot(cx - D / 2, 0))]

    R['question'] = question
    R['quotesingle'] = lambda: (SV * .8, [('a', rr(0, H * .7, SV * .8, H, RS))])
    R['quotedbl'] = lambda: (SV * 2.2, [('a', rr(0, H * .7, SV * .8, H, RS)), ('a', rr(SV * 1.4, H * .7, SV * 2.2, H, RS))])
    R['slash'] = lambda: (W * .75, [('a', para(0, -H * .05, W * .75 - TW, H * 1.02, TW))])
    BW = SV * 1.9
    R['parenleft'] = lambda: (BW, [('a', rr(0, -H * .1, BW, H * 1.06, RB, RS, RS, RB)),
                                   ('s', rr(SV, -H * .1 + SH, BW + 1, H * 1.06 - SH, RC, 0, 0, RC))])
    R['parenright'] = lambda: (BW, [('a', rr(0, -H * .1, BW, H * 1.06, RS, RB, RB, RS)),
                                    ('s', rr(-1, -H * .1 + SH, BW - SV, H * 1.06 - SH, 0, RC, RC, 0))])
    PW = W * .8
    R['plus'] = lambda: (PW, [('a', rr(0, MID - SV * .45, PW, MID + SV * .45, RS)),
                              ('a', rr(PW / 2 - SV * .45, MID - PW / 2, PW / 2 + SV * .45, MID + PW / 2, RS))])
    R['equal'] = lambda: (PW, [('a', rr(0, MID + XB * .4, PW, MID + XB * .4 + max(SH, XB), RS)),
                               ('a', rr(0, MID - XB * .4 - max(SH, XB), PW, MID - XB * .4, RS))])

    def sterling():
        x0 = W * .14
        st = stub(True)
        return W, [('a', rr(x0, MID - XB / 2, W, H, RB, RB, 0, 0)),
                   ('s', rr(x0 + SV, MID - XB / 2 - 1, W - SV, H - SH, 0, RC, 0, 0)),
                   ('s', rr(W - SV - IN, MID - XB / 2 - 1, W + 1, H - (st or SH))),
                   ('a', rr(x0, SH / 2, x0 + SV, MID, 0, 0, 0, 0)),
                   ('p', rr(0, lo - XB * .1, W * .7, hi - XB * .1, RS)),
                   ('p', rr(0, 0, W, SH, RS))]

    R['sterling'] = sterling
    R['space'] = lambda: (W * .55, [])
    return R


CHARMAP = {c: c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'}
CHARMAP.update({'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six',
                '7': 'seven', '8': 'eight', '9': 'nine', '.': 'period', ',': 'comma', ':': 'colon',
                ';': 'semicolon', '-': 'hyphen', '!': 'exclam', '?': 'question', "'": 'quotesingle',
                '"': 'quotedbl', '/': 'slash', '(': 'parenleft', ')': 'parenright', '+': 'plus',
                '=': 'equal', '£': 'sterling', ' ': 'space'})


# ---------------------------------------------------------------- boolean ops via Inkscape

def boolean_glyphs(style, glyphs):
    """glyphs: {name: (width, ops)} -> {name: [svg path d, ...]} with overlaps merged."""
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(WORK, style + '_in.svg')
    dst = os.path.join(WORK, style + '_out.svg')
    act = os.path.join(WORK, style + '_actions.txt')
    parts, actions = [], []
    for name, (w, ops) in glyphs.items():
        if not ops:
            continue
        g = ['<g id="G_%s">' % name]
        for kind in 'asp':
            g.append('<g id="G_%s_%s">' % (name, kind))
            g += ['<path d="%s"/>' % d for k, d in ops if k == kind]
            g.append('</g>')
        g.append('</g>')
        parts.append(''.join(g))
        kinds = {k for k, _ in ops}
        a = '#G_%s_a > *' % name
        actions.append('select-clear;select-by-selector:%s;path-union' % a)
        if 's' in kinds:
            s = '#G_%s_s > *' % name
            actions.append('select-clear;select-by-selector:%s;path-union' % s)
            actions.append('select-clear;select-by-selector:%s, %s;path-difference' % (a, s))
        if 'p' in kinds:
            actions.append('select-clear;select-by-selector:%s, #G_%s_p > *;path-union' % (a, name))
    with open(src, 'w', encoding='utf-8') as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-200 -1200 3000 1600">%s</svg>' % ''.join(parts))
    with open(act, 'w', encoding='utf-8') as f:
        f.write(';\n'.join(actions) + ';\nselect-clear')
    subprocess.run([INKSCAPE, src, '--actions-file=' + act, '--export-type=svg', '--export-plain-svg',
                    '--export-filename=' + dst], check=True, capture_output=True)
    tree = ET.parse(dst)
    ns = '{http://www.w3.org/2000/svg}'
    out = {}
    for g in tree.iter(ns + 'g'):
        gid = g.get('id', '')
        m = re.fullmatch(r'G_(.+)', gid)
        if m and not re.search(r'_[asp]$', gid):
            out[m.group(1)] = [pth.get('d') for pth in g.iter(ns + 'path')]
    return out


# ---------------------------------------------------------------- outlines

def contours_from_svg(ds, dx=0.0):
    """Parse svg path data (y down) into contours in font space (y up)."""
    rec = RecordingPen()
    tp = TransformPen(rec, (1, 0, 0, -1, dx, 0))
    for d in ds:
        parse_path(d, tp)
    return split_contours(rec.value)


def contours_from_psp(shape_list, x0, base, k, dx):
    rec = RecordingPen()
    for s in shape_list:
        for sp in s['paths']:
            for seg in sp:
                t = lambda pt: ((pt[0] - x0) * k + dx, (base - pt[1]) * k)
                if seg[0] == 'M':
                    rec.moveTo(t(seg[1]))
                elif seg[0] == 'L':
                    rec.lineTo(t(seg[1]))
                else:
                    rec.curveTo(t(seg[1]), t(seg[2]), t(seg[3]))
            rec.closePath()
    return split_contours(rec.value)


def split_contours(value):
    contours, cur = [], []
    for op, args in value:
        cur.append((op, args))
        if op in ('closePath', 'endPath'):
            contours.append(cur)
            cur = []
    if cur:
        cur.append(('closePath', ()))
        contours.append(cur)
    # drop degenerate contours and lineTo back onto the start point
    clean = []
    for c in contours:
        if c[0][0] != 'moveTo':
            continue
        start = c[0][1][0]
        body = c[1:-1]
        if body and body[-1][0] == 'lineTo' and _close(body[-1][1][0], start):
            body = body[:-1]
        if len(body) >= 2 or any(op == 'curveTo' for op, _ in body):
            clean.append([c[0]] + body + [('closePath', ())])
    return clean


def _close(a, b):
    return abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 0.01


def flatten(contour, steps=12):
    pts = []
    cur = None
    for op, args in contour:
        if op == 'moveTo' or op == 'lineTo':
            cur = args[0]
            pts.append(cur)
        elif op == 'curveTo':
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = cur, args[0], args[1], args[2]
            for i in range(1, steps + 1):
                t = i / steps
                mt = 1 - t
                pts.append((mt ** 3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * x3,
                            mt ** 3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * y3))
            cur = args[2]
    return pts


def area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) / 2


def inside(pt, pts):
    x, y = pt
    c = False
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def reverse(contour):
    """Reverse a contour of moveTo/lineTo/curveTo ops."""
    pts = [contour[0][1][0]]
    segs = []
    for op, args in contour[1:]:
        if op == 'lineTo':
            segs.append(('L', pts[-1], args[0]))
            pts.append(args[0])
        elif op == 'curveTo':
            segs.append(('C', pts[-1], args))
            pts.append(args[2])
    start = pts[0]
    out = [('moveTo', (start,))]
    # implicit closing line from last point back to start
    if not _close(pts[-1], start):
        out.append(('lineTo', (pts[-1],)))
    for seg in reversed(segs):
        if seg[0] == 'L':
            out.append(('lineTo', (seg[1],)))
        else:
            c1, c2, _ = seg[2]
            out.append(('curveTo', (c2, c1, seg[1])))
    if out[-1][0] == 'lineTo' and _close(out[-1][1][0], start):
        out.pop()
    out.append(('closePath', ()))
    return out


def orient(contours):
    """Outer contours counter-clockwise, holes clockwise (PostScript convention)."""
    flat = [flatten(c) for c in contours]
    out = []
    for i, c in enumerate(contours):
        depth = sum(1 for j, f in enumerate(flat) if j != i and inside(_probe(flat[i]), f))
        want_ccw = depth % 2 == 0
        is_ccw = area(flat[i]) > 0
        out.append(c if want_ccw == is_ccw else reverse(c))
    return out


def _probe(pts):
    """A point on the contour; contours never touch, so it tells us which others enclose it."""
    return pts[len(pts) // 3]


def draw(contours, pen):
    for c in contours:
        for op, args in c:
            getattr(pen, op)(*args)


def bounds(contours):
    pts = [p for c in contours for p in flatten(c)]
    if not pts:
        return 0, 0, 0, 0
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


# ---------------------------------------------------------------- font assembly

def build(style_name):
    s = STYLES[style_name]
    p = P(style_name, s)
    R = recipes(p)
    generated = {name: R[name]() for name in R}
    merged = boolean_glyphs(style_name, generated)

    glyphs = {}  # name -> (advance, contours)
    for name, (w, ops) in generated.items():
        contours = contours_from_svg(merged.get(name, []), dx=p.SB) if ops else []
        glyphs[name] = (w + 2 * p.SB, orient(contours))

    # the real logo letters replace the generated ones
    L = letters(PSP)
    originals = L[s['word']]
    for ch, shape in originals.items():
        x0 = shape['bbox'][0]
        w = (shape['bbox'][2] - x0) * p.k
        c = contours_from_psp([shape], x0, s['base'], p.k, p.SB)
        glyphs[ch] = (w + 2 * p.SB, orient(c))
    if s['word'] == 'micro':
        stem = originals['I']
        x0 = stem['bbox'][0]
        c = contours_from_psp([stem, L['micro_dot']], x0, s['base'], p.k, p.SB)
        glyphs['i'] = (glyphs['I'][0], orient(c))
    from_logo = sorted(originals)

    order = ['.notdef'] + sorted(glyphs)
    cmap = {}
    for ch, gname in CHARMAP.items():
        cmap[ord(ch)] = gname
        if ch.isalpha():
            cmap[ord(ch.lower())] = 'i' if (ch == 'I' and 'i' in glyphs) else gname
    glyphs['.notdef'] = (p.W + 2 * p.SB, orient(contours_from_svg(
        [rr(0, 0, p.W, p.H, 0) + rr(p.SV * .5, p.SV * .5, p.W - p.SV * .5, p.H - p.SV * .5, 0)], dx=p.SB)))

    family = 'MicroCheck ' + style_name
    ps_name = 'MicroCheck-' + style_name
    ymin = min(bounds(c)[1] for _, c in glyphs.values())
    ymax = max(bounds(c)[3] for _, c in glyphs.values())
    names = dict(familyName=family, styleName='Regular', uniqueFontIdentifier=ps_name + ' 1.000',
                 fullName=family, psName=ps_name, version='Version 1.000',
                 copyright='Copyright Micro-Check Computers',
                 description='Lettering from the Micro-Check Computers logo. Letters %s are traced from the logo; '
                             'the rest are drawn to match.' % ''.join(from_logo))
    metrics = dict(ascent=900, descent=-250)
    files = []
    for flavour in ('otf', 'ttf'):
        fb = FontBuilder(UPM, isTTF=(flavour == 'ttf'))
        fb.setupGlyphOrder(order)
        fb.setupCharacterMap(cmap)
        if flavour == 'otf':
            charstrings = {}
            for g in order:
                adv, contours = glyphs[g]
                pen = T2CharStringPen(round(adv), None)
                draw(contours, pen)
                charstrings[g] = pen.getCharString()
            fb.setupCFF(ps_name, {'FullName': family, 'FamilyName': family}, charstrings, {})
        else:
            tt = {}
            for g in order:
                adv, contours = glyphs[g]
                pen = TTGlyphPen(None)
                draw(contours, Cu2QuPen(pen, max_err=0.6, reverse_direction=True))
                tt[g] = pen.glyph()
            fb.setupGlyf(tt)
        hm = {}
        for g in order:
            adv = round(glyphs[g][0])
            if flavour == 'ttf':
                gl = fb.font['glyf'][g]
                gl.recalcBounds(fb.font['glyf'])
                lsb = getattr(gl, 'xMin', 0)
            else:
                b = fb.font['CFF '].cff.topDictIndex[0].CharStrings[g].calcBounds(None)
                lsb = round(b[0]) if b else 0
            hm[g] = (adv, lsb)
        fb.setupHorizontalMetrics(hm)
        fb.setupHorizontalHeader(ascent=metrics['ascent'], descent=metrics['descent'])
        fb.setupNameTable(names)
        fb.setupOS2(sTypoAscender=metrics['ascent'], sTypoDescender=metrics['descent'], sTypoLineGap=0,
                    usWinAscent=max(metrics['ascent'], math.ceil(ymax)), usWinDescent=max(-metrics['descent'], math.ceil(-ymin)),
                    sCapHeight=CAP, sxHeight=CAP, achVendID='MCHK', fsType=0)
        fb.setupPost()
        path = os.path.join(OUT, '%s.%s' % (ps_name, flavour))
        fb.save(path)
        files.append(path)
        if flavour == 'otf':
            fb.font.flavor = 'woff'
            os.makedirs(os.path.join(OUT, 'web'), exist_ok=True)
            wpath = os.path.join(OUT, 'web', '%s.woff' % ps_name)
            fb.font.save(wpath)
            files.append(wpath)
    print(style_name, 'glyphs', len(order), 'from logo:', ''.join(from_logo), '->', ', '.join(os.path.basename(f) for f in files))


if __name__ == '__main__':
    for name in (sys.argv[1:] or STYLES):
        build(name)
