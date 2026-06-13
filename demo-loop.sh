#!/bin/sh
# demo-loop.sh — close the loop and watch what pops out.
#
# Route a seed to the expert that fits it best; let that expert GENERATE a
# continuation; feed the output back; re-route; repeat. Because the lit expert
# changes with the content, the trajectory can wander across the population's
# territories — but atn is deterministic, so a self-fed loop has nowhere to go
# but an ATTRACTOR: it slides downhill in surprisal until it sits in some
# expert's most-comfortable self-generated text (a fixed point or short cycle).
#
# That attractor structure is the honest answer to "connect the output to the
# input and see what pops out" — the shape of the network's basins, not a spark
# of mind. Closing the loop adds recurrence; recurrence in a deterministic map
# gives you dynamics, not a someone.
#
#   ./demo-loop.sh [RUNDIR]      # default: the richest run dir present
#
# Needs: a C compiler + make, python3 (stdlib). Run a demo first (e.g. demo-all).
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }

[ -x ./atn ] || { echo "building atn ..."; make >/dev/null; }

RUN="${1:-}"
if [ -z "$RUN" ]; then
    for d in demo-meta demo-langs demo-formal demo-code demo-run; do
        [ -d "$d" ] && RUN="$d" && break
    done
fi
[ -d "$RUN" ] || { echo "no run dir found — run ./demo-all.sh (or a single demo) first"; exit 1; }

say "dream loop over '$RUN' — route → generate → feed back → re-route"
for SEED in \
  "in the beginning there was light" \
  "the quick brown fox" \
  "∀x (Human(x) → Mortal(x))" ; do
  python3 atn-ga.py loop --out "$RUN" --seed-text "$SEED" --steps 20
  echo
done

cat <<'GUIDE'
────────────────────────────────────────────────────────────────────
WHAT POPPED OUT
  An attractor, fast. Each seed flows to the expert that fits it, that expert
  generates the text it itself finds least surprising, and the loop locks onto
  that fixed point (watch the bpb fall as it settles). Different seeds drain
  into different experts; determinism means it can't escape.

  This is the honest end of the meta thread. Closing the loop gives the system
  RECURRENCE — the one ingredient the architecture lacked — and what recurrence
  produces here is a dynamical system relaxing into its basins. Not a mind:
  there is no novelty source, no self-model, no world, nothing felt. A drain,
  found. Which is itself a clean thing to be able to see.
────────────────────────────────────────────────────────────────────
GUIDE
