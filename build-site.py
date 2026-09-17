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

COMMON = {
    # Generic nouns that a title-case title donates by accident: 'Salamis
    # Tablet' gave 'Tablet' to a card about the Emerald Tablet, and a
    # church building linked to Alonzo Church.
    # 'orrery' is a common noun AND the Earl of Orrery's title, so it linked
    # the man to the Greek machine named after him.
    'orrery', 'orreries',
    'tablet', 'tablets', 'mathematics', 'mechanical', 'church', 'churches',
    'islands', 'island', 'engine', 'engines', 'instrument', 'instruments',
'history','computer','computers','computing','machine','machines','technology',
          'network','memory','science','data','number','numbers','system','systems',
          'information','digital','future','world','time','work','film','video','part',
          'optical','guidance','teaching','curriculum','advantage','pioneers','overview',
          'mathematical','electronic','automatic','universal','american','national',
          'general','modern','physical','practical','personal'}

# A title that opens with a function word is a sentence, not a name. 'For
# Leibniz, binary was theology' was donating 'Leibniz' alongside the real
# Leibniz card, and two claimants means the ambiguity guard drops the term —
# so prose saying 'Leibniz' linked nowhere at all.
ARTICLES = {'the', 'a', 'an', 'of', 'on', 'in', 'at', 'to', 'by', 'for', 'from',
            'with', 'without', 'against', 'before', 'after', 'beyond', 'inside',
            'how', 'why', 'when', 'what', 'where', 'who', 'which',
            'and', 'but', 'or', 'not', 'no', 'it', 'its', 'this', 'that',
            'these', 'those', 'every', 'most', 'some', 'one', 'two', 'three',
            'early', 'first', 'new', 'late', 'other', 'another'}

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
    # The surname is the LAST word of the name run, not the second: taking the
    # second made 'Gottfried Wilhelm Leibniz' donate 'Wilhelm', so prose saying
    # 'Leibniz' linked to nothing. Articles are refused a run so 'The Analytical
    # Engine' cannot donate 'Engine'.
    person = re.match(r"(?:[A-Z][a-z\u00c0-\u024f]+\s+)+([A-Z][a-z\u00c0-\u024f]{3,})\b", base)
    if person and person.group(1).lower() not in COMMON \
       and base.split()[0].lower() not in ARTICLES:
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

GENERIC_AT = int(os.environ.get('DE_GENERIC_AT', 24))

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
        # A surname that shows up on many cards is a hub, not noise — that is
        # what the reader most wants to follow. The guard is here for generic
        # words, and capitalisation plus COMMON already catch those, so it sits
        # high and the per-card cap does the rest.
        if sum(1 for b in bodies if p.search(b)) > GENERIC_AT:
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

 {'t': 'The machine itself', 'd': '8 September 2026',
  'plates': [
    {'src': 'media/museum/679a6d2c4b72.webp',
     'alt': 'A brass and iron dividing engine on a wooden tripod frame, in a museum case',
     'cap': 'Dividing engine for making scales on instruments, late 1700s, '
            'modified 1800s. Made in England. Science Museum, London \u2014 object no. 1925-478.'},
    {'src': 'media/museum/c26441cd2826.webp',
     'alt': 'The toothed dividing plate of the engine seen from above',
     'cap': 'The dividing plate. A sextant or octant was fixed above it, and the '
            'engine\u2019s precision screw and ratchet stepped the divisions round.'},
    {'src': 'media/museum/1e1fe74a57e3.webp',
     'alt': 'Oil portrait of Jesse Ramsden seated beside a dividing engine',
     'cap': 'Jesse Ramsden (1735\u20131800), painted by Robert Home about 1790. A '
            'dividing engine stands at his hand. Lent by the Royal Society.'}],
  'hand': 'Photographs \u2014 William Edward Hahn, 8 September 2026',
  'b': 'Thirteen years after starting this archive, I stood in front of one.<br><br>'
       'A dividing engine does a single job: it marks an accurate scale. Before it, every '
       'degree on every sextant, octant and theodolite was stepped off by hand with '
       'dividers, and the instrument was only ever as good as one man\u2019s eye and his '
       'patience. The engine cut the divisions mechanically \u2014 repeatably, and finer '
       'than a hand can hold. <strong>Jesse Ramsden</strong> built the first in London in '
       'the 1770s, and the government\u2019s Board of Longitude paid him to hand the design '
       'to his competitors: scales meant sextants, sextants meant navigation, and navigation '
       'meant ships.<br><br>'
       'It is a machine for making other machines trustworthy \u2014 the precondition for '
       'measurement, and one almost nobody is taught.<br><br>'
       'Half an hour earlier, in the same building, I had been photographing Babbage\u2019s '
       'Difference Engine No. 2.'},

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
  'img': 'media/museum/c29f3069ef23.webp',
  'cred': 'Sinclair Cambridge pocket calculator, 1970s',
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

 {'t': 'Where to start', 'd': '', 'special': 'start', 'b': ''},
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


MUSEUM = ROOT / 'museum.json'

def attach_museum(stacks):
    """Photographs taken in a museum, joined onto the cards they show.

    These run after the Commons pass and overwrite it: a first-party
    photograph of the actual object beats a stock picture of one like it,
    and it carries no licence obligation but the one we owe ourselves —
    saying who took it and where.
    """
    if not MUSEUM.exists():
        return 0
    db = json.loads(MUSEUM.read_text(encoding='utf-8'))
    want = {}
    for rec in db.get('photos', {}).values():
        if rec.get('keep') and rec.get('web') and rec.get('card'):
            want[rec['card'].strip().lower()] = rec
    n = 0
    for st in stacks:
        for c in st['cards']:
            if c.get('kindc') == 'film':
                continue
            rec = want.get((c.get('t') or '').strip().lower())
            if not rec:
                continue
            c['img'] = rec['web']
            c['cred'] = rec.get('cap') or 'Science Museum, London'
            c.pop('credurl', None)
            n += 1
    return n



SITE = 'https://dividingengine.com'

def head_meta(n_cards, n_film):
    """Description and social card, generated from the archive.

    These were typed by hand once and went stale the moment the archive grew:
    the page claimed 1,266 cards and 734 films while serving 1,589 and 936.
    Anything that states a number about the data belongs in the build.
    """
    desc = (f'The history of computation as one timeline — {n_cards:,} cards, '
            f'{n_film:,} of them archival film, from 43,000 BCE to 2000.')
    title = 'Dividing Engine — the history of computation'
    img = f'{SITE}/assets/og.png'
    esc = lambda t: (t.replace('&', '&amp;').replace('"', '&quot;')
                      .replace('<', '&lt;').replace('>', '&gt;'))
    tags = [
        f'<meta name="description" content="{esc(desc)}">',
        f'<link rel="canonical" href="{SITE}/">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Dividing Engine">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{SITE}/">',
        f'<meta property="og:image" content="{img}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="Dividing Engine — the history of '
        'computation as one timeline">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(desc)}">',
        f'<meta name="twitter:image" content="{img}">',
        '<meta name="theme-color" content="#f2eee4">',
    ]
    return '\n'.join(tags)


def write_sitemap():
    (ROOT / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE}/</loc><changefreq>weekly</changefreq>'
        '<priority>1.0</priority></url>\n'
        '</urlset>\n', encoding='utf-8')



# ── ten films to start with ───────────────────────────────────────────────
# An archive of 865 films with no opinion about any of them is a card
# catalogue. These ten are an opinion: short where possible, weighted toward
# the machines the About page says nobody was taught, and ordered so that the
# first thing a visitor meets is 2,000 years old and the last went to the Moon.
PICKS = [
 ('antikythera-mechanism-the-ancient-computer-that',
  'The Antikythera Mechanism',
  'Geared bronze from a Greek shipwreck that predicted eclipses. '
  'The first computer is about two thousand years older than you were told.'),
 ('jaquet-droz-the-writer-automaton-from-1774-in-ac',
  'The Writer, an automaton of 1774',
  'A clockwork boy from 1774 dips his pen and writes any sentence you set '
  'on his cam stack. A program, and its storage, in brass.'),
 ('mk-57-gun-director',
  'Mk 57 Gun Director',
  'How a warship hit a moving target from a moving platform in a moving sea: '
  'a mechanical computer solving the problem continuously, while under fire.'),
 ('the-torpedo-data-computer-tdc',
  'The Torpedo Data Computer',
  'The firing triangle, solved without pause inside a submarine hull. '
  'Analogue computing with lives on both ends of the answer.'),
 ('navy-fire-control-computers',
  'Navy Fire Control Computers',
  'Differential equations, integrated by gears and cams, in a steel box. '
  'This is the computing that mattered most and was taught least.'),
 ('see-it-now-jay-w-forrester-and-the-whirlwind-com',
  'Murrow meets Whirlwind',
  'Edward R. Murrow visits Whirlwind in 1951 and asks what it is for. '
  'Core memory, real-time control, and live network television.'),
 ('perceptron',
  'Perceptron',
  'One minute of 1957 film showing the first neural network learning. '
  'Everything now called AI starts in this room.'),
 ('the-thinking-machine',
  'The Thinking Machine',
  'MIT, 1961, asking on camera whether a machine can think \u2014 '
  'sixty years before the question became a product category.'),
 ('impulse-propagtion-in-a',
  'Impulse Propagation in a Nerve Fiber',
  'A nerve impulse, filmed and explained as a signal problem. '
  'The neuron modelled as a circuit, which is how the metaphor began.'),
 ('computer-for-apollo',
  'Computer for Apollo',
  'The guidance computer that flew to the Moon, explained by the people who '
  'built it. Less memory than this page, and it did not fail.'),
]


def resolve_picks(stacks):
    """Locate each chosen film and hand the page its address and its reason."""
    where = {}
    for s in stacks:
        for n, c in enumerate(s['cards']):
            if c.get('kindc') == 'film' and c.get('slug'):
                where.setdefault(c['slug'], (s['id'], n, c))
    out, missing = [], []
    for slug, short, why in PICKS:
        hit = where.get(slug)
        if not hit:
            missing.append(slug); continue
        sid, n, c = hit
        if c.get('status') != 'live':
            missing.append(slug + ' (not playable)'); continue
        out.append({'to': f'{sid}/{n}', 't': short or c.get('t', ''), 'why': why,
                    'img': c.get('img', ''), 'dur': c.get('dur'), 'd': c.get('d', '')})
    if missing:
        print('  ! picks not placed: ' + ', '.join(missing))
    return out


def main():
    stacks = rb.parse((RECK / 'history-of-computation-master-list.md').read_text(encoding='utf-8'))
    films  = json.loads(ARCHIVE.read_text(encoding='utf-8'))['films']
    by_id  = {s['id']: s for s in stacks}

    # A film whose source is gone is still a record worth keeping — it stays in
    # archive.json so ./de can re-check it and so we know what was lost — but it
    # is not worth a reader's click. Blocked films are a different case: they
    # play perfectly well, just on YouTube's page rather than ours.
    lost = [f for f in films if f.get('status') == 'dead']
    films = [f for f in films if f.get('status') != 'dead']

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

    undated_stack = None
    if undated:
        undated.sort(key=lambda c: (c['t'] or '').lower())
        undated_stack = {
            'id': 'undated', 'kind': 'undated',
            'title': 'Undated Film',
            'sub': f'{len(undated)} films whose year is not yet known',
            'cards': undated,
        }

    n_dp = dphys_cards(stacks)
    # before crosslink: the About cards name real machines and should link to them
    stacks.append({'id': 'about', 'kind': 'apparatus', 'title': 'About',
                   'sub': 'what this is, and why you were not taught it',
                   'cards': ABOUT})
    n_link = crosslink(stacks)
    n_pic = attach_pictures(stacks)
    n_mus = attach_museum(stacks)
    # Contents, Index and Glossary are stacks like any other — reachable from Go,
    # addressable, in the Back chain. They were bolted on beside the card system;
    # a book's apparatus belongs inside the book.
    for sid, title, sub in (
            ('contents', 'Contents', 'the whole archive, in order'),
            ('index',    'Index',    'every name, alphabetically'),
            ('glossary', 'Glossary', 'terms, as the cards define them')):
        stacks.append({'id': sid, 'kind': 'apparatus', 'title': title, 'sub': sub,
                       'cards': [{'t': title, 'b': '', 'special': sid}]})
    # Last, and deliberately: these films are not on the timeline, and sitting
    # them between era 10 and the threads implied that they were.
    if undated_stack:
        stacks.append(undated_stack)
    n_cards = sum(len(s['cards']) for s in stacks)
    n_film  = sum(1 for s in stacks for c in s['cards'] if c.get('kindc') == 'film')
    # Contents, Index, Glossary and the timeline are all pure functions of the
    # cards, so the browser derives them at runtime. Shipping them cost 320 KB
    # and most of the parse time, for nothing the page did not already have.
    colls = json.loads(ARCHIVE.read_text(encoding='utf-8')).get('collections', {})
    data = json.dumps({'stacks': stacks,
                       'picks': resolve_picks(stacks),
                       'colls': {k: v.get('title', k) for k, v in colls.items()}},
                      ensure_ascii=False).replace('</', '<\\/')
    theme = THEME.read_text(encoding='utf-8')
    html = (TPL.read_text(encoding='utf-8')
              .replace('/*__THEME__*/', theme)
              .replace('/*__DATA__*/null', data)
              .replace('<!--__META__-->', head_meta(n_cards, n_film)))
    OUT.write_text(html, encoding='utf-8')
    write_sitemap()
    print(f'{OUT.name}: {len(html)//1024} KB — {n_cards} cards in {len(stacks)} stacks, '
          f'{n_film} with video, {n_pic} with a picture ({n_mus} photographed), {n_dp} from dataphys, '
          f'{n_link} cross-links '
          f'({placed} dated into eras, {len(undated)} undated, '
          f'{len(lost)} lost films withheld)')

if __name__ == '__main__':
    main()
