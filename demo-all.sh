#!/bin/sh
# demo-all.sh — the grand tour: run all four atn corpus demos back to back.
#
# Each grows a population of GA brains over a different KIND of corpus and shows
# the experts self-organising — same mechanism, four very different materials:
#   1. news       one topical domain (1920s-1940s American newspapers)  [internet]
#   2. languages  seven natural languages (Wikipedia)                   [internet]
#   3. code       five kinds of machine text (the local filesystem)     [local]
#   4. formal     six mathematical notations (generated from grammars)  [no data]
#
#   ./demo-all.sh [MINUTES_PER_DEMO]      # default 5; total run ≈ 4× that
#
# Needs: a C compiler + make, python3 (stdlib). News & languages also need
# internet; code also likes objdump + xxd. Any demo that can't run is skipped,
# and the tour continues with the rest.
set -u
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
M="${1:-5}"
T0=$(date +%s)

LINE="──────────────────────────────────────────────────────────────────────"
banner() { printf '\n\033[1m%s\n  %s\n%s\033[0m\n' "$LINE" "$1" "$LINE" 2>/dev/null \
           || printf '\n%s\n  %s\n%s\n' "$LINE" "$1" "$LINE"; }

# build once up front (so no demo rebuilds, and we fail early without a compiler)
[ -x ./atn ] || { echo "building atn ..."; make >/dev/null || { echo "build failed — need a C compiler"; exit 1; }; }

STATUS=""
run_one() {
    label=$1; script=$2
    banner "$label  (~${M} min)"
    if "./$script" "$M"; then
        STATUS="$STATUS\n  ✓ $label"
    else
        STATUS="$STATUS\n  ✗ $label  — skipped/failed (see output above)"
    fi
}

run_one "1/4  NEWS — one topical domain (1920s-1940s American newspapers)"      demo-news.sh
run_one "2/4  NATURAL LANGUAGES — seven languages (en/nl/fr/de/es/it/zh)"        demo-languages.sh
run_one "3/4  CODE — five kinds of machine text (C/Python/shell/asm/hex)"        demo-code.sh
run_one "4/4  FORMAL — six notations (FOL/linalg/set/calculus/lambda/regex)"     demo-formal.sh

banner "grand tour complete in $(( $(date +%s) - T0 ))s"
printf 'demos run:%b\n' "$STATUS"
cat <<'EOF'

Four populations now live in their run directories — explore any of them:
  demo-run  (news)    demo-langs (languages)    demo-code (code)    demo-formal (formal)

  python3 atn-ga.py lightup  --out demo-langs  "a sentence in some language"
  python3 atn-ga.py classify --out demo-code   somefile.txt
  python3 atn-ga.py mixture  --out demo-formal

The throughline: one cheap mechanism — a population of n-gram brains the GA
tiles over a corpus — finds whatever structure the corpus actually has (topic,
language, kind of code) with no labels. The formal demo also shows the limit:
it reads surface form, not meaning, so look-alike systems (∀ vs λ) blur.
EOF
