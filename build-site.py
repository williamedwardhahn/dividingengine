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

# ── cross-linking: what makes this a web rather than a slideshow ──────────
STOP_TITLE = {'overview', 'ideas', 'machines', 'memory', 'the signal', 'home'}
GENERIC = re.compile(r'^(the|a|an)\s+', re.I)

COMMON = {'history','computer','computers','computing','machine','machines','technology',
          'network','memory','science','data','number','numbers','system','systems',
          'information','digital','future','world','time','work','film','video','part'}

def link_terms(card):
    """Terms that should point at this card when they appear on another one.

    The full title, plus the distinctive names inside it — 'Jacquard loom
    (1804)' should also answer to 'Jacquard', because that is how other cards
    actually refer to it. Common words are excluded by name, and anything that
    turns out to match much of the corpus is dropped by the frequency guard in
    crosslink().
    """
    t = (card.get('t') or '').strip()
    if not t or t.lower() in STOP_TITLE:
        return []
    base = re.sub(r'\s*\([^)]*\)', '', t).strip(' .,:;\'"')
    base = re.split(r'\s+[-–—]\s+', base)[0].strip()
    out = set()
    if len(base) >= 9 and len(base.split()) >= 2 and base.lower() not in COMMON:
        out.add(base)
    # distinctive capitalised names: Jacquard, Antikythera, Pascaline, Leibniz
    for w in re.findall(r"\b([A-Z][a-z\u00c0-\u024f]{4,}(?:['’][a-z]+)?)\b", base):
        if w.lower() not in COMMON and not GENERIC.match(w):
            out.add(w)
    # a lone distinctive noun title: 'Quipus', 'Pascaline', 'Nomograms'
    if len(base.split()) == 1 and len(base) >= 7 and base.lower() not in COMMON:
        out.add(base)
    return [x for x in out if len(x) >= 6]

def link_label(stack, card):
    t = (card.get('t') or '').strip()
    if t.lower() in ('overview', ''):
        return re.sub(r'^(Era \d+|Thread [A-Z]):\s*', '', stack['title'])
    return t

def crosslink(stacks, cap=6):
    """Turn mentions of other cards into links, and record what points back."""
    # Only the narrative and catalogue cards are link targets. A film title is
    # not a concept — letting one own the word 'Telephony' produced hundreds of
    # links that pointed at a 1956 industrial short for no reason.
    index = []                                   # (term, stack_id, card_idx, title)
    for s in stacks:
        for n, c in enumerate(s['cards']):
            if c.get('kindc') == 'film':
                continue
            for term in link_terms(c):
                index.append((term, s['id'], n, link_label(s, c)))
    # longest terms first so 'Jacquard loom' wins over 'Jacquard'
    index.sort(key=lambda x: -len(x[0]))
    bodies = [(c.get('b') or '') for s_ in stacks for c in s_['cards']]
    pats = []
    for t, sid, n, ti in index:
        p = re.compile(r'(?<![\w-])' + re.escape(t) + r'(?![\w-])', re.I)
        if sum(1 for b in bodies if p.search(b)) > 8:      # too generic to mean anything
            continue
        pats.append((p, sid, n, ti))

    back = {}
    made = 0
    for s in stacks:
        for n, c in enumerate(s['cards']):
            body = c.get('b') or ''
            if not body:
                continue
            # only rewrite text outside existing tags and anchors
            parts = re.split(r'(<a\b[^>]*>.*?</a>|<[^>]+>)', body, flags=re.S)
            hits, seen = 0, set()
            for i, seg in enumerate(parts):
                if not seg or seg.startswith('<'):
                    continue
                for pat, sid, tn, ti in pats:
                    if hits >= cap:
                        break
                    if sid == s['id'] and tn == n:      # never link to itself
                        continue
                    key = (sid, tn)
                    if key in seen:
                        continue
                    new, k = pat.subn(
                        lambda m: f'<a class="xl" href="#{sid}/{tn}">{m.group(0)}</a>',
                        seg, count=1)
                    if k:
                        seg = new; hits += 1; seen.add(key); made += 1
                        back.setdefault(f'{sid}/{tn}', []).append(
                            {'to': f"{s['id']}/{n}", 't': link_label(s, c)})
                parts[i] = seg
            if hits:
                c['b'] = ''.join(parts)
                c['out'] = [{'to': f'{sid}/{tn}', 't': ti} for (sid, tn) in seen
                            for ti in [next((x[3] for x in index
                                             if x[1] == sid and x[2] == tn), '')]]
    for s in stacks:
        for n, c in enumerate(s['cards']):
            b = back.get(f"{s['id']}/{n}")
            if b:
                seen, uniq = set(), []
                for x in b:
                    if x['to'] not in seen:
                        seen.add(x['to']); uniq.append(x)
                c['in'] = uniq[:12]
    return made

def short_name(stack):
    """'Thread T: The Harmony Thread: music, myth...' -> 'The Harmony Thread'."""
    t = re.sub(r'^(Era \d+|Thread [A-Z])\s*[:—-]\s*', '', stack['title'])
    return t.split(':')[0].strip()

def apparatus(stacks):
    """The furniture of a book: contents, an index, and a glossary.

    All three are derived, not written twice — the index comes from the same
    terms that drive cross-linking, and each glossary entry is the opening
    sentence of the card that defines it.
    """
    contents, index, glossary = [], {}, []
    for s in stacks:
        if s['id'] == 'home':
            continue
        contents.append({
            'id': s['id'], 'kind': s.get('kind', 'thread'),
            'title': s['title'], 'short': short_name(s), 'sub': s.get('sub', ''),
            'n': len(s['cards']),
            'film': sum(1 for c in s['cards'] if c.get('kindc') == 'film'),
            'cards': [{'t': c.get('t') or '', 'd': c.get('d') or '',
                       'to': f"{s['id']}/{i}",
                       'film': 1 if c.get('kindc') == 'film' else 0}
                      for i, c in enumerate(s['cards'])],
        })
        for i, c in enumerate(s['cards']):
            if c.get('kindc') == 'film':
                continue
            for term in link_terms(c):
                index.setdefault(term, []).append(
                    {'to': f"{s['id']}/{i}", 'in': short_name(s)})
            body = re.sub(r'<[^>]+>', '', c.get('b') or '').strip()
            title = (c.get('t') or '').strip()
            if body and len(title) > 3 and title.lower() != 'overview':
                first = re.split(r'(?<=[.;])\s', body)[0].strip()
                if 24 <= len(first) <= 240:
                    glossary.append({'t': title, 'g': first,
                                     'to': f"{s['id']}/{i}", 'd': c.get('d') or ''})
    # index entries pointing at many cards are not index entries
    index = {k: v for k, v in sorted(index.items(), key=lambda kv: kv[0].lower())
             if len(v) <= 6}
    seen, gl = set(), []
    for g in sorted(glossary, key=lambda g: g['t'].lower()):
        k = g['t'].lower()
        if k in seen:
            continue
        seen.add(k); gl.append(g)
    return {'contents': contents, 'index': index, 'glossary': gl}

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
    n_link = crosslink(stacks)
    n_pic = attach_pictures(stacks)
    n_cards = sum(len(s['cards']) for s in stacks)
    n_film  = sum(1 for s in stacks for c in s['cards'] if c.get('kindc') == 'film')
    app = apparatus(stacks)
    data = json.dumps({'stacks': stacks, 'app': app},
                      ensure_ascii=False).replace('</', '<\\/')
    theme = THEME.read_text(encoding='utf-8')
    print(f'  apparatus: {len(app["index"])} index entries, '
          f'{len(app["glossary"])} glossary entries')
    html = (TPL.read_text(encoding='utf-8')
              .replace('/*__THEME__*/', theme)
              .replace('/*__DATA__*/null', data))
    OUT.write_text(html, encoding='utf-8')
    print(f'{OUT.name}: {len(html)//1024} KB — {n_cards} cards in {len(stacks)} stacks, '
          f'{n_film} with video, {n_pic} with a picture, {n_dp} from dataphys, '
          f'{n_link} cross-links '
          f'({placed} dated into eras, {len(undated)} undated)')

if __name__ == '__main__':
    main()
