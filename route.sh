#!/bin/sh
# route.sh — mixture-of-atn-experts. Score a query against every brain in a
# directory and report which corpus it fits best (lowest surprisal). A cheap,
# interpretable "which of these domains/days/topics is this about" front-end.
#
#   route.sh BRAIN_DIR "the query"
#   route.sh BRAIN_DIR < queries.txt          # one query per line
#
# Output per query: best brain, its bits/byte, and the margin over the runner-up.
A="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/atn"
[ -x "$A" ] || { echo "build first: make"; exit 1; }
DIR="$1"; QUERY="$2"
[ -d "$DIR" ] || { echo "usage: route.sh BRAIN_DIR [\"query\"]"; exit 2; }
brains=$(ls "$DIR"/*.brain 2>/dev/null) || true
[ -n "$brains" ] || { echo "no *.brain files in $DIR"; exit 2; }

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
if [ -n "$QUERY" ]; then printf '%s\n' "$QUERY" > "$tmp/q"; else cat > "$tmp/q"; fi
[ -s "$tmp/q" ] || { echo "(no query)"; exit 0; }

# score every query under each brain (one batch load per brain) -> a column each
cols=""; names=""; i=0
for b in $brains; do
    "$A" --score --brain "$b" < "$tmp/q" | awk '{print $1}' > "$tmp/c$i"
    cols="$cols $tmp/c$i"
    names="$names $(basename "$b" .brain)"
    i=$((i + 1))
done

# for each query row, pick the min-bpb brain and the margin over 2nd best
paste $cols "$tmp/q" | awk -F'\t' -v names="$names" -v nb="$i" '
BEGIN { split(names, nm, " ") }
{
    best = 1e9; second = 1e9; bi = 0
    for (j = 1; j <= nb; j++) { v = $j + 0
        if (v < best) { second = best; best = v; bi = j }
        else if (v < second) { second = v } }
    q = $(nb + 1)
    printf "%-30s -> %-14s %5.2f bpb  (+%.2f over next)\n", q, nm[bi], best, second - best
}'
