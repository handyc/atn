#!/bin/sh
# prepare-llm.sh — one command from raw corpus to a train-ready dataset.
# Runs the cleaning/dedup pass (atn --prep), then a DETERMINISTIC shuffle and a
# train/val split, and writes a manifest. The output dir is what you hand to a
# real (GPU) trainer later.
#
#   prepare-llm.sh OUTDIR file1 [file2 ...]
#   prepare-llm.sh data/run1 news1934.txt
#
# Produces in OUTDIR:
#   train.txt      cleaned, deduped, shuffled corpus (minus the val slice)
#   val.txt        held-out slice for eval (VAL_PCT of lines)
#   manifest.txt   byte/line counts, est. tokens, prep drop stats, settings
#
# Determinism: the shuffle orders lines by a fixed hash of their content, so the
# same inputs always yield the same split — no RNG, reproducible across machines.
#
# Env: VAL_PCT=1 (percent of lines held out), and any PREP_* knobs are passed
#      through to the cleaning pass (PREP_MINLEN, PREP_MINALPHA, PREP_MINWORD,
#      PREP_NEAR). Set PREP_SKIP=1 if inputs are already cleaned.
set -e
A="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/atn"
[ -x "$A" ] || { echo "build first: make"; exit 1; }

OUT="$1"; shift || true
[ -n "$OUT" ] && [ $# -ge 1 ] || { echo "usage: prepare-llm.sh OUTDIR file1 [file2 ...]"; exit 2; }
for f in "$@"; do [ -f "$f" ] || { echo "no such file: $f"; exit 2; }; done
VAL_PCT="${VAL_PCT:-1}"
mkdir -p "$OUT"

# 1. clean + dedup (or skip if caller says inputs are already clean)
if [ "${PREP_SKIP:-0}" = "1" ]; then
    cat "$@" > "$OUT/clean.txt"
    PREP_STATS="(prep skipped; inputs assumed clean)"
else
    # stderr from prep carries the drop stats; capture it for the manifest
    PREP_STATS="$("$A" --prep "$@" > "$OUT/clean.txt" 2>&1 1>/dev/null || true)"
    [ -n "$PREP_STATS" ] || PREP_STATS="$("$A" --prep "$@" 2>&1 >"$OUT/clean.txt")"
fi
[ -s "$OUT/clean.txt" ] || { echo "prep produced no output"; exit 1; }

# 2. deterministic shuffle + train/val split (hash-keyed sort, no RNG)
python3 - "$OUT/clean.txt" "$OUT/train.txt" "$OUT/val.txt" "$VAL_PCT" <<'PY'
import sys, hashlib
src, trainf, valf, vpct = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
lines = [ln for ln in open(src, errors="ignore").read().split("\n") if ln]
# stable pseudo-random order: sort by a fixed content hash (reproducible anywhere)
lines.sort(key=lambda s: hashlib.blake2b(s.encode("utf-8", "ignore"), digest_size=8).digest())
nval = max(1, int(len(lines) * vpct / 100)) if len(lines) > 1 else 0
val, train = lines[:nval], lines[nval:]
open(trainf, "w").write("\n".join(train) + ("\n" if train else ""))
open(valf,   "w").write("\n".join(val)   + ("\n" if val else ""))
print(f"{len(train)}\t{len(val)}")
PY

# 3. manifest
cb=$(wc -c < "$OUT/clean.txt"); cl=$(wc -l < "$OUT/clean.txt")
tb=$(wc -c < "$OUT/train.txt"); tl=$(wc -l < "$OUT/train.txt")
vb=$(wc -c < "$OUT/val.txt");   vl=$(wc -l < "$OUT/val.txt")
est=$((cb / 4))   # rough GPT-BPE token estimate (~4 bytes/token for English)
{
    echo "atn prepare-llm manifest"
    echo "inputs        : $*"
    echo "val_pct       : $VAL_PCT"
    echo "prep          : $PREP_STATS"
    echo "clean.txt     : $cl lines, $cb bytes"
    echo "train.txt     : $tl lines, $tb bytes"
    echo "val.txt       : $vl lines, $vb bytes"
    echo "est. tokens   : ~$est  (clean bytes / 4)"
    echo "shuffle       : deterministic (blake2b content hash)"
} > "$OUT/manifest.txt"

cat "$OUT/manifest.txt"
echo "ready -> $OUT/train.txt  +  $OUT/val.txt"
