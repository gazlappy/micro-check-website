"""Build src/assets/ink-official.json, the manufacturer-sourced UK printer -> cartridge list used by the ink finder.

Inputs (collected from the makers' own UK websites, see THIRD_PARTY_NOTICES.md):
  tools/data/hp-official-uk.json      HP support table, Europe column        {"sets": [{"c": [carts], "m": [models]}]}
  tools/data/canon-official-uk.json   Canon UK store, cartridges per model   {"models": {model: [product names]}}
  tools/data/epson-official-uk.json   Epson UK, compatible printers per ink  {"inks": [{"t": title, "names": [...], "p": [printers]}]}

The ink finder searches this file before the older PrinterTonerDB conversion (ink-db.json).

usage: python tools/build_official_ink.py
"""
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'tools', 'data')
OUT = os.path.join(ROOT, 'src', 'assets', 'ink-official.json')

COLOURS = [('light light black', 'Light Light Black'), ('light black', 'Light Black'), ('m black', 'Matte Black'),
           ('photo blue', 'Photo Blue'), ('pigment black', 'Black'), ('photo black', 'Photo Black'),
           ('matte black', 'Matte Black'), ('light cyan', 'Light Cyan'), ('light magenta', 'Light Magenta'),
           ('c/m/y', 'Colour'), ('tri-colour', 'Tri-colour'), ('black', 'Black'), ('cyan', 'Cyan'),
           ('magenta', 'Magenta'), ('yellow', 'Yellow'), ('grey', 'Grey'), ('red', 'Red'), ('colour', 'Colour')]
COLOUR_ORDER = ['Black', 'Photo Black', 'Matte Black', 'Tri-colour', 'Colour', 'Cyan', 'Magenta', 'Yellow']


def colour_of(text):
    low = text.lower()
    return next((v for k, v in COLOURS if k in low), '')


def cart_order(c):
    return ('XL' in c, next((i for i, o in enumerate(COLOUR_ORDER) if c.endswith(o) or f' {o} ' in c), 99), c)


def group(per_printer, brand):
    """per_printer: model -> {family: set(labels)}. Printers taking the same families share one set."""
    sets = defaultdict(lambda: {'models': set(), 'carts': set()})
    for model, fams in per_printer.items():
        if not fams:
            continue
        s = sets[tuple(sorted(fams))]
        s['models'].add(model)
        for labels in fams.values():
            s['carts'] |= labels
    out = []
    for fams, s in sorted(sets.items()):
        fams = sorted(fams, key=lambda f: (not f.startswith('PG'), f))   # Canon black (PG-560) before colour (CL-561)
        name = ' / '.join(fams[:4])
        if len(fams) == 1 and any(f'{fams[0]}XL' in c or f'/ {fams[0].split("-")[-1]}XL' in c for c in s['carts']):
            name = f'{fams[0]} / {fams[0].split("-")[-1]}XL'
        out.append({'brand': brand, 'name': f'{brand} {name}',
                    'carts': sorted(s['carts'], key=cart_order), 'models': sorted(s['models'])})
    return out


def split_titles(title):
    """'HP Color LaserJet Pro 3200, MFP 3300' -> two models; '3001-3008, 3001e-3008e' keeps the first range."""
    parts = [p.strip() for p in title.split(',')]
    first = parts[0]
    line = re.split(r'\s(?=\S*\d)', first, maxsplit=1)[0]
    line = re.sub(r'\s+MFP$', '', line)
    out = [first]
    for p in parts[1:]:
        if re.fullmatch(r'\d+[a-z]*\s*-\s*\d+[a-z]*', p):
            continue
        out.append(p if p.startswith('HP ') else f'{line} {p}')
    return out


def hp():
    data = json.load(open(os.path.join(DATA, 'hp-official-uk.json'), encoding='utf-8'))
    per = defaultdict(dict)
    for s in data['sets']:
        fams = defaultdict(set)
        for c in s['c']:
            m = re.match(r'HP (\w+)', c)
            if not m:
                continue
            code = m.group(1)
            t = re.fullmatch(r'([A-Z]*\d+)(A|X|XC)', code)
            fam = t.group(1) + 'A' if t else re.sub(r'(XXL|XL|e)$', '', code)
            fams[fam].add(c.replace(', ', ' / '))
        for f, labels in fams.items():   # drop bare "HP 303" when "HP 303 Black" etc. are listed
            if len(labels) > 1:
                labels -= {l for l in labels if re.fullmatch(r'HP \w+', l)}
        for title in s['m']:
            for model in split_titles(title):
                model = re.sub(r'^HP\s+', '', model).strip()
                for f, labels in fams.items():
                    per[model].setdefault(f, set()).update(labels)
    return group(per, 'HP')


CANON_CODE = re.compile(r'\b(PGI|PG|CLI|CL|GI)-?\s?(\d{2,4})\s?(PGBK|BK|PB|GY|C|M|Y|R)?\s?(XXL|XL)?\b')
CANON_TONER = re.compile(r'\b(\d{3})\s?(H|L|BK|C|M|Y)?\b|\b(E\d{2}|FX\d{1,2}|EP-\d{2}|CRG T)\b')


def canon():
    data = json.load(open(os.path.join(DATA, 'canon-official-uk.json'), encoding='utf-8'))['models']
    per = defaultdict(dict)
    for model, names in data.items():
        if model in ('Ink Cartridges', 'Toner Cartridges'):
            continue
        for n in names:
            if re.search(r'drum|maintenance', n, re.I):
                continue
            col = colour_of(n)
            m = CANON_CODE.search(n)
            if m:
                pre, num, sub, size = m.group(1), m.group(2), m.group(3) or '', m.group(4) or ''
                fam = f'{pre}-{num}'
                if pre == 'GI':
                    label = f'Canon {fam} {col} bottle'
                else:   # the store lists XL sizes; the standard size takes the same slot
                    label = f'Canon {fam} / {num}XL {col}'.strip()
            else:
                m = CANON_TONER.search(n.replace('Canon i-SENSYS', 'Canon'))
                if not m:
                    continue
                if m.group(1):
                    fam = m.group(1)
                    label = f'Canon {fam}{"H" if m.group(2) == "H" else ""} {col} toner'.replace('  ', ' ')
                else:
                    fam = m.group(3)
                    label = f'Canon {fam} toner'
            per[model].setdefault(fam, set()).add(label)
    return group(per, 'Canon')


def epson():
    path = os.path.join(DATA, 'epson-official-uk.json')
    if not os.path.exists(path):
        return []
    data = json.load(open(path, encoding='utf-8'))
    per = defaultdict(dict)
    for ink in data['inks']:
        if not ink.get('p') or not re.search(r'ink', ink.get('t') or '', re.I) and ink['f'].isdigit() and 'EcoTank' not in (ink.get('t') or ''):
            continue
        fam = ink['f'].upper()
        code = re.compile(rf'(?<![\dA-Z]){fam}(\d{{0,2}})(XXL|XL|L)?\b', re.I)
        labels = set()
        for n in ink['names']:
            if re.search(r'multipack|series|easymail|value pack|\bpack\b', n, re.I):
                continue
            m = code.search(n)
            col = colour_of(n)
            if not m or not col:
                continue
            kind = ' bottle' if re.search(r'ecotank|bottle', n, re.I) else ''
            labels.add(f'Epson {fam}{m.group(1)}{(m.group(2) or "").upper()} {col}{kind}')
        if not labels:
            labels.add(f'Epson {fam} EcoTank bottles, all colours' if 'EcoTank' in ink['t'] else f'Epson {fam} ink, all colours')
        for p in ink['p']:
            p = re.sub(r'^Epson\s+|\s+Unlimited$|\s+(A\d\+?\s+)?(Wireless\s+)?(Inkjet\s+)?Printer$|\s+WE$', '', p).strip()
            if not re.search(r'\d', p):   # "Booklet finisher" and other accessories
                continue
            per[p].setdefault(fam, set()).update(labels)
    return group(per, 'Epson')


def main():
    sets = hp() + canon() + epson()
    meta = {'source': 'HP, Canon and Epson UK websites, read October 2026; built by tools/build_official_ink.py',
            'printers': sum(len(s['models']) for s in sets), 'sets': len(sets)}
    json.dump({'meta': meta, 'sets': sets}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(meta, 'bytes', os.path.getsize(OUT))


main()
