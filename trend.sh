#!/bin/sh
# trend.sh — what's rising? Score each phrase under TWO brains (e.g. today vs
# yesterday, or this week vs last week) and report the change in surprisal.
#
#   trend.sh NEW.brain OLD.brain < phrases.txt
#   printf '%s\n' "phrase one" "phrase two" | trend.sh today.brain yesterday.brain
#
# A phrase that fits NEW much better than OLD (surprisal dropped) is trending up;
# one that fits OLD better than NEW is fading. Output is sorted most-rising first:
#
#   delta   new    old    phrase
#  +1.840  1.90   3.74   roosevelt recovery program     <- surged in NEW
#  -0.020  2.51   2.49   the weather today              <- unchanged
#  -1.300  4.10   2.80   the gold standard              <- faded
#
# delta = old_bits_per_byte - new_bits_per_byte  (positive = rising in NEW).
set -e
A=./atn
[ -x "$A" ] || { echo "build first: make"; exit 1; }
NEW="$1"; OLD="$2"
[ -n "$OLD" ] || { echo "usage: trend.sh NEW.brain OLD.brain < phrases.txt"; exit 2; }
[ -f "$NEW" ] && [ -f "$OLD" ] || { echo "both brain files must exist"; exit 2; }

phrases=$(cat)
[ -n "$phrases" ] || { echo "(no phrases on stdin)"; exit 0; }

# score the same phrases under each brain (one batch load each), keep bits/byte
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
printf '%s\n' "$phrases" | "$A" --score --brain "$NEW" | awk '{print $1}' > "$tmp/new"
printf '%s\n' "$phrases" | "$A" --score --brain "$OLD" | awk '{print $1}' > "$tmp/old"
printf '%s\n' "$phrases" > "$tmp/phr"

printf ' %-7s %-6s %-6s  %s\n' delta new old phrase
paste "$tmp/new" "$tmp/old" "$tmp/phr" \
  | awk -F'\t' '{ d = $2 - $1; printf "%+7.3f %6.2f %6.2f  %s\n", d, $1, $2, $3 }' \
  | sort -rn
