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
    T="${NOVEL_BPB:-3.0}"
    inlines=0; : > "$tmp/all"
    for b in $brains; do
        inlines=$((inlines + $(wc -l < "$b")))
        # train a model of everything EXCEPT this brain
        : > "$tmp/rest"
        for o in $brains; do [ "$o" = "$b" ] || cat "$o" >> "$tmp/rest"; done
        "$A" --train "$tmp/rest" --brain "$tmp/rest.brain" >/dev/null 2>&1
        # keep b's lines that the rest finds surprising (>= T bits/byte)
        "$A" --score --brain "$tmp/rest.brain" < "$b" \
          | awk -F'\t' -v t="$T" '($1+0) >= t { print $2 }' >> "$tmp/all"
        rm -f "$tmp/rest.brain" "$tmp/rest.brain.weights"
    done
    note="novelty-filtered (>= ${T} bpb vs other brains)"
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
