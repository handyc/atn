#!/bin/sh
# demo-meta.sh — train on the previous trainings.
#
# The other demos (news / languages / code / formal) each evolve a population
# over one KIND of corpus and leave it in a run directory. This meta-demo takes
# the text those runs trained on (each RUNDIR/territory.txt) and evolves ONE new
# population over the COMBINATION — a single brain-network spanning all of them
# at once. The experts then organise by the coarse kind (news vs language vs code
# vs formal) and the finer structure within, so a query of any kind routes home.
#
#   ./demo-meta.sh [MINUTES]      # total time target, default 7
#
# Needs: a C compiler + make, python3 (stdlib). No network — it reuses corpora
# already on disk. Run the four demos first (e.g. ./demo-all.sh); this uses
# whichever of demo-run / demo-langs / demo-code / demo-formal exist.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
BUDGET="${1:-7}"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }
elapsed() { echo "[t+$(( $(date +%s) - T0 ))s]"; }

say "atn meta demo — train on the previous trainings  (target ~${BUDGET} min)"

[ -x ./atn ] || { echo "$(elapsed) building atn ..."; make >/dev/null; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. pool the territory corpora of whichever prior runs exist
say "pool — gathering the corpora the previous demos trained on"
python3 - "$WORK/corpus.txt" demo-run demo-langs demo-code demo-formal <<'PY'
import os, sys, random
out = sys.argv[1]
sources = sys.argv[2:]
random.seed(1)
PER, CAP, MIN = 130, 1500, 120
def collapse(t): return " ".join(t.split())[:CAP]
used, lines = [], []
for d in sources:
    terr = os.path.join(d, "territory.txt")
    if not os.path.exists(terr):
        continue
    raw = [collapse(ln) for ln in open(terr, encoding="utf-8", errors="ignore")]
    raw = [x for x in raw if len(x) >= MIN]
    random.shuffle(raw)
    take = raw[:PER]
    if take:
        used.append((d, len(take)))
        lines += take
for d, n in used:
    print(f"  {d:13} {n:4d} docs", flush=True)
if len(used) < 2:
    sys.stderr.write("\nNeed at least two prior runs. Run ./demo-all.sh (or the "
                     "individual demos) first, then re-run this.\n")
    sys.exit(3)
random.shuffle(lines)
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"  pooled: {len(lines)} docs from {len(used)} prior runs", flush=True)
PY
RAW=$(wc -l < "$WORK/corpus.txt")
echo "  $(elapsed)"

# 2. evolve ONE population over the pooled corpus-of-corpora
GA_MIN=$(awk "BEGIN{printf \"%.1f\", $BUDGET*0.5}")
say "evolve — one meta-population over everything, for ~${GA_MIN} min"
echo "  (experts should carve out news / each language / each code kind / each notation)"
rm -rf demo-meta
python3 atn-ga.py run --corpus "$WORK/corpus.txt" --out demo-meta \
    --pop 40 --minutes "$GA_MIN" --chunk-on '.' --locus content --evolve-orders \
    --span-mb 0.05 --eval-frac 0.08 2>&1 | grep -E "chunks=|content index|gen|budget|honesty|best\]"
echo "  $(elapsed)"

# 3. one query of each kind — all routed by the SAME population
say "classify — route text of every kind against the one meta-population"
echo "  (news, three human languages, two kinds of code, two formal notations)"
printf '%s\n' \
  "the president addressed congress on the new tariff bill late last night" \
  "the river flows north through the mountains into the sea near the old city" \
  "de regering heeft een nieuwe wet over handel en belastingen aangenomen" \
  "这条河流穿过山脉向北流入大海靠近那座古老的城市和港口" \
  "int main(void){ struct node *p = malloc(sizeof(*p)); return p ? 0 : 1; }" \
  "00000000: 7f45 4c46 0201 0100 0000 0000 0000 0000  .ELF............" \
  "∀x (Human(x) → Mortal(x)) ∧ ∃y Loves(socrates, y) ; ¬Even(plato)" \
  "∫ sin(x) dx = -cos(x) + C ; lim_{x→0} sin(x)/x = 1 ; Σ_{n=1}^∞ 1/n^2" \
  | python3 atn-ga.py classify --out demo-meta

say "lightup — SEE that the meta-population grew a territory per kind"
echo "  a Dutch sentence:"
python3 atn-ga.py lightup --out demo-meta \
  "de rivier stroomt door de bergen naar de zee bij de oude stad in het noorden"
echo
echo "  a hex dump:"
python3 atn-ga.py lightup --out demo-meta \
  "00001a40: 4889 e5 4883 ec20 488d 3d12 0000 0048  H...H.. .H.=....H"
echo
echo "  a calculus worksheet:"
python3 atn-ga.py lightup --out demo-meta \
  "∫ cos(t) dt = sin(t) + C ; ∂f/∂x = 3x ; lim_{u→0} exp(u) = 1 ; Σ_{n=1}^∞ 1/n^2"

say "mixture — the meta-population AS one model over the corpus-of-corpora"
python3 atn-ga.py mixture --out demo-meta 2>&1 | grep -E "experts,|single|oracle|fixed-share|Bayes|beats|means:|character|complementary|POPULATION" || true

say "done in $(( $(date +%s) - T0 ))s"

cat <<'GUIDE'

────────────────────────────────────────────────────────────────────
WHAT YOU JUST SAW
  A population trained on the PREVIOUS TRAININGS — the pooled corpora the
  news / languages / code / formal demos each trained on. One brain-network
  now spans all of them: 1920s news, seven human languages, five kinds of
  code, six formal notations — and a query of any kind routes to its region.

  Nothing here is new machinery — it's the same GA over a corpus-of-corpora.
  That's the point: the approach COMPOSES. Feed it a pile of everything and it
  finds the coarse structure (natural language vs code vs formal vs news) and
  the finer structure inside, all unsupervised. This is the routable-mixture
  vision in miniature: keep pooling more corpora, keep tiling, lazily light up
  the right expert. Re-run after building more demos to fold them in too.

  python3 atn-ga.py lightup  --out demo-meta "text of any kind"
  ./ga-step.sh  demo-meta 10        # evolve the meta-population further
────────────────────────────────────────────────────────────────────
GUIDE
