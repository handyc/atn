#!/bin/sh
# classify.sh — route text to its best-fitting expert in an evolved population.
# Each input line is labelled with the expert (corpus slice) that explains it best,
# its bits/byte, and the margin over the runner-up (confidence).
#
#   classify.sh RUNDIR [file ...]        # files, or stdin if none
#   echo "some text" | classify.sh RUNDIR
#
# RUNDIR is an atn-ga run directory (created by `atn-ga.py run`).
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
[ -x "$HERE/atn" ] || { echo "build first: make"; exit 1; }
OUT="$1"; [ -d "$OUT" ] || { echo "usage: classify.sh RUNDIR [file ...]"; exit 2; }
shift
exec python3 "$HERE/atn-ga.py" classify --out "$OUT" --atn "$HERE/atn" "$@"
