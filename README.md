# Dividing Engine

A history of computation as one timeline. Some cards have video.

```
build                build the site
build-site.py          merges both sources into index.html
theme.css              shared design tokens, inlined at build
assets/banner.png      the original 2015 banner, recovered from _source/
index.html           the site: 1,266 cards in 32 stacks, 734 of them film

the-reckoner/
  history-of-computation-master-list.md   the narrative — source of truth
  build.py                                markdown -> stacks (used by build-site)
  template.html                           the card UI

de                   the film tool (add / sync / check / tag / enrich)
archive.json           the film archive — source of truth
pics                 the picture tool (propose / review / fetch)
pics.json              which picture belongs to which card, and its licence
dataphys.json          catalogue entries from dataphys.org, to year 2000
media/cards/           archived pictures, WebP, ~90 KB each
media/                 title frames; media/yt/ holds YouTube thumbnails
_source/               the raw Wayback pull (deletable)
```

Two sources stay separate — prose in markdown, film in JSON — and are merged
into one stack of cards at build time. A film is a card that happens to play.

**You land on the films**, as the site always did: a contact sheet of all 734,
searchable and filterable by era. Clicking one does not open a page of its own —
it drops you into that film's place on the timeline, where you can walk forward
into whatever came next, film or not. **Films** in the menubar returns you to
the sheet.

The banner is the original: a gear-train technical drawing that shipped with the
2015 Sandvox theme, pulled back out of `_source/` and set to tile behind the
wordmark exactly as it did then.

Films are slotted into the era their year falls in, in date order among the
narrative cards, so Era 7 runs from the Atanasoff–Berry Computer through
*Electronics at Work* to Turing's Delilah without changing register.

**370 films have no year** and cannot sit on a timeline. They are a stack of
their own, *Undated Film*, until `./de year` or a hand edit dates them.

## Pictures

Every card should carry an image. Films already have a title frame; the
narrative cards get one from Wikimedia Commons and Wikipedia.

```
./pics propose      search both, gather up to 4 candidates per card
./pics review       open a picker in the browser — click the right one, or Skip
./pics fetch        download and compress everything chosen
./pics status       coverage and archive size
./pics recompress   re-encode from source at current settings
```

`review` is a local page showing every card beside its candidates as
thumbnails. Reading 500 filenames is slow; looking at 500 pictures is not.
Choices save as you click.

Images are archived locally — never hotlinked — resized to 860px and encoded
to WebP within a 150 KB budget, stepping quality down for the pathological
cases. About 90 KB each.

**Attribution is not optional.** Most of Commons is CC BY or CC BY-SA, which
requires crediting the photographer. The licence and author come down with the
file, live in `pics.json`, and render under the picture. A test fails if a
CC-BY image has no credit — which caught one that Commons had filed under
`Attribution` rather than `Artist`.

## The physical-visualization catalogue

`dataphys.json` holds 97 entries to the year 2000 from the
[List of Physical Visualizations](https://dataphys.org/list/), maintained by
Pierre Dragicevic and Yvonne Jansen. Each becomes a card in the era its date
falls in, carrying a short excerpt, the source line, and a link back to the
original entry. Six that the master list already covered — the Ishango bone,
Mesopotamian clay tokens, water clocks, Marshall Islands stick charts — were
dropped rather than duplicated. **No images are taken from dataphys.org**;
those go through `./pics` like every other card.

## Updating it

The loop is the same whatever you change:

```
# 1. change a source
./de add https://www.youtube.com/playlist?list=PL...     # or: edit the master list
./de sync                                               # or: ./de check

# 2. rebuild and prove it
./build
./test

# 3. ship
git add -A && git commit -m "..." && git push
```

The domain is registered at Namecheap but was delegated to Network Solutions
nameservers; switching to Namecheap BasicDNS and adding four `A` records on `@`
plus a `www` CNAME is what brought it up. `--deploy` resolves GitHub's Pages
addresses directly rather than trusting the local resolver, so a stale cache
cannot turn a real check into a skip.

`git push` runs `./test` first and refuses a failing build (`--no-verify` to
override). The same suite runs in CI on every push and pull request.

### The suite

```
./test              45 checks: archive data, master list, build output, assets
./test --browser    also drives the built page in Chromium
./test --net        also samples whether "live" films are still reachable
./test --deploy     also diffs the live site against the local build
./test --all        everything
```

Every check is something that has actually broken in this project at least
once — a film whose status disagreed with its sources, a card with an empty
title, a `--grid` token left behind when CSS moved to the theme, a template
placeholder that never got substituted, an asset path that broke when the page
moved directory. Neither `--net` nor `--deploy` runs in CI, because a bad
minute at YouTube is not a broken build.

Two checks tolerate reality rather than assert against it: 54 lost films have
no title frame, because they died before a thumbnail was ever fetched and
YouTube no longer serves one. The suite asserts that every *reachable* film has
a frame, and reports the 54 as a count.

## Adding films

`./de` is the archive tool. It takes YouTube links — single videos or whole
playlists — pulls metadata and thumbnails, and rebuilds the page.

```
./de add https://www.youtube.com/watch?v=qXdn6ynwpiI
./de add https://www.youtube.com/playlist?list=PLWmIsQcAzRkoGhGAGzwgnXbHnXi3Tlh8E
./de add <playlist-url> --collection hamming --title "Hamming Lectures"
./de build
```

Adding a playlist registers it as a **collection** and remembers the playlist id.
After that:

```
./de sync                    # re-pull every tracked playlist, add only what is new
./de sync --collection computers-101
```

`sync` is the "new videos show up automatically" path — put it on a cron and the
archive keeps itself current. Everything is keyed on the YouTube video id, so
adding the same video twice is a no-op and a video in two playlists becomes one
film in two collections.

Other commands:

```
./de check [--all] [--deep]      re-verify videos still play (see below)
./de enrich                      backfill duration/channel for --fast adds
./de title [--apply]             tidy scraped YouTube titles
./de year  [--apply]             propose years from video descriptions
./de list [--collection C] [--status live|blocked|dead]
./de collections
./de set <slug|videoid> --year 1966 --name "Better Title"
./de rm  <slug|videoid>
./de build                       (superseded — the site is built by ./build)
```

### How it decides things

**Years.** The scale needs a year per film, and YouTube upload dates are useless
for archival footage — a 1966 film uploaded in 2022 is not a 2022 film. So the
year is parsed out of the *title* (`(1943)`, `1966:`, `ca. 1941`) and left empty
otherwise. About 40% of a typical playlist yields a year that way; fix the rest
by hand with `./de set <id> --year 1966`.

**Liveness.** `check` runs an HTTP pass first: a thumbnail HEAD plus an oEmbed
call per video, 24 at a time. Measured over the whole archive, that separates
the states cleanly — every dead video has lost its thumbnail, every live one
keeps it. **734 films in ~20 seconds.**

The one thing HTTP cannot see is *public but will not embed*: 39 of 45 such
videos look identical to healthy ones. Only loading the real embed in a browser
distinguishes them, so that is `--deep`, and it costs ~17 minutes. Run the cheap
pass often and the deep pass rarely; the cheap pass never promotes a
browser-confirmed `embed-blocked` video back to live, since it cannot know.

`check` also records YouTube's own wording (`Private video`, `Video
unavailable`), so the page says **Made private** rather than a vague *signal
lost*.

**Titles.** `de title` normalises scraped titles — shouty caps runs, stray
wrapping quotes, `[4k, 60 fps]`, trailing `| Channel Name` — while preserving
real acronyms (IBM, RAND, AT&T, VPRI). It prints a diff and does nothing without
`--apply`, and the original is kept in `raw_title`, so it is reversible. It
leaves the hand-written original 106 alone unless you pass `--all`.

**Years, honestly.** `de year` reads video descriptions looking for an explicit
claim (*produced in 1962*, *ca. 1949*). On this archive it dated **20 of 317**
undated films, and several of those were wrong — a modern video *about* 1969
says 1969 in its description. A wrong year puts a film at the wrong place on the
scale, which is worse than no year, so nothing is applied without `--apply` and
review. Half this archive is undated and likely to stay that way; the scale now
gives those films their own graduation past a break rather than a bin under the
grid.

**Thumbnails** are downloaded to `media/yt/`, not hotlinked, so the page does not
depend on `i.ytimg.com` staying up.

### Dependencies

They live in `.venv/` in this directory, on Homebrew's Python 3.14. `de`
re-execs itself into that venv automatically, so `./de` works from any shell and
any working directory without activating anything.

```
/opt/homebrew/bin/python3.14 -m venv .venv
.venv/bin/python -m pip install yt-dlp playwright
.venv/bin/python -m playwright install chromium
```

**Do not run this on macOS system Python.** `/usr/bin/python3` is 3.9, which
yt-dlp has deprecated, and the last version that still supports it silently
truncates long playlists at ~100 entries — the "Dividing Engine" playlist came
back as 103 videos when it actually holds 546.

`de` now checks for this itself: YouTube reports how long a playlist is, and
ingest compares that against what actually arrived. A shortfall over 10% aborts
with instructions to upgrade yt-dlp (`--force` overrides); a smaller one warns,
since private or deleted entries account for a few.

Without playwright, `check` falls back to oEmbed and warns you that the result is
less accurate.

## Editing by hand

`archive.json` is the source of truth — plain JSON, one object per film. Edit it
directly and run `./de build`. `index.html` is a build artifact; changes made to
it are lost on the next build.

Don't edit it while a long command (`check --deep`, `enrich`, `year`) is running.
Those load at the start and save at the end, so a concurrent edit would be lost.
If it happens, `de` notices: it leaves `archive.json` alone, writes its own
result to `archive.json.new`, and exits 3 so you can compare the two.

## Using it

Films open in place, over the sheet, and each has its own address —
`index.html#1969-shakey` links straight to it. Back, forward and reload behave.
`/` focuses search, `←` `→` step through films, `Esc` closes.

The **Sheet / Index** toggle switches between the contact sheet and a
chronological list.

Note that YouTube refuses to load embeds from `file://`, so serve it rather than
double-clicking the file:

```
python3 -m http.server 8777
```

## The scale

The rule under the masthead is a graduated scale spanning 1922–2001 — one tick
per film at its year, taller marks at each decade with a count. It doubles as a
histogram: search or filter and the matching ticks light up, so you can see
which part of the century your query lands in. Hover a tick to identify the
film, click to open it, click a decade to filter.

A dividing engine is the instrument that cuts graduations onto scientific
instruments. The site's own index is one.

## Video liveness

Ten years is hard on embedded video. Every source was probed twice: first
through YouTube's oEmbed endpoint, then again by loading the real embed in a
headless browser — because oEmbed reports videos as fine that will not in fact
play. The browser result is what the site uses.

The original archive was then **re-sourced**: every dead film was searched for
on YouTube, the best surviving copy picked by title, era, duration and uploader,
and each candidate verified by loading its real embed in a browser before being
wired in. That took the losses among the original 106 from 28 down to 1.
Films added since are checked the same way by `./de check`.

| | |
|---|---|
| **293** | play inline — 27 of them restored copies |
| **28** | exist but refuse to embed — marked `OFF-SITE`, linked out |
| **3** | gone — marked `LOST` |

Of the original 106 films: 94 playable, 11 off-site, 1 lost.

Restored films carry a credit under the player naming the channel the copy came
from, so the substitution is visible rather than silent. Preference went to real
archive channels — AT&T Tech Channel, A/V Geeks, Prelinger Archives, Charlie
Dean Archives, Periscope Film, the official Computer Chronicles channel, and in
two cases the filmmakers themselves (Christopher Sykes for Feynman's *Fun to
Imagine*, Alfred Leitner for the physics films) — since those are least likely
to vanish next.

Two of the hardest were found by reading their own title cards: *More Power to
You* turned up on the Jam Handy Organization's channel once the card revealed
Jam Handy made it, and *The Laser: A Light Fantastic* was unfindable as "Lasers"
but obvious under its real title.

One film is still missing — **UHF TV**, whose card reads *Chicago UHF—W9XZC
1946*, footage of Zenith's experimental Chicago station. Nothing matching it is
on YouTube or archive.org. It keeps its page, its title frame and its place on
the scale, with searches against both plus the Wayback record of the dead URL —
a lead rather than a dead end.

The five `techchannel.att.com` embeds all died with that domain — but AT&T had
moved the same films to its own YouTube channel, so all five came back. Every
archive.org embed in the collection still works untouched, which is the argument
for archive.org.

## What changed from the original

Gone: Google Analytics, jQuery, the Sandvox "Carbone" theme, the fixed
`width=960` viewport, 110 near-identical HTML files, and the `_Resources` cruft.

Added: responsive layout, dark mode, search, decade and availability filtering,
keyboard navigation, and a verified liveness flag on every film.

Four pages Sandvox left behind after renames (`lasers.html`, `superfluid.html`,
`voder-speech-synthesizer.html`, `sign-language-telephone.html`) were duplicates
of surviving entries and were dropped.
