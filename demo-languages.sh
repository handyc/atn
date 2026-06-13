#!/bin/sh
# demo-languages.sh — the crisp-separation companion to demo-news.sh.
#
# Builds atn, fetches random Wikipedia articles in FIVE languages, shuffles them
# into one corpus, then evolves a population of GA brains over it. On mixed
# languages the experts self-organise into one-per-language territories — so
# `lightup`/`classify` route an English sentence to the English expert, a French
# sentence to the French expert, etc. This is the clearest showcase for the
# "what does each expert specialise in?" feature: the answer is a different
# language for each one. (General news, in demo-news.sh, separates only subtly;
# distinct languages separate dramatically.)
#
#   ./demo-languages.sh [MINUTES]      # total time target, default 6
#
# Needs: a C compiler + make, python3 (stdlib only), internet. No local data.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
BUDGET="${1:-6}"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }
elapsed() { echo "[t+$(( $(date +%s) - T0 ))s]"; }

say "atn languages demo  (target ~${BUDGET} min)"

# 0. build the binary if needed
[ -x ./atn ] || { echo "$(elapsed) building atn ..."; make >/dev/null; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. fetch random Wikipedia articles in 5 languages (one cleaned article per line)
say "fetch — random Wikipedia articles in en / fr / de / es / it"
python3 - "$WORK/corpus.txt" <<'PY'
import json, sys, random, urllib.request, urllib.parse
out = sys.argv[1]
LANGS = ["en", "fr", "de", "es", "it"]
PER_LANG = 90                     # target articles per language
UA = "atn-demo/1.0 (educational; https://github.com/handyc/atn)"

def grab(lang, n):
    # exlimit=max is essential — without it the API returns only ONE extract per
    # request; exintro=1 gives a clean, present-for-every-page lead paragraph.
    q = {"format": "json", "formatversion": "2", "action": "query",
         "generator": "random", "grnnamespace": "0", "grnlimit": str(n),
         "prop": "extracts", "exlimit": "max", "exintro": "1", "explaintext": "1"}
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    return [p.get("extract", "") for p in data.get("query", {}).get("pages", [])]

def clean(text):                  # collapse an article lead to one capped line
    return " ".join(text.split())[:2800]

lines = []
for lang in LANGS:
    got, tries = [], 0
    while len(got) < PER_LANG and tries < 12:
        tries += 1
        try:
            for e in grab(lang, 20):
                c = clean(e)
                if len(c) >= 140:           # skip stubs
                    got.append(c)
        except Exception:
            continue
    print(f"  {lang}  {len(got):4d} articles", flush=True)
    lines += got[:PER_LANG]

random.seed(1)
random.shuffle(lines)                       # mix languages: position no longer hints topic
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"  total: {len(lines)} articles", flush=True)
PY
RAW=$(wc -l < "$WORK/corpus.txt")
[ "$RAW" -gt 100 ] || { echo "too little data fetched ($RAW lines) — network issue?"; exit 1; }
echo "  $(elapsed)"

# 2. clean / dedup for the pipeline
say "prep — clean + dedup (training-free)"
./atn --prep "$WORK/corpus.txt" > "$WORK/clean.txt" 2> "$WORK/prep.log" || true
sed -n 's/^atn: /  /p' "$WORK/prep.log"; echo "  $(elapsed)"

# 3. evolve a population, time-boxed to ~45% of the budget
GA_MIN=$(awk "BEGIN{printf \"%.1f\", $BUDGET*0.45}")
say "evolve — GA population (content loci) for ~${GA_MIN} min"
echo "  (experts should self-organise into one territory per language)"
rm -rf demo-langs
python3 atn-ga.py run --corpus "$WORK/clean.txt" --out demo-langs \
    --pop 24 --minutes "$GA_MIN" --chunk-on '.' --locus content --evolve-orders \
    --eval-frac 0.06 2>&1 | grep -E "chunks=|content index|gen|budget|honesty|best\]"
echo "  $(elapsed)"

# 4. example queries — each language should route to its own expert
say "classify — route a sentence in each language to its best-fit expert"
echo "  (watch the expert id change from language to language)"
printf '%s\n' \
  "the government passed a new law on trade and taxation this year" \
  "le gouvernement a adopté une nouvelle loi sur le commerce et les impots" \
  "die Regierung verabschiedete ein neues Gesetz über Handel und Steuern" \
  "el gobierno aprobó una nueva ley sobre el comercio y los impuestos" \
  "il governo ha approvato una nuova legge sul commercio e sulle tasse" \
  | python3 atn-ga.py classify --out demo-langs

say "lightup — route ONE query and SEE the chosen expert's own vocabulary"
echo "  English query -> English expert (its words should be English):"
python3 atn-ga.py lightup --out demo-langs \
  "the river flows north through the mountains into the sea near the old city"
echo
echo "  French query -> French expert (its words should be French):"
python3 atn-ga.py lightup --out demo-langs \
  "le fleuve traverse la ville et se jette dans la mer au nord du pays"

say "novelty — flag text unlike anything in the corpus"
echo "  (gibberish and an unseen script score as out-of-distribution)"
printf '%s\n' \
  "the small village sits beside a quiet river in the green valley" \
  "qx zzt 9999 ;;;; vbnm kkkk wpwp" \
  | python3 atn-ga.py novelty --out demo-langs

say "mixture — use the whole POPULATION as one language model"
echo "  (blends every expert per character; should beat any single expert)"
python3 atn-ga.py mixture --out demo-langs 2>&1 | grep -E "experts,|single|oracle|fixed-share|Bayes|beats|means:|character|complementary|POPULATION" || true

say "done in $(( $(date +%s) - T0 ))s"

cat <<'GUIDE'

────────────────────────────────────────────────────────────────────
WHAT YOU JUST SAW
  We grew a POPULATION of tiny "expert" models over a corpus mixing five
  languages. A genetic algorithm grouped articles by shared vocabulary —
  and with languages mixed together, the cleanest grouping IS by language,
  so each expert becomes a per-language specialist on its own.

    classify : each sentence routes to an expert specialised in its language
    lightup  : shows the chosen expert's actual words — a whole language
    novelty  : flags text unlike anything seen (gibberish, unseen scripts)
    mixture  : blends all experts into one cross-lingual model

  This is the same machinery as demo-news.sh — only the corpus changed.
  Distinct languages separate dramatically; a single uniform domain
  (1920s news) separates only subtly. The structure the GA can find is
  whatever structure the corpus actually contains.

TRY IT YOURSELF
  # route your own sentence in any of the five languages:
  python3 atn-ga.py lightup  --out demo-langs "a full sentence in some language"

  # batch-classify or novelty-check a file (one item per line):
  ./classify.sh demo-langs yourfile.txt
  ./novelty.sh  demo-langs yourfile.txt

  # keep evolving this population for 10 more minutes (resumable):
  ./ga-step.sh  demo-langs 10
────────────────────────────────────────────────────────────────────
GUIDE
