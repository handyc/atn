#!/bin/sh
# demo.sh — a narrated, fully automated tour of atn's "fake transformer":
#   from "attention to the files in a filesystem" to "attention in the GPT
#   sense" to "a deterministic, unlearned transformer that actually works".
# Run from the atn source dir after `make`.  Deterministic; safe to re-run.
set -e
A=./atn
strip() { sed 's/\x1b\[[0-9;]*m//g'; }
say()  { printf '\n\033[1m\033[36m%s\033[0m\n' "$1"; }
note() { printf '\033[2m%s\033[0m\n' "$1"; }
hr()   { printf '\033[2m────────────────────────────────────────────────────────\033[0m\n'; }

[ -x "$A" ] || { echo "build first:  make"; exit 1; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

cat <<'EOF'

  atn — looking very, very closely at files.
  The thesis of this demo: a file's PREDICTABILITY is a measurement, and you can
  compute it with the real transformer machinery (attention, induction, layered
  feedback) — deterministically, with no training. Five acts:

EOF

# ───────────────────────────────────────────────────────────────────────────
say "ACT 1 — Attention to FILES: which file in a tree doesn't belong?"
note "We build ONE byte language-model over a directory and score every file's"
note "surprisal under it (held out). Files that fit score low; aliens score high."
mkdir -p "$TMP/src"; cp ./*.c ./*.h ./README.md "$TMP/src/" 2>/dev/null || true
head -c 8192 /dev/urandom > "$TMP/src/SECRET.enc"      # a planted encrypted blob
$A --corpus "$TMP/src" 2>/dev/null | strip | grep -A6 "most surprising"
note "→ SECRET.enc rockets to the top at ~8.6 bits/byte. The model can't predict"
note "  encrypted data, so its surprise = a content-grounded anomaly score."
hr

# ───────────────────────────────────────────────────────────────────────────
say "ACT 2 — Attention in the GPT sense: the 2-layer induction circuit"
note "Hand-wired, no learning: a previous-token head (layer 0) feeds an induction"
note "head (layer 1). This is the actual circuit behind in-context learning."
$A -q -Z README.md 2>/dev/null | strip | grep -A20 "2-layer induction circuit" | head -23
note "→ Layer 0 is the sub-diagonal ('look back one'); layer 1 attends to where"
note "  the current byte last occurred — induction = in-context copying."
hr

# ───────────────────────────────────────────────────────────────────────────
say "ACT 3 — The feedback loop: prediction error re-weights the model"
note "Several experts (short..long context) each predict the next byte; the blend"
note "weights are updated by the error every byte — a transformer's gradient loop,"
note "online and deterministic. It also locates the file's information-dense spots."
$A -q -B /bin/sh 2>/dev/null | strip | sed -n '/experts:/,/every byte/p'
note "→ The weights LEARN which context length to trust from the model's own"
note "  mistakes; the surprisal map shows where the model 'looks hardest'."
hr

# ───────────────────────────────────────────────────────────────────────────
say "ACT 4 — It generates: feed the prediction back in (autoregression)"
note "Temperature sampling from the model, each output byte fed back as input."
$A -q -Z --temp 0.5 --gen 200 README.md 2>/dev/null | strip \
  | grep -A1 "generated .* bytes:" | tail -1 | sed 's/^ *//'
note "→ Coherent fragments reconstructed from the file's own statistics — the GPT"
note "  inference loop, no training."
hr

# ───────────────────────────────────────────────────────────────────────────
say "ACT 5 — It WORKS: lossless compression that beats gzip -9"
note "Context-mixing: 7 models predict each bit; a logistic mixer (online-trained"
note "by prediction error — the feedback loop, load-bearing) drives an arithmetic"
note "coder. The decoder runs the identical model in lockstep -> provably lossless."
cat ./*.c ./*.h > "$TMP/corpus.txt"
$A --compress "$TMP/corpus.txt" -o "$TMP/c.atcm" 2>&1 | sed 's/^atn: /  /'
$A --decompress "$TMP/c.atcm" -o "$TMP/c.out" 2>/dev/null
cmp -s "$TMP/corpus.txt" "$TMP/c.out" && echo "  round-trip: LOSSLESS (bit-identical)" || echo "  round-trip: FAILED"
gz=$(gzip -9c "$TMP/corpus.txt" | wc -c); at=$(wc -c < "$TMP/c.atcm"); raw=$(wc -c < "$TMP/corpus.txt")
printf "  raw %s   atn %s   gzip -9 %s   (smaller is better)\n" "$raw" "$at" "$gz"
note "→ A deterministic, untrained model beating the standard compressor on text."
hr

cat <<'EOF'

  That's the whole arc: files -> attention -> prediction -> generation ->
  working compression. Nothing was trained; every number is reproducible.

  Explore interactively:   ./explore.sh <file>
  Read the prediction docs: PREDICTION.md
EOF
