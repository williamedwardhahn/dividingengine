#!/usr/bin/env python3
"""
Build the site: one timeline, some cards have video.

Two sources stay separate — the markdown master list is the narrative, and
archive.json is the film archive — but they are merged into a single stack of
cards at build time. A film is a card that happens to play.
"""
import importlib.util, json, pathlib, re, sys

ROOT   = pathlib.Path(__file__).parent
RECK   = ROOT / 'the-reckoner'
THEME  = ROOT / 'theme.css'
TPL    = RECK / 'template.html'
OUT    = ROOT / 'index.html'
ARCHIVE= ROOT / 'archive.json'

# reuse the master-list parser rather than reimplementing it
spec = importlib.util.spec_from_file_location('reckoner_build', RECK / 'build.py')
rb = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(RECK))
_cwd = pathlib.Path.cwd()
import os; os.chdir(RECK)
spec.loader.exec_module(rb)
os.chdir(_cwd)

ERAS = [('era-6',1900,1940), ('era-7',1940,1955), ('era-8',1955,1975),
        ('era-9',1975,2005), ('era-10',2005,9999)]

YEAR = re.compile(r'(-?\d{1,5})')
def card_year(c):
    """Best-effort sort year for an existing card ('1951', 'c. 150–100 BCE')."""
    d = c.get('d') or ''
    if not d: return None
    neg = 'BCE' in d.upper() or 'BC' in d.upper()
    m = YEAR.search(d.replace(',', ''))
    if not m: return None
    try: v = int(m.group(1))
    except ValueError: return None
    return -v if neg else v

def era_of(y):
    for e, a, b in ERAS:
        if a <= y < b: return e
    return None

def film_card(f):
    src = (f.get('sources') or [{}])[0]
    c = {
        't': f.get('name') or f.get('title'),
        'b': '',
        'kindc': 'film',
        'slug': f['slug'],
        'status': f.get('status', 'live'),
    }
    if f.get('year'):  c['d'] = str(f['year'])
    if f.get('thumb'): c['img'] = f['thumb']
    if f.get('dur'):   c['dur'] = f['dur']
    if f.get('chan'):  c['by'] = f['chan']
    if src.get('id'):  c['v'] = src['id']
    if src.get('embed'): c['emb'] = src['embed']
    if src.get('url'):   c['url'] = src['url']
    if src.get('reason'): c['why'] = src['reason']
    if src.get('via'):    c['via'] = src['via']
    return c

def main():
    stacks = rb.parse((RECK / 'history-of-computation-master-list.md').read_text(encoding='utf-8'))
    films  = json.loads(ARCHIVE.read_text(encoding='utf-8'))['films']
    by_id  = {s['id']: s for s in stacks}

    placed, undated = 0, []
    for f in films:
        y = f.get('year')
        eid = era_of(y) if y else None
        if not eid:
            undated.append(film_card(f)); continue
        st = by_id.get(eid)
        if not st:
            undated.append(film_card(f)); continue
        card = film_card(f)
        # slot it in by year, after the last card that is no later
        pos = len(st['cards'])
        for i, c in enumerate(st['cards']):
            cy = card_year(c)
            if cy is not None and cy > y:
                pos = i; break
        st['cards'].insert(pos, card)
        placed += 1

    if undated:
        undated.sort(key=lambda c: (c['t'] or '').lower())
        i = max((n for n, s in enumerate(stacks) if s.get('kind') == 'era'), default=len(stacks)-1)
        stacks.insert(i + 1, {
            'id': 'undated', 'kind': 'era',
            'title': 'Undated Film',
            'sub': f'{len(undated)} films whose year is not yet known',
            'cards': undated,
        })

    n_cards = sum(len(s['cards']) for s in stacks)
    n_film  = sum(1 for s in stacks for c in s['cards'] if c.get('kindc') == 'film')
    data = json.dumps({'stacks': stacks}, ensure_ascii=False).replace('</', '<\\/')
    theme = THEME.read_text(encoding='utf-8')
    html = (TPL.read_text(encoding='utf-8')
              .replace('/*__THEME__*/', theme)
              .replace('/*__DATA__*/null', data))
    OUT.write_text(html, encoding='utf-8')
    print(f'{OUT.name}: {len(html)//1024} KB — {n_cards} cards in {len(stacks)} stacks, '
          f'{n_film} with video ({placed} dated into eras, {len(undated)} undated)')

if __name__ == '__main__':
    main()
