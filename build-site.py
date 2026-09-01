#!/usr/bin/env python3
"""
Build the site: one timeline, some cards have video.

Two sources stay separate — the markdown master list is the narrative, and
archive.json is the film archive — but they are merged into a single stack of
cards at build time. A film is a card that happens to play.
"""
import hashlib, importlib.util, json, pathlib, re, sys

ROOT   = pathlib.Path(__file__).parent
RECK   = ROOT / 'the-reckoner'
THEME  = ROOT / 'theme.css'
TPL    = RECK / 'template.html'
OUT    = ROOT / 'index.html'
ARCHIVE= ROOT / 'archive.json'
PICS   = ROOT / 'pics.json'
DPHYS  = ROOT / 'dataphys.json'

# reuse the master-list parser rather than reimplementing it
spec = importlib.util.spec_from_file_location('reckoner_build', RECK / 'build.py')
rb = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(RECK))
_cwd = pathlib.Path.cwd()
import os; os.chdir(RECK)
spec.loader.exec_module(rb)
os.chdir(_cwd)

ALL_ERAS = [('era-1',-99999,-3000), ('era-2',-3000,500), ('era-3',500,1500),
            ('era-4',1500,1800), ('era-5',1800,1900), ('era-6',1900,1940),
            ('era-7',1940,1955), ('era-8',1955,1975), ('era-9',1975,2005),
            ('era-10',2005,9999)]

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

def dphys_cards(stacks):
    """Add the physical-visualization catalogue as cards, credited and linked.

    The entries are facts (what the artifact is, when); the wording is theirs, so
    each card carries a short excerpt, the source line, and a link back. No
    images are taken from dataphys.org — those go through ./pics like any other.
    """
    if not DPHYS.exists():
        return 0
    doc = json.loads(DPHYS.read_text(encoding='utf-8'))
    src, by_id, n = doc['source'], {s['id']: s for s in stacks}, 0
    for e in doc['entries']:
        y = e['year']
        eid = next((i for i, a, b in ALL_ERAS if a <= y < b), None)
        st = by_id.get(eid)
        if not st:
            continue
        card = {
            't': e['title'],
            'd': (f"c. {abs(y):,} BCE" if y < 0 else str(y)),
            'b': (e['text'] + f' <span class="src">&mdash; <a href="{e["href"]}" '
                  f'target="_blank" rel="noopener">{src["name"]}</a>, '
                  f'{src["by"]}</span>'),
            'kindc': 'dataphys',
        }
        pos = len(st['cards'])
        for i, c in enumerate(st['cards']):
            cy = card_year(c)
            if cy is not None and cy > y:
                pos = i; break
        st['cards'].insert(pos, card)
        n += 1
    return n

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

def pic_key(stack_id, title):
    return hashlib.sha1(f'{stack_id}|{title}'.encode()).hexdigest()[:12]

def attach_pictures(stacks):
    """Join the picture archive onto the narrative cards. Attribution rides
    along with the image because most of Commons is CC BY or CC BY-SA."""
    if not PICS.exists():
        return 0
    pics = json.loads(PICS.read_text(encoding='utf-8'))
    n = 0
    for s in stacks:
        for c in s['cards']:
            if c.get('kindc') == 'film' or not c.get('t'):
                continue
            p = pics.get(pic_key(s['id'], c['t']))
            if not p or not p.get('img'):
                continue
            if not (ROOT / p['img']).exists():
                continue
            c['img'] = p['img']
            cred = p.get('by') or p.get('via') or ''
            if cred or p.get('lic'):
                c['cred'] = ' · '.join(x for x in (cred, p.get('lic')) if x)[:90]
            if p.get('page'):
                c['credurl'] = p['page']
            n += 1
    return n

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

    n_dp = dphys_cards(stacks)
    n_pic = attach_pictures(stacks)
    n_cards = sum(len(s['cards']) for s in stacks)
    n_film  = sum(1 for s in stacks for c in s['cards'] if c.get('kindc') == 'film')
    data = json.dumps({'stacks': stacks}, ensure_ascii=False).replace('</', '<\\/')
    theme = THEME.read_text(encoding='utf-8')
    html = (TPL.read_text(encoding='utf-8')
              .replace('/*__THEME__*/', theme)
              .replace('/*__DATA__*/null', data))
    OUT.write_text(html, encoding='utf-8')
    print(f'{OUT.name}: {len(html)//1024} KB — {n_cards} cards in {len(stacks)} stacks, '
          f'{n_film} with video, {n_pic} with a picture, {n_dp} from dataphys '
          f'({placed} dated into eras, {len(undated)} undated)')

if __name__ == '__main__':
    main()
