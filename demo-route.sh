#!/bin/sh
# demo-route.sh — a 2-level routing TREE over the domain populations (the useful
# "meta on meta"). It does NOT train more experts; it builds a cheap COARSE GATE.
#
#   level 1 (coarse): one small brain per domain (news / language / code / formal),
#                     trained on a sample of that domain's corpus. Picks the domain.
#   level 2 (fine):   the chosen domain's existing expert population picks the expert.
#
# A query routes kind → expert in two hops, scoring #domains + (experts in one
# domain) brains instead of every expert everywhere — sublinear routing, which is
# the point of a hierarchy at scale. Quality is still capped by the leaf n-gram
# brains: this makes routing cheaper, not the output smarter.
#
#   ./demo-route.sh
#
# Needs: a C compiler + make, python3 (stdlib). No network. Run some of the other
# demos first (e.g. ./demo-all.sh); this uses whichever domain runs exist.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }

say "atn routing-tree demo — coarse domain gate → fine expert"

[ -x ./atn ] || { echo "building atn ..."; make >/dev/null; }

# 1. build the coarse gate: one cheap brain per available domain + a manifest
say "build — a coarse brain per domain (a sample of each domain's corpus)"
python3 - <<'PY'
import os, json, random, subprocess, tempfile
random.seed(1)
DOMAINS = [("news","demo-run"), ("language","demo-langs"),
           ("code","demo-code"), ("formal","demo-formal")]
os.makedirs("demo-route", exist_ok=True)
present = []
for label, d in DOMAINS:
    terr = os.path.join(d, "territory.txt")
    if not os.path.exists(terr):
        continue
    lines = [ln for ln in open(terr, encoding="utf-8", errors="ignore") if len(ln.strip()) >= 40]
    random.shuffle(lines)
    sample = "".join(lines[:800])[:400000]          # a representative slice of the domain
    tf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    tf.write(sample); tf.close()
    brain = f"coarse-{label}.brain"
    subprocess.run(["./atn", "--train", tf.name, "--brain", os.path.join("demo-route", brain),
                    "-q", "--orders", "2,4,7"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    os.unlink(tf.name)
    present.append({"label": label, "run_dir": d, "brain": brain})
    print(f"  coarse brain: {label:9} ← {d}", flush=True)
if len(present) < 2:
    raise SystemExit("\nNeed at least two domain runs. Run ./demo-all.sh first, then re-run this.")
json.dump({"coarse_orders": "2,4,7", "coarse_mapbits": 22, "domains": present},
          open("demo-route/manifest.json", "w"), indent=2)
print(f"  manifest: {len(present)} domains", flush=True)
PY

# 2. route a query of each kind through the tree
say "route — each query goes coarse (which domain?) then fine (which expert?)"
for Q in \
  "the president addressed congress on the new tariff bill late last night" \
  "de regering heeft een nieuwe wet over handel en belastingen aangenomen" \
  "int main(void){ struct node *p = malloc(sizeof(*p)); return p ? 0 : 1; }" \
  "∀x (Human(x) → Mortal(x)) ∧ ∃y Loves(socrates, y) ; ¬Even(plato)" \
  "∫ sin(x) dx = -cos(x) + C ; lim_{x→0} sin(x)/x = 1 ; Σ_{n=1}^∞ 1/n^2" ; do
  python3 atn-ga.py route --out demo-route "$Q"
  echo
done

say "done in $(( $(date +%s) - T0 ))s"

cat <<'GUIDE'
────────────────────────────────────────────────────────────────────
WHAT YOU JUST SAW
  A hierarchy of routers. The coarse gate is one cheap brain per domain; it
  picks the domain in #domains scores. Then only that domain's population is
  consulted for the specific expert. The [cost] line shows the win: a handful
  of brains touched instead of the whole forest — sublinear routing, which is
  how you'd serve a mixture of experts over a corpus far too big to score
  exhaustively per query.

  Honest scope: this is a SCALING structure, not an intelligence one. It makes
  routing cheaper; the answer is still only as good as the leaf n-gram brain it
  lands on. Two useful levels (kind → expert), maybe a third; past that there's
  no nested structure left to exploit — more gates would be cosplay.

  python3 atn-ga.py route --out demo-route "text of any kind"
────────────────────────────────────────────────────────────────────
GUIDE
