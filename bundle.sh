#!/bin/sh
# bundle.sh — the honest path to a real model: export a set of brains' text as
# one clean training corpus. Concatenates every brain's transcript and removes
# exact-duplicate lines (articles / chat turns). The brains' n-gram COUNTS are
# discarded — the text is the asset a real trainer would relearn and surpass.
#
#   bundle.sh BRAIN_DIR OUT.txt
#
# Then fine-tune / pretrain a neural model on OUT.txt.
DIR="$1"; OUT="$2"
{ [ -d "$DIR" ] && [ -n "$OUT" ]; } || { echo "usage: bundle.sh BRAIN_DIR OUT.txt"; exit 2; }
brains=$(ls "$DIR"/*.brain 2>/dev/null) || true
[ -n "$brains" ] || { echo "no *.brain files in $DIR"; exit 2; }

tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
nbrains=0
for b in $brains; do cat "$b" >> "$tmp"; nbrains=$((nbrains + 1)); done
inlines=$(wc -l < "$tmp")
awk '!seen[$0]++' "$tmp" > "$OUT"          # exact-line dedup, order preserved
outlines=$(wc -l < "$OUT"); outbytes=$(wc -c < "$OUT")

printf 'bundled %d brain(s): %d -> %d lines after dedup, %d bytes -> %s\n' \
    "$nbrains" "$inlines" "$outlines" "$outbytes" "$OUT"
echo "next: fine-tune a real model on $OUT (its n-gram counts get relearned;"
echo "      the text is what carries over). For novelty filtering across brains,"
echo "      score each line under the OTHER brains and keep the surprising ones."
