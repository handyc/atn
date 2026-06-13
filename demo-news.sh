#!/bin/sh
# demo-news.sh — ONE command, from a clean clone to a working result.
# Builds atn, streams a slice of 1920-1940 news from the AmericanStories archive,
# cleans it, evolves a population of GA brains over it (time-boxed), then runs
# example queries on the result. Tuned to finish in well under 10 minutes.
#
#   ./demo-news.sh [MINUTES]      # total time target, default 8
#
# Needs: a C compiler + make, python3 with numpy, curl. No pre-existing data.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
BUDGET="${1:-8}"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }
elapsed() { echo "[t+$(( $(date +%s) - T0 ))s]"; }

# fail fast on missing prerequisites, BEFORE the long corpus fetch.
# numpy is required by the content-loci and mixture steps below.
python3 -c 'import numpy' 2>/dev/null || {
    echo "error: this demo needs numpy (used by --locus content and the mixture step)."
    echo "       install it with:  python3 -m pip install numpy"
    exit 1
}

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
say "classify — which slice of the news does each line fit?"
printf '%s\n' \
  "the president addressed congress on the new tariff bill" \
  "the home team won the championship in the ninth inning" \
  "shares fell sharply on the stock exchange today" \
  "the orchestra performed a symphony at the concert hall" \
  | python3 atn-ga.py classify --out demo-run

say "novelty — in-period news vs out-of-distribution text"
printf '%s\n' \
  "a fire broke out downtown late last night" \
  "stream the viral selfie to your influencer hashtag feed" \
  "qx zzt 9999 ;;;; vbnm kkkk" \
  | python3 atn-ga.py novelty --out demo-run

say "mixture — the population AS a corpus language model"
python3 atn-ga.py mixture --out demo-run 2>&1 | grep -E "single|fixed-share|beats" || true

say "done in $(( $(date +%s) - T0 ))s"
echo "explore further:"
echo "  python3 atn-ga.py lightup  --out demo-run \"your headline here\""
echo "  ./classify.sh demo-run somefile.txt"
echo "  ./novelty.sh  demo-run somefile.txt"
echo "  ./ga-step.sh  demo-run 10           # evolve it 10 more minutes"
