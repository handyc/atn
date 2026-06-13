#!/bin/sh
# news-week.sh — END OF WEEK. Collect every tick this week and prep one
# train-ready dataset for the LLM. This is the second cron job (run once weekly).
#
#   news-week.sh [DATADIR] [WEEK]
#   news-week.sh                 # this ISO week
#   news-week.sh ./newsdata 2026-W24
#
# Pools all of the week's raw scrapes and runs them through prepare-llm.sh, which
# cleans + de-duplicates ACROSS ticks (the same wire story scraped 8x/day collapses
# to one), deterministically shuffles, and splits train/val. It also builds one
# whole-week brain (for week-over-week trend.sh / route.sh).
#
# Output in DATADIR/WEEK/:
#   dataset/{train.txt,val.txt,manifest.txt}   <- hand this to the GPU trainer
#   dataset/all.meta                            <- pooled provenance, line-aligned to clean.txt
#   week.brain                                  <- brain over the whole week
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DATADIR="${1:-${NEWS_DIR:-$HERE/newsdata}}"
WEEK="${2:-$(date +%G-W%V)}"
WDIR="$DATADIR/$WEEK"
[ -d "$WDIR/raw" ] || { echo "no week data at $WDIR (run news-tick.sh first)"; exit 2; }

set -- "$WDIR"/raw/*.txt
[ -e "$1" ] || { echo "no raw scrapes in $WDIR/raw"; exit 2; }
echo "pooling $# ticks from $WEEK ..."

# 1. prep + shuffle + split across the whole week (dedup collapses repeats)
"$HERE/prepare-llm.sh" "$WDIR/dataset" "$@"

# 2. pooled provenance sidecar (concatenate the per-tick .meta files)
cat "$WDIR"/raw/*.meta > "$WDIR/dataset/all.meta" 2>/dev/null || true

# 3. one brain over the whole cleaned week (for trend.sh / route.sh vs other weeks)
"$HERE/atn" --train "$WDIR/dataset/clean.txt" --brain "$WDIR/week.brain" -q --strip-html >/dev/null 2>&1 || true

echo "week $WEEK ready:"
echo "  dataset -> $WDIR/dataset/train.txt + val.txt   (manifest.txt has the stats)"
echo "  brain   -> $WDIR/week.brain"
echo "  compare to last week:  ./trend.sh $WDIR/week.brain <lastweek>/week.brain < phrases.txt"
