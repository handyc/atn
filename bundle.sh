#!/bin/sh
# bundle.sh — the honest path to a real model: export a set of brains' text as
# one clean training corpus. Concatenates every brain's transcript and removes
# exact-duplicate lines (articles / chat turns). The brains' n-gram COUNTS are
# discarded — the text is the asset a real trainer would relearn and surpass.
#
#   bundle.sh BRAIN_DIR OUT.txt [--novel]
#
# --novel: cross-brain novelty filter. For each brain, score its lines under a
# model of all the OTHER brains and keep only the surprising (distinctive) ones,
# so material common across brains (boilerplate, shared stories) is dropped and
# the corpus keeps more signal per byte. Env NOVEL_BPB sets the threshold
# (default 3.0 bits/byte; higher = stricter = fewer, more distinctive lines).
A=./atn
DIR="$1"; OUT="$2"; MODE="$3"
{ [ -d "$DIR" ] && [ -n "$OUT" ]; } || { echo "usage: bundle.sh BRAIN_DIR OUT.txt [--novel]"; exit 2; }
brains=$(ls "$DIR"/*.brain 2>/dev/null) || true
[ -n "$brains" ] || { echo "no *.brain files in $DIR"; exit 2; }
nbrains=$(printf '%s\n' "$brains" | wc -l)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

if [ "$MODE" = "--novel" ] && [ "$nbrains" -gt 1 ]; then
    # 2-fold held-out novelty: split the brains into two folds, train a model on
    # each fold (sampling a slice of every brain so the fold fits MODEL_CAP), and
    # score each brain's lines under the OPPOSITE fold's model. Keep the
    # surprising ones. Two trainings regardless of how many brains (scales to 64+),
    # and held out (a brain is never scored by a model that contains it).
    T="${NOVEL_BPB:-3.0}"
    half=$(( (nbrains + 1) / 2 ))
    per=$(( 64000000 / half ))          # bytes sampled per brain so a fold <= MODEL_CAP
    : > "$tmp/foldA"; : > "$tmp/foldB"
    i=0
    for b in $brains; do
        if [ $((i % 2)) -eq 0 ]; then head -c "$per" "$b" >> "$tmp/foldA"
        else head -c "$per" "$b" >> "$tmp/foldB"; fi
        i=$((i + 1))
    done
    "$A" --train "$tmp/foldA" --brain "$tmp/mA.brain" -q >/dev/null 2>&1
    "$A" --train "$tmp/foldB" --brain "$tmp/mB.brain" -q >/dev/null 2>&1

    inlines=0; : > "$tmp/all"; i=0
    for b in $brains; do
        inlines=$((inlines + $(wc -l < "$b")))
        if [ $((i % 2)) -eq 0 ]; then m="$tmp/mB.brain"; else m="$tmp/mA.brain"; fi
        "$A" --score --brain "$m" < "$b" \
          | awk -F'\t' -v t="$T" '($1+0) >= t { print $2 }' >> "$tmp/all"
        i=$((i + 1))
    done
    rm -f "$tmp/mA.brain" "$tmp/mA.brain.weights" "$tmp/mB.brain" "$tmp/mB.brain.weights"
    note="novelty-filtered (>= ${T} bpb, 2-fold held-out)"
else
    inlines=0; : > "$tmp/all"
    for b in $brains; do cat "$b" >> "$tmp/all"; inlines=$((inlines + $(wc -l < "$b"))); done
    note="exact-line dedup"
fi

awk '!seen[$0]++' "$tmp/all" > "$OUT"      # dedup, order preserved
outlines=$(wc -l < "$OUT"); outbytes=$(wc -c < "$OUT")
printf 'bundled %d brain(s) [%s]: %d -> %d lines, %d bytes -> %s\n' \
    "$nbrains" "$note" "$inlines" "$outlines" "$outbytes" "$OUT"
echo "next: fine-tune a real model on $OUT (its n-gram counts get relearned; the text carries over)."
