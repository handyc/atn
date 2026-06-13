#!/bin/sh
# fetch-news.sh — pull current headlines+summaries from RSS/Atom feeds into the
# same one-article-per-line + .meta format the rest of the pipeline expects.
# This is the live-news counterpart to build-corpus.sh (which pulls the historic
# AmericanStories archive). Swap in any feeds you like via a feeds file.
#
#   fetch-news.sh OUTPREFIX [feeds.txt]
#   fetch-news.sh /data/2026W24/raw/20260613-0300 myfeeds.txt
#
# Produces:
#   OUTPREFIX.txt    one item per line: "Title. Summary"
#   OUTPREFIX.meta   one line per item: fetch-datetime <TAB> source-host <TAB> feed-title
#
# feeds.txt: one feed URL per line (blank lines / #comments ignored). If omitted,
# a small built-in default list is used — override it, those URLs will drift.
set -e
PREFIX="$1"; FEEDS="$2"
[ -n "$PREFIX" ] || { echo "usage: fetch-news.sh OUTPREFIX [feeds.txt]"; exit 2; }
NOW="$(date -u +%Y-%m-%dT%H:%M)"

# feed list: file arg, else $NEWS_FEEDS file, else built-in default
if [ -n "$FEEDS" ] && [ -f "$FEEDS" ]; then FEED_SRC="$(grep -vE '^\s*(#|$)' "$FEEDS")"
elif [ -n "$NEWS_FEEDS" ] && [ -f "$NEWS_FEEDS" ]; then FEED_SRC="$(grep -vE '^\s*(#|$)' "$NEWS_FEEDS")"
else FEED_SRC="https://feeds.bbci.co.uk/news/world/rss.xml
https://feeds.npr.org/1001/rss.xml
https://feeds.arstechnica.com/arstechnica/index
https://rss.cnn.com/rss/edition.rss"
fi

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
i=0
for url in $FEED_SRC; do
    curl -sL --max-time 30 -A "atn-fetch/1.0" "$url" > "$tmp/f$i.xml" 2>/dev/null || true
    i=$((i + 1))
done

python3 - "$NOW" "$PREFIX" "$tmp"/f*.xml <<'PY'
import sys, re, glob, html
from xml.etree import ElementTree as ET
from urllib.parse import urlparse

now, pref = sys.argv[1], sys.argv[2]
files = sys.argv[3:]
txt  = open(pref + ".txt",  "w")
meta = open(pref + ".meta", "w")

def strip(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)          # drop any HTML in summaries
    return re.sub(r"\s+", " ", s).strip()

def tag(e): return e.tag.rsplit("}", 1)[-1].lower()   # ignore XML namespaces

n = 0
for fn in files:
    try: root = ET.parse(fn).getroot()
    except Exception: continue
    # feed title + a host for provenance
    ftitle, host = "?", "?"
    for e in root.iter():
        if tag(e) == "title" and e.text: ftitle = strip(e.text)[:60]; break
    for e in root.iter():
        if tag(e) == "link":
            href = e.get("href") or e.text
            if href:
                host = urlparse(href).netloc or "?"; break
    # items (RSS <item>) or entries (Atom <entry>)
    for it in root.iter():
        if tag(it) not in ("item", "entry"): continue
        title = desc = ""
        for c in it:
            t = tag(c)
            if t == "title" and c.text: title = strip(c.text)
            elif t in ("description", "summary", "content") and c.text and not desc:
                desc = strip(c.text)
        line = (title + ". " + desc).strip() if desc else title
        if len(line) >= 40:
            txt.write(line + "\n")
            meta.write(f"{now}\t{host}\t{ftitle}\n")
            n += 1
print(f"  {n} items -> {pref}.txt + {pref}.meta", file=sys.stderr)
PY
