#!/bin/sh
# build-corpus.sh — build a dated/geo-tagged news corpus from the AmericanStories
# (Chronicling America OCR) dataset on HuggingFace.
#
#   build-corpus.sh YEAR PREFIX [MAXBYTES]
#   build-corpus.sh 1934 news1934 18000000
#
# Produces TWO line-aligned files:
#   PREFIX.txt   one article per line (the corpus you --train on)
#   PREFIX.meta  one line per article: date <TAB> state <TAB> paper
# where.sh uses the .meta sidecar to report where/when a phrase appears.
set -e
YEAR="$1"; PREFIX="$2"; MAX="${3:-18000000}"
[ -n "$PREFIX" ] || { echo "usage: build-corpus.sh YEAR PREFIX [MAXBYTES]"; exit 2; }
URL="https://huggingface.co/datasets/dell-research-harvard/AmericanStories/resolve/main/faro_${YEAR}.tar.gz"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

echo "streaming ~$((MAX/1000000)) MB of $YEAR from AmericanStories ..."
curl -sL --max-time 600 "$URL" | head -c "$MAX" > "$tmp/part.tgz" || true
tar -xzf "$tmp/part.tgz" -C "$tmp" 2>/dev/null || true   # partial tar: keeps complete leading files

python3 - "$tmp" "$PREFIX" <<'PY'
import sys, json, glob, os
root, pref = sys.argv[1], sys.argv[2]
txt  = open(pref + ".txt",  "w")
meta = open(pref + ".meta", "w")
n = 0
for fn in sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True)):
    try: d = json.load(open(fn))
    except Exception: continue
    lccn  = d.get("lccn", {}) or {}
    ed    = d.get("edition", {}) or {}
    state = (lccn.get("state") or "?").strip() or "?"
    paper = ((lccn.get("title") or "?").split("[")[0].strip() or "?")[:40]
    date  = (ed.get("date") or (d.get("scan", {}) or {}).get("date") or "?")
    for a in (d.get("full articles") or []):
        t = (a.get("article") or "").replace("\n", " ").strip()
        if len(t) > 120:
            txt.write(t + "\n")
            meta.write(f"{date}\t{state}\t{paper}\n")
            n += 1
print(f"  {n} articles -> {pref}.txt + {pref}.meta")
PY

# optional: clean it into an LLM-ready corpus in the same step
if [ "$4" = "--prep" ] || [ "$5" = "--prep" ]; then
    ATN="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/atn"
    "$ATN" --prep "${PREFIX}.txt" > "${PREFIX}.clean.txt"
    echo "  cleaned -> ${PREFIX}.clean.txt  (ready to fine-tune a real model)"
fi

echo "next:  ./prepare-llm.sh out ${PREFIX}.txt          (clean+shuffle+split -> train/val)"
echo "  or:  ./atn --prep ${PREFIX}.txt > ${PREFIX}.clean.txt   (just clean for LLM training)"
echo "  or:  ./atn --train ${PREFIX}.txt --brain ${PREFIX}.brain -q   (build a brain)"
echo "  or:  ./where.sh ${PREFIX}.txt \"some phrase\"            (where/when it appears)"
