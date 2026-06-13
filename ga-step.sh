#!/bin/sh
# ga-step.sh — advance the resumable atn-ga evolver by one time-boxed step.
# Designed for cron: each call evolves for ~MINUTES, checkpoints, and exits. The
# next call picks up exactly where it left off (deterministically).
#
#   ga-step.sh OUTDIR MINUTES [FRESH-RUN ARGS...]
#
#   # first call creates the run (needs --corpus and any params):
#   ga-step.sh /data/eo 10 --corpus enwik8 --chunk-on '<title>' \
#              --locus content --evolve-orders --pop 48 --span-mb 0.6
#   # every later call just continues — no args needed:
#   ga-step.sh /data/eo 10
#
# Cron (advance 10 min every hour):
#   0 * * * * /path/to/ga-step.sh /data/eo 10 >> /data/eo/cron.log 2>&1
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
[ -x "$HERE/atn" ] || { echo "build first: make"; exit 1; }
OUT="$1"; MIN="${2:-10}"
[ -n "$OUT" ] || { echo "usage: ga-step.sh OUTDIR MINUTES [fresh-run args...]"; exit 2; }
shift 2 2>/dev/null || shift $#

if [ -f "$OUT/state.json" ]; then
    echo "[$(date '+%F %T')] resume $OUT (+${MIN}m)"
    exec python3 "$HERE/atn-ga.py" run --out "$OUT" --minutes "$MIN" --atn "$HERE/atn"
else
    echo "[$(date '+%F %T')] fresh   $OUT (+${MIN}m)  $*"
    exec python3 "$HERE/atn-ga.py" run --out "$OUT" --minutes "$MIN" --atn "$HERE/atn" "$@"
fi
