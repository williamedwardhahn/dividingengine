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
    if f.get('collections'): c['coll'] = f['collections']
    return c

# ── cross-linking: what makes this a web rather than a slideshow ──────────
STOP_TITLE = {'overview', 'ideas', 'machines', 'memory', 'the signal', 'home'}
GENERIC = re.compile(r'^(the|a|an)\s+', re.I)

COMMON = {'history','computer','computers','computing','machine','machines','technology',
          'network','memory','science','data','number','numbers','system','systems',
          'information','digital','future','world','time','work','film','video','part',
          'optical','guidance','teaching','curriculum','advantage','pioneers','overview',
          'mathematical','electronic','automatic','universal','american','national',
          'general','modern','physical','practical','personal'}

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
    # What prose actually says is the surname — 'Babbage', 'Oughtred', 'Napier'.
    # Taking every capitalised word made 'William Oughtred: slide rule' donate
    # 'William'; taking only the leading word gave almost nothing.
    person = re.match(r"[A-Z][a-z\u00c0-\u024f]+\s+([A-Z][a-z\u00c0-\u024f]{3,})\b", base)
    if person and person.group(1).lower() not in COMMON:
        out.add(person.group(1))
    elif re.match(r"[A-Z][a-z\u00c0-\u024f]{8,}\b", base):
        w = re.match(r"([A-Z][a-z\u00c0-\u024f]{8,})\b", base).group(1)
        if w.lower() not in COMMON:
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
        if not t.strip():
            continue
        # A one-word term is only a link where it is capitalised as a name.
        # Matching case-insensitively let a card called 'Guidance' claim every
        # lowercase 'guidance', and 'Teaching' every 'teaching'.
        flags = 0 if ' ' not in t else re.I
        p = re.compile(r'(?<![\w-])' + re.escape(t) + r'(?![\w-])', flags)
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
            parts = re.split(r'(<a\\b[^>]*>.*?</a>|<[^>]+>)', body, flags=re.S)
            hits, seen = 0, set()
            for i, seg in enumerate(parts):
                if not seg or seg.startswith('<'):
                    continue
                # Collect every candidate first, then apply the non-overlapping
                # ones in one pass. Substituting as we went let a second term
                # match inside the anchor the first had just inserted, which
                # produced nested <a><a>…</a></a> and an empty outer link.
                cands = []
                for rank, (pat, sid, tn, ti) in enumerate(pats):
                    if sid == s['id'] and tn == n:
                        continue
                    if (sid, tn) in seen:
                        continue
                    m = pat.search(seg)
                    if m:
                        # rank breaks ties so the sort never compares Match objects
                        cands.append((m.start(), -(m.end() - m.start()), rank, m, sid, tn))
                cands.sort(key=lambda x: x[:3])
                out, last, used = [], 0, set()
                for _start, _neg, _rank, m, sid, tn in cands:
                    if hits >= cap or m.start() < last:
                        continue
                    if (sid, tn) in used:
                        continue
                    out.append(seg[last:m.start()])
                    out.append(f'<a class="xl" href="#{sid}/{tn}">{m.group(0)}</a>')
                    last = m.end()
                    used.add((sid, tn)); seen.add((sid, tn)); hits += 1; made += 1
                    back.setdefault(f'{sid}/{tn}', []).append(
                        {'to': f"{s['id']}/{n}", 't': link_label(s, c)})
                if out:
                    out.append(seg[last:])
                    parts[i] = ''.join(out)
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


ABOUT = [
 {'t': 'About', 'd': 'since 2013',
  'b': 'Dividing Engine is an archive of the history of computation, assembled by '
       '<strong>William Edward Hahn, PhD</strong>, who began it in 2013 to put automation '
       'and artificial intelligence back into historical context.<br><br>'
       'He is an Associate Professor of Mathematical Sciences at Florida Atlantic '
       'University, and founder and director of the <strong>Machine Perception and '
       'Cognitive Robotics Laboratory</strong>, which he co-founded there in 2014. His '
       'doctorate is in sparse coding and compressed sensing; before that, neural networks. '
       'He has been collecting this material for about as long as he has been running the lab.<br><br>'
       'The premise has not changed since the beginning: <em>you cannot see where a '
       'technology is going without knowing where it has been.</em> Everything here — '
       'the films, the cards, the timeline — exists to make that history visible to '
       'people who were never shown it.'},

 {'t': 'Why almost none of this was taught to you', 'd': '',
  'b': 'The history of computing falls into a gap between two departments, and neither one '
       'reaches in.<br><br>'
       'It is <strong>too old for technical training</strong>, which starts at the current '
       'framework and works forward — a course on machine learning begins at the point where '
       'the present toolchain begins, and everything earlier is a charming anecdote if it is '
       'mentioned at all. And it is <strong>too new to be treated as history</strong>, a '
       'discipline still deciding what to make of the twentieth century.<br><br>'
       'So it is taught almost nowhere. And what fell into that gap is not the footnotes. '
       'It is most of the important ideas.'},

 {'t': 'Have you heard of any of these?', 'd': '',
  'b': 'Water computers. Machines built to simulate nerve impulses and model neurons in '
       'brass and oil. Torpedo inertial guidance. Optical bomb sights. Fire-control gun '
       'directors solving differential equations continuously while the ship rolled '
       'underneath them.<br><br>'
       'No?<br><br>'
       'There is a reason, and it is not that these were minor. <strong>Military advantage '
       'is not a curriculum.</strong> The computing that mattered most was, for decades, the '
       'computing nobody was told about — and the silence outlived the secrecy that caused '
       'it. The machines were declassified. The teaching never caught up.<br><br>'
       'They are all in here. Start with Naval fire-control computers, Bombsight oaths, '
       'the Torpedo Data Computer, McCulloch &amp; Pitts, or the tide-predicting machines, '
       'and follow the links out.'},

 {'t': 'You were told not to use a calculator', 'd': '',
  'b': 'Calculators are not a modern convenience. They are <strong>four hundred years '
       'old</strong>. Schickard built one in 1623, Pascal in 1642, Leibniz in 1673. By the '
       'time you were told to put yours away, every consequential calculation on earth — '
       'navigation, ballistics, actuarial tables, spaceflight — had been done by machine '
       'for generations, and in many cases by rooms of people organised to work like one.<br><br>'
       'The picture you were given, of mathematics as something a person does alone with a '
       'pencil, is not a description of how mathematics has ever been done at scale. It is a '
       'misdirection — away from the tools, away from who had them, and away from what '
       'having them was worth.<br><br>'
       'That is what this archive is for.'},
]

def short_name(stack):
    """'Thread T: The Harmony Thread: music, myth...' -> 'The Harmony Thread'."""
    t = re.sub(r'^(Era \d+|Thread [A-Z])\s*[:—-]\s*', '', stack['title'])
    return t.split(':')[0].strip()

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
    # before crosslink: the About cards name real machines and should link to them
    stacks.append({'id': 'about', 'kind': 'apparatus', 'title': 'About',
                   'sub': 'what this is, and why you were not taught it',
                   'cards': ABOUT})
    n_link = crosslink(stacks)
    n_pic = attach_pictures(stacks)
    n_cards = sum(len(s['cards']) for s in stacks)
    n_film  = sum(1 for s in stacks for c in s['cards'] if c.get('kindc') == 'film')
    # Contents, Index and Glossary are stacks like any other — reachable from Go,
    # addressable, in the Back chain. They were bolted on beside the card system;
    # a book's apparatus belongs inside the book.
    for sid, title, sub in (
            ('contents', 'Contents', 'the whole archive, in order'),
            ('index',    'Index',    'every name, alphabetically'),
            ('glossary', 'Glossary', 'terms, as the cards define them')):
        stacks.append({'id': sid, 'kind': 'apparatus', 'title': title, 'sub': sub,
                       'cards': [{'t': title, 'b': '', 'special': sid}]})
    # Contents, Index, Glossary and the timeline are all pure functions of the
    # cards, so the browser derives them at runtime. Shipping them cost 320 KB
    # and most of the parse time, for nothing the page did not already have.
    colls = json.loads(ARCHIVE.read_text(encoding='utf-8')).get('collections', {})
    data = json.dumps({'stacks': stacks,
                       'colls': {k: v.get('title', k) for k, v in colls.items()}},
                      ensure_ascii=False).replace('</', '<\\/')
    theme = THEME.read_text(encoding='utf-8')
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
