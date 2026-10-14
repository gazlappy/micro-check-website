"""Read the vector shapes out of brand/vectorlogo.psp (Paint Shop Pro 7).

Each shape is returned as a list of subpaths; each subpath is a list of
segments ('L', (x, y)) or ('C', (c1x, c1y), (c2x, c2y), (x, y)), in image
pixels with y pointing down.
"""
import struct


def _blocks(data, start, end):
    pos = start
    while pos + 10 <= end and data[pos:pos + 4] == b'~BK\x00':
        bid, length = struct.unpack_from('<HI', data, pos + 4)
        yield bid, pos + 10, length
        pos += 10 + length


def _paint(data, body):
    size, stype = struct.unpack_from('<IH', data, body)
    if stype != 1:
        return None
    r, g, b = data[body + size + 4: body + size + 7]
    return '#%02x%02x%02x' % (r, g, b)


def _shape(data, body, length):
    end = body + length
    asize = struct.unpack_from('<I', data, body)[0]
    nlen = struct.unpack_from('<H', data, body + 4)[0]
    name = data[body + 6: body + 6 + nlen].decode('latin1')
    stype = struct.unpack_from('<H', data, body + 6 + nlen)[0]
    if stype != 2:
        return None
    p = body + asize
    p += struct.unpack_from('<I', data, p)[0]
    paints, nodes_at = [], None
    for bid, b, ln in _blocks(data, p, end):
        if bid == 15:
            paints.append(_paint(data, b))
        nodes_at = b + ln
    nsize, count = struct.unpack_from('<II', data, nodes_at)
    q = nodes_at + nsize
    nodes = []
    for _ in range(count):
        sz = struct.unpack_from('<I', data, q)[0]
        x, y, ax, ay, bx, by = struct.unpack_from('<6d', data, q + 4)
        nodes.append(((x, y), (ax, ay), (bx, by), data[q + 52], struct.unpack_from('<H', data, q + 53)[0]))
        q += sz
    subs, cur = [], []
    for n in nodes:
        if n[3] and cur:
            subs.append(cur)
            cur = []
        cur.append(n)
    if cur:
        subs.append(cur)
    paths = []
    for sp in subs:
        seq = sp + ([sp[0]] if sp[-1][4] & 0x80 else [])
        segs = [('M', sp[0][0])]
        for a, b in zip(seq, seq[1:]):
            c1, c2 = a[2], b[1]
            if c1 == a[0] and c2 == b[0]:
                segs.append(('L', b[0]))
            else:
                segs.append(('C', c1, c2, b[0]))
        paths.append(segs)
    fill = paints[1] if len(paints) > 1 else None
    return {'name': name, 'fill': fill, 'paths': paths}


def read_shapes(filename):
    data = open(filename, 'rb').read()
    shapes = []
    for bid, b, ln in _blocks(data, 36, len(data)):
        if bid != 3:
            continue
        for lbid, lb, lln in _blocks(data, b, b + ln):
            if lbid != 4:
                continue
            nlen = struct.unpack_from('<H', data, lb + 4)[0]
            if data[lb + 6: lb + 6 + nlen] == b'check':
                continue  # hidden guide layer
            for vbid, vb, vln in _blocks(data, lb + struct.unpack_from('<I', data, lb)[0], lb + lln):
                if vbid != 13:
                    continue
                for sbid, sb, sln in _blocks(data, vb + struct.unpack_from('<I', data, vb)[0], vb + vln):
                    if sbid == 14:
                        s = _shape(data, sb, sln)
                        if s:
                            shapes.append(s)
    for s in shapes:
        pts = [p for sp in s['paths'] for seg in sp for p in seg[1:]]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        s['bbox'] = (min(xs), min(ys), max(xs), max(ys))
    return shapes


def letters(filename):
    """Group the logo shapes into the three words, ordered left to right."""
    shapes = read_shapes(filename)
    micro = [s for s in shapes if s['fill'] == '#ff0000']
    white = [s for s in shapes if s['fill'] == '#ffffff']
    check = sorted([s for s in white if s['bbox'][1] < 600], key=lambda s: s['bbox'][0])
    computers = sorted([s for s in white if s['bbox'][1] >= 600], key=lambda s: s['bbox'][0])
    dot = next(s for s in micro if s['name'] == 'idot')
    micro = sorted([s for s in micro if s is not dot], key=lambda s: s['bbox'][0])
    return {
        'micro': dict(zip('MICRO', micro)), 'micro_dot': dot,
        'check': dict(zip('CHECK', check)),
        'computers': dict(zip('COMPUTERS', computers)),
    }
