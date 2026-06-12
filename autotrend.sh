#!/bin/sh
# autotrend.sh — what's trending, without you guessing the phrases.
# Mines frequent content phrases from TODAY's corpus, then ranks them by how
# much better they fit TODAY's brain than YESTERDAY's (surprisal drop).
#
#   autotrend.sh today.brain yesterday.brain [today_corpus.txt]
#
# Candidates default to the today brain's own text. Output is sorted most-rising
# first, so the top lines are the day's emerging topics:
#
#   delta   new    old    phrase
#  +3.9    0.6    4.5   the election results
#  +3.1    0.9    4.0   voters at the polls
#  ...
#
# Env: TOPN=40 (how many to show), MINCOUNT=3 (min phrase freq today).
set -e
A=./atn
[ -x "$A" ] || { echo "build first: make"; exit 1; }
NEW="$1"; OLD="$2"; SRC="${3:-$1}"
[ -n "$OLD" ] || { echo "usage: autotrend.sh today.brain yesterday.brain [corpus.txt]"; exit 2; }
[ -f "$NEW" ] && [ -f "$OLD" ] && [ -f "$SRC" ] || { echo "files must exist"; exit 2; }
K="${TOPN:-40}"; MIN="${MINCOUNT:-3}"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

# 1. mine candidate phrases: most frequent 3-word "content" sequences in SRC
python3 - "$SRC" "$K" "$MIN" > "$tmp/cands" <<'PY'
import sys, re, collections
text = open(sys.argv[1], errors='ignore').read().lower()
K, MIN = int(sys.argv[2]), int(sys.argv[3])
stop = set("the a an of to and in is was on for at by it he she they them with that "
           "this as his her from were are be had has have not but you i we our their "
           "will would said say says one two said mr mrs to-day today".split())
words = re.findall(r"[a-z][a-z']{1,}", text)
tri = collections.Counter()
for i in range(len(words) - 2):
    g = words[i:i+3]
    if all(w in stop for w in g): continue         # skip pure boilerplate
    if sum(w in stop for w in g) >= 2: continue     # need >=2 content words
    tri[' '.join(g)] += 1
for ph, c in tri.most_common(K * 4):
    if c < MIN: break
    print(ph)
PY
head -n "$((K * 3))" "$tmp/cands" > "$tmp/c" && mv "$tmp/c" "$tmp/cands"
[ -s "$tmp/cands" ] || { echo "(no candidate phrases mined from $SRC)"; exit 0; }

# 2. score the candidates under each brain (one batch load each)
"$A" --score --brain "$NEW" < "$tmp/cands" | awk '{print $1}' > "$tmp/new"
"$A" --score --brain "$OLD" < "$tmp/cands" | awk '{print $1}' > "$tmp/old"

# 3. rank by rise (old surprisal - new surprisal), show the top K
printf ' %-7s %-6s %-6s  %s\n' delta new old phrase
paste "$tmp/new" "$tmp/old" "$tmp/cands" \
  | awk -F'\t' '{ d = $2 - $1; printf "%+7.3f %6.2f %6.2f  %s\n", d, $1, $2, $3 }' \
  | sort -rn | head -n "$K"
