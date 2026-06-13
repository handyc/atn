#!/bin/sh
# novelty.sh — out-of-distribution / anomaly score for text, using an evolved
# population. Each line gets the lowest bits/byte any expert assigns it: low =
# familiar (in-corpus), high = novel/foreign/anomalous. Lines at/above a
# threshold (default ~1.6x the corpus's own bpb) are flagged NOVEL.
#
#   novelty.sh RUNDIR [file ...]               # files, or stdin if none
#   NOVELTY_THRESHOLD=4.0 novelty.sh RUNDIR in.txt
#
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
[ -x "$HERE/atn" ] || { echo "build first: make"; exit 1; }
OUT="$1"; [ -d "$OUT" ] || { echo "usage: novelty.sh RUNDIR [file ...]"; exit 2; }
shift
THR=""
[ -n "$NOVELTY_THRESHOLD" ] && THR="--threshold $NOVELTY_THRESHOLD"
exec python3 "$HERE/atn-ga.py" novelty --out "$OUT" --atn "$HERE/atn" $THR "$@"
