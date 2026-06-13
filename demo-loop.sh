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

# An optional class-4 hex-CA LUT (a mandelhunt .lut) is the deterministic
# novelty source. Pass it as $2, or set ATN_CA_LUT; without it the loop just
# shows the fixed-point collapse.
CA_LUT="${2:-${ATN_CA_LUT:-}}"

say "dream loop over '$RUN' — CLOSED loop with no novelty source"
echo "  (route → generate → feed back → re-route; expect a fast collapse)"
python3 atn-ga.py loop --out "$RUN" --seed-text "in the beginning there was light" --steps 12

if [ -n "$CA_LUT" ] && [ -f "$CA_LUT" ]; then
  say "same loop, now driven by a class-4 hex CA ($(basename "$CA_LUT"))"
  echo "  (the CA advances each step → deterministic novelty → no collapse)"
  python3 atn-ga.py loop --out "$RUN" --seed-text "in the beginning there was light" \
      --steps 16 --ca-ticks 6 --ca-lut "$CA_LUT"
else
  say "no CA LUT given — pass one to see the loop escape the fixed point:"
  echo "  ./demo-loop.sh $RUN /path/to/some_class4.lut    (or set ATN_CA_LUT)"
fi

cat <<'GUIDE'
────────────────────────────────────────────────────────────────────
WHAT POPPED OUT
  Closing the loop adds RECURRENCE — the ingredient the architecture lacked.
  With no novelty source, a deterministic map fed its own output has nowhere to
  go but an ATTRACTOR: it locks to a fixed point in a step or two (watch the bpb
  fall as it settles into the lit expert's most-comfortable self-text).

  Add a class-4 cellular automaton as the seed and the collapse goes away. The
  CA is deterministic and reproducible (no clock, no rand) yet never repeats —
  edge-of-chaos structure forever — so each step samples differently and the
  loop keeps exploring instead of draining. That's cheap novelty without
  breaking determinism: the system stays a dynamical process, but now an
  open-ended one. Still not a mind — the novelty is the CA's, injected, not the
  network's own — but it is the difference between a thing that stops and a
  thing that keeps going.
────────────────────────────────────────────────────────────────────
GUIDE
