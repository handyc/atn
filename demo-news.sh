#!/bin/sh
# demo-news.sh — ONE command, from a clean clone to a working result.
# Builds atn, streams a slice of 1920-1940 news from the AmericanStories archive,
# cleans it, evolves a population of GA brains over it (time-boxed), then runs
# example queries on the result. Tuned to finish in well under 10 minutes.
#
#   ./demo-news.sh [MINUTES]      # total time target, default 8
#
# Needs: a C compiler + make, python3 (stdlib only), curl. No pre-existing data.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
BUDGET="${1:-8}"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }
elapsed() { echo "[t+$(( $(date +%s) - T0 ))s]"; }

say "atn news demo  (target ~${BUDGET} min)"

# 0. build the binary if needed
[ -x ./atn ] || { echo "$(elapsed) building atn ..."; make >/dev/null; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. fetch a spread of years across 1920-1940 (each capped + hard-timeboxed)
say "fetch — streaming 1920-1940 news from AmericanStories"
: > "$WORK/corpus.txt"
for Y in 1921 1926 1931 1936 1940; do
    timeout 120 ./build-corpus.sh "$Y" "$WORK/$Y" 5000000 >/dev/null 2>&1 || true
    if [ -f "$WORK/$Y.txt" ]; then
        cat "$WORK/$Y.txt" >> "$WORK/corpus.txt"
        printf '  %s  %6s articles   %s\n' "$Y" "$(wc -l < "$WORK/$Y.txt")" "$(elapsed)"
    else
        printf '  %s  (skipped)\n' "$Y"
    fi
done
RAW=$(wc -l < "$WORK/corpus.txt")
[ "$RAW" -gt 100 ] || { echo "too little data fetched ($RAW lines) — network issue?"; exit 1; }
echo "  total: $RAW articles, $(wc -c < "$WORK/corpus.txt") bytes  $(elapsed)"

# 2. clean / dedup for the pipeline
say "prep — clean + dedup (training-free)"
./atn --prep "$WORK/corpus.txt" > "$WORK/clean.txt" 2> "$WORK/prep.log" || true
sed -n 's/^atn: /  /p' "$WORK/prep.log"; echo "  $(elapsed)"

# 3. evolve a population, time-boxed to ~45% of the budget
GA_MIN=$(awk "BEGIN{printf \"%.1f\", $BUDGET*0.45}")
say "evolve — GA population (content loci, evolving n-gram orders) for ~${GA_MIN} min"
rm -rf demo-run
python3 atn-ga.py run --corpus "$WORK/clean.txt" --out demo-run \
    --pop 24 --minutes "$GA_MIN" --chunk-kb 4 --locus content --evolve-orders \
    --span-mb 0.4 --eval-frac 0.05 2>&1 | grep -E "chunks=|content index|gen|budget|honesty|best\]"
echo "  $(elapsed)"

# 4. example queries on the evolved population
say "classify — route each line to the expert that fits it best"
echo "  (each headline goes to whichever expert finds it least 'surprising')"
printf '%s\n' \
  "the president addressed congress on the new tariff bill" \
  "the home team won the championship in the ninth inning" \
  "shares fell sharply on the stock exchange today" \
  "the orchestra performed a symphony at the concert hall" \
  | python3 atn-ga.py classify --out demo-run

say "lightup — route ONE query and SEE what the chosen expert is about"
echo "  (reads back real words + a sample line from the expert's own articles)"
python3 atn-ga.py lightup --out demo-run "the home team won the baseball game in the ninth inning"

say "novelty — tell in-period news from out-of-distribution text"
echo "  (flags text no expert recognises: off-topic, anachronistic, or garbled)"
printf '%s\n' \
  "a fire broke out downtown late last night" \
  "stream the viral selfie to your influencer hashtag feed" \
  "qx zzt 9999 ;;;; vbnm kkkk" \
  | python3 atn-ga.py novelty --out demo-run

say "mixture — use the whole POPULATION as one language model"
echo "  (blends every expert per character; should beat any single expert)"
python3 atn-ga.py mixture --out demo-run 2>&1 | grep -E "experts,|single|oracle|fixed-share|Bayes|beats|means:|character|complementary|POPULATION" || true

say "done in $(( $(date +%s) - T0 ))s"

cat <<'GUIDE'

────────────────────────────────────────────────────────────────────
WHAT YOU JUST SAW
  We grew a POPULATION of tiny "expert" models, each trained on one
  slice of 1920-1940 newspaper text. A genetic algorithm decided which
  articles each expert should specialise in. Every expert measures how
  "surprised" it is by text, in bits/byte (bpb) — lower = more familiar.

    classify : route each line to its least-surprised (best-fit) expert
    lightup  : route ONE query AND show what that expert is about
    novelty  : flag text no expert recognises (out-of-distribution)
    mixture  : blend all experts into one model (beats any single one)

  Note: this is GENERAL news — a fairly uniform corpus — so experts
  specialise SUBTLY (by era / section / region) more than by sharp
  topic. The split is far crisper on topically-varied corpora (mixed
  languages, Wikipedia articles); see GA.md for those results.

TRY IT YOURSELF
  # route a query and see the chosen expert's real vocabulary + a sample:
  python3 atn-ga.py lightup  --out demo-run "a full sentence works best"

  # batch-route or novelty-check your own file (one item per line):
  ./classify.sh demo-run yourfile.txt
  ./novelty.sh  demo-run yourfile.txt

  # keep evolving this same population for 10 more minutes (resumable):
  ./ga-step.sh  demo-run 10

  Tip: full sentences score far better than 2-3 words — a short query
  looks "surprising" to every expert, so trust the RANKING, not the
  absolute bpb.
────────────────────────────────────────────────────────────────────
GUIDE
