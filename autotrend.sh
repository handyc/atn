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
A="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/atn"
[ -x "$A" ] || { echo "build first: make"; exit 1; }
NEW="$1"; OLD="$2"; SRC="${3:-$1}"
[ -n "$OLD" ] || { echo "usage: autotrend.sh today.brain yesterday.brain [corpus.txt]"; exit 2; }
[ -f "$NEW" ] && [ -f "$OLD" ] && [ -f "$SRC" ] || { echo "files must exist"; exit 2; }
K="${TOPN:-40}"; MIN="${MINCOUNT:-3}"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

# 1. mine candidate phrases (most frequent content trigrams) -> "count<TAB>phrase"
python3 - "$SRC" "$K" "$MIN" > "$tmp/cf" <<'PY'
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
    print(f"{c}\t{ph}")
PY
head -n "$((K * 3))" "$tmp/cf" > "$tmp/c" && mv "$tmp/c" "$tmp/cf"
[ -s "$tmp/cf" ] || { echo "(no candidate phrases mined from $SRC)"; exit 0; }
cut -f1 "$tmp/cf" > "$tmp/cnt"
cut -f2 "$tmp/cf" > "$tmp/cands"

# 2. score the candidates under each brain (one batch load each)
"$A" --score --brain "$NEW" < "$tmp/cands" | awk '{print $1}' > "$tmp/new"
"$A" --score --brain "$OLD" < "$tmp/cands" | awk '{print $1}' > "$tmp/old"

# 3. rank by a FREQUENCY-WEIGHTED rise: (old-new) * log10(freq+1), so a phrase
#    that is both frequent today and newly fitting beats a rare-but-rising one.
printf ' %-7s %-7s %-5s %-5s %-5s  %s\n' score rise freq new old phrase
paste "$tmp/new" "$tmp/old" "$tmp/cnt" "$tmp/cands" \
  | awk -F'\t' '{ d=$2-$1; w=d*log($3+1)/log(10);
                  printf "%+7.2f %+7.3f %5d %5.2f %5.2f  %s\n", w, d, $3, $1, $2, $4 }' \
  | sort -rn | head -n "$K"
