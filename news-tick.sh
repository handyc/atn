#!/bin/sh
# news-tick.sh — ONE scrape tick. This is what you put in cron every 3 hours.
# Fetches current headlines, stores them under this ISO-week's folder, and builds
# a small brain for the tick (handy for route/trend; the text is what feeds the
# LLM at week's end).
#
#   news-tick.sh [DATADIR]
#
# Layout it maintains (DATADIR default ./newsdata or $NEWS_DIR):
#   DATADIR/2026-W24/raw/<stamp>.txt      one item per line (+ .meta provenance)
#   DATADIR/2026-W24/brains/<stamp>.brain n-gram brain for this tick
#
# Feeds come from $NEWS_FEEDS (a feeds file); otherwise fetch-news.sh's default.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DATADIR="${1:-${NEWS_DIR:-$HERE/newsdata}}"
WEEK="$(date +%G-W%V)"            # ISO year-week, e.g. 2026-W24
STAMP="$(date +%Y%m%d-%H%M%S)"
WDIR="$DATADIR/$WEEK"
mkdir -p "$WDIR/raw" "$WDIR/brains"

"$HERE/fetch-news.sh" "$WDIR/raw/$STAMP" >/dev/null 2>"$WDIR/raw/$STAMP.log" || true

if [ -s "$WDIR/raw/$STAMP.txt" ]; then
    "$HERE/atn" --train "$WDIR/raw/$STAMP.txt" --brain "$WDIR/brains/$STAMP.brain" \
        -q --strip-html >/dev/null 2>&1 || true
    echo "$(date '+%F %T')  tick $STAMP  $(wc -l < "$WDIR/raw/$STAMP.txt") items  -> $WEEK"
else
    echo "$(date '+%F %T')  tick $STAMP  NO ITEMS (see $WDIR/raw/$STAMP.log)"
fi
