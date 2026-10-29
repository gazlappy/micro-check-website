"""Build src/assets/ink-db.json, the bulk printer -> cartridge list used by the ink finder.

Source: kurcz/PrinterTonerDB (Apache License 2.0), Printers2Toners.csv
  https://github.com/kurcz/PrinterTonerDB  (scraped North American retail data, about 2021)

That data uses North American cartridge numbers, so a UK customer would be told the wrong cartridge if it
were shown as is (US "HP 67" is UK "HP 305"). This script keeps only cartridge families whose UK equivalent is
well established, converts them, and drops everything else (those printers fall back to "ask us" and the
maker's own UK finder). Laser toner codes that are the same worldwide (HP 26A, Samsung MLT-D116L ...) are kept.
The hand-checked UK list in src/assets/ink.js always wins over this file.

usage: python tools/build_ink_db.py path/to/Printers2Toners.csv
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict

SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'assets', 'ink-db.json')

# North American -> UK cartridge family. Only families with a well-known UK equivalent.
HP_INK = {
    '60': '300', '61': '301', '62': '62', '63': '302', '64': '303', '65': '304', '67': '305',
    '564': '364', '74': '350', '75': '351', '02': '363',
    '902': '903', '906': '907', '910': '912', '952': '953', '962': '963',
    '950': '950', '951': '951', '932': '932', '933': '933', '934': '934', '935': '935',
    '920': '920', '901': '901', '940': '940', '21': '21', '22': '22', '56': '56', '57': '57',
    '45': '45', '10': '10', '11': '11', '88': '88', '70': '70', '82': '82', '711': '711', '712': '712', '727': '727',
}
CANON_INK = {
    'PG-245': 'PG-545', 'CL-246': 'CL-546', 'PG-240': 'PG-540', 'CL-241': 'CL-541',
    'PG-260': 'PG-560', 'CL-261': 'CL-561', 'PG-275': 'PG-575', 'CL-276': 'CL-576',
    'PGI-280': 'PGI-580', 'CLI-281': 'CLI-581', 'PGI-270': 'PGI-570', 'CLI-271': 'CLI-571',
    'PGI-250': 'PGI-550', 'CLI-251': 'CLI-551', 'PGI-220': 'PGI-520', 'CLI-221': 'CLI-521',
    'PGI-225': 'PGI-525', 'CLI-226': 'CLI-526', 'PG-40': 'PG-40', 'CL-41': 'CL-41',
    'PG-50': 'PG-50', 'CL-51': 'CL-51',
}
# Canon laser toner: North American 1xx is European 7xx; the newer 0xx codes are the same everywhere
CANON_TONER_NA = {'116': '716', '118': '718', '119': '719', '125': '725', '126': '726', '128': '728', '131': '731', '137': '737'}
CANON_TONER_GLOBAL = {'045', '046', '051', '052', '054', '055', '057', '067', '069', '070', '071'}

SKIP = re.compile(r'compatible|remanufactur|fuzion|generic|refill|pack\b|combo|value|bundle|fuser|maintenance|'
                  r'printhead|print head|kit\b|staple|transfer|waste|belt|paper|110v|220v|roller|adf', re.I)
COLOURS = [('tri-colour', 'Tri-colour'), ('tri-color', 'Tri-colour'), ('tricolor', 'Tri-colour'),
           ('photo black', 'Photo Black'), ('matte black', 'Matte Black'), ('light cyan', 'Light Cyan'),
           ('light magenta', 'Light Magenta'), ('photo cyan', 'Photo Cyan'), ('photo magenta', 'Photo Magenta'),
           ('black', 'Black'), ('cyan', 'Cyan'), ('magenta', 'Magenta'), ('yellow', 'Yellow'), ('grey', 'Grey'),
           ('gray', 'Grey'), ('photo', 'Photo'), ('colour', 'Colour'), ('color', 'Colour')]


def colour_of(d):
    low = d.lower()
    for k, v in COLOURS:
        if k in low:
            return v
    return ''


def convert(brand, desc):
    """Return (family, cartridge label) in UK terms, or None to drop the row."""
    if SKIP.search(desc) or re.search(r'XXL', desc):   # XXL sizes are mostly North America only
        return None
    col = colour_of(desc)
    if brand == 'HP':
        m = re.search(r'\bHP\s+(\d{2,3})(XXL|XL)?\b(?![A-Z])', desc)
        if m and m.group(1) in HP_INK:
            fam = HP_INK[m.group(1)]
            return f'HP {fam}', f'HP {fam}{m.group(2) or ""} {col}'.strip()
        m = re.search(r'\bHP\s+(\d{2,3}[AXY])\b', desc)          # LaserJet toner, e.g. HP 26A / 26X
        if m and re.search(r'toner', desc, re.I):
            fam = m.group(1)
            n = re.sub(r"[AXY]$", "", fam)
            return f'HP {n}A / {n}X toner', f'HP {fam} {col} toner'.replace('  ', ' ').strip()
        return None
    if brand == 'Canon':
        m = re.search(r'\b(PGI?|CLI?)-?(\d{2,3})(XXL|XL)?\b', desc)
        if m:
            na = f'{m.group(1)}-{m.group(2)}'
            if na in CANON_INK:
                uk = CANON_INK[na]
                return f'Canon {uk}', f'Canon {uk}{m.group(3) or ""} {col}'.strip()
            return None
        m = re.search(r'\b(?:Cartridge|CRG)[\s-]*(\d{3})([A-Z]?)\b|\bCanon\s+(\d{3})([A-Z]?)\s', desc)
        if m and re.search(r'toner|cartridge', desc, re.I):
            code = m.group(1) or m.group(3)
            suf = m.group(2) or m.group(4) or ''
            uk = CANON_TONER_NA.get(code, code if code in CANON_TONER_GLOBAL else None)
            if uk:
                return f'Canon {uk} toner', f'Canon {uk}{suf} {col} toner'.replace('  ', ' ').strip()
        return None
    if brand == 'Samsung':
        m = re.search(r'\b(?:(MLT|CLT)-)?([A-Z]\d{3}[A-Z]?)\b', desc)   # "MLT-D111S" or just "D111S"
        if m and re.search(r'toner', desc, re.I):
            code = f"{m.group(1) or ('CLT' if m.group(2)[0] in 'KCMY' else 'MLT')}-{m.group(2)}"
            fam = re.sub(r'[SLEX]$', '', code)
            return f'Samsung {fam}', f'Samsung {code} {col} toner'.replace('  ', ' ').strip()
        return None
    return None


LINES = ('Color imageCLASS', 'imageCLASS', 'PIXMA', 'i-SENSYS', 'MAXIFY', 'imagePROGRAF', 'SELPHY', 'Xpress')


def clean_model(brand, model):
    """Tidy retailer model names: drop "All-in-One"/"Printer" tails, put Canon/Samsung line names first."""
    m = re.sub(r'\s+(e-)?All-in-One\b.*$|\s+(Wireless\s+)?(Photo\s+)?Printer\b.*$|\s+Series$', '', model, flags=re.I).strip()
    for line in LINES:   # "MG3620 PIXMA" -> "PIXMA MG3620"
        if m.endswith(' ' + line):
            m = f'{line} {m[: -len(line) - 1]}'
            break
    return re.sub(r'\s+Series$', '', m)


def main():
    per_printer = defaultdict(lambda: defaultdict(set))   # (brand, model) -> family -> labels
    for r in csv.DictReader(open(SRC, encoding='utf-8', errors='replace'), delimiter='\t'):
        brand, model, desc = (r.get('Brand') or '').strip(), (r.get('Series') or '').strip(), (r.get('Description') or '').strip()
        if not (brand and model and desc):
            continue
        model = clean_model(brand, model)
        got = convert(brand, desc)
        if got:
            fam, label = got
            per_printer[(brand, model)][fam].add(label)
    # group printers that take exactly the same families into one set
    sets = defaultdict(lambda: {'models': set(), 'carts': set()})
    for (brand, model), fams in per_printer.items():
        key = (brand, tuple(sorted(fams)))
        sets[key]['models'].add(model)
        for labels in fams.values():
            sets[key]['carts'] |= labels

    def cart_order(c):
        xl = 'XL' in c.split(' ')[1] if len(c.split(' ')) > 1 else False
        order = ['Black', 'Photo Black', 'Matte Black', 'Tri-colour', 'Colour', 'Cyan', 'Magenta', 'Yellow']
        col = next((i for i, o in enumerate(order) if o in c), 99)
        return (xl, col, c)

    out = []
    for (brand, fams), s in sorted(sets.items()):
        names = []
        for f in fams:
            short = f.split(' ', 1)[1]
            names.append(short)
        name = f'{brand} ' + ' / '.join(names)
        if brand == 'HP' and all(re.fullmatch(r'\d+', n) for n in names) and any('XL' in c for c in s['carts']):
            name = f'{brand} ' + ' / '.join(f'{n} / {n}XL' if len(names) == 1 else n for n in names)
        out.append({'brand': brand, 'name': name, 'carts': sorted(s['carts'], key=cart_order), 'models': sorted(s['models'])})
    meta = {'source': 'kurcz/PrinterTonerDB (Apache-2.0), converted to UK cartridge codes by tools/build_ink_db.py',
            'printers': len(per_printer), 'sets': len(out)}
    json.dump({'meta': meta, 'sets': out}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(meta, 'bytes', os.path.getsize(OUT))


main()
