#!/bin/sh
# where.sh — find WHERE (and, with metadata, in which place/when) a phrase occurs.
# The corpus is one article per line (as built by --train / build-corpus.sh), so
# each match is located by its line = article index, shown with context. If a
# PREFIX.meta sidecar exists (date<TAB>state<TAB>paper per line, from
# build-corpus.sh), it also reports the distribution by state and by date.
#
#   where.sh CORPUS "phrase"
#   autotrend.sh today.brain yest.brain | tail -n +2 \
#     | awk '{$1=$2=$3=$4=$5=""; sub(/^ +/,""); print}' \
#     | while read -r p; do where.sh today.txt "$p"; done   # top trends + where
#
# Env: MAX=8 (context matches shown), WIN=45 (context chars), GEO=6 (top places/dates).
CORPUS="$1"; PHRASE="$2"
[ -n "$PHRASE" ] || { echo "usage: where.sh CORPUS \"phrase\""; exit 2; }
[ -f "$CORPUS" ] || { echo "corpus not found: $CORPUS"; exit 2; }
MAX="${MAX:-8}"; WIN="${WIN:-45}"; GEO="${GEO:-6}"

count=$(grep -i -c -F -- "$PHRASE" "$CORPUS" 2>/dev/null); count=${count:-0}
printf '\033[1m"%s"\033[0m — in %s article(s)/line(s) of %s\n' "$PHRASE" "$count" "$CORPUS"
[ "$count" -gt 0 ] || exit 0

grep -i -n -F -- "$PHRASE" "$CORPUS" 2>/dev/null | head -n "$MAX" \
  | awk -F: -v p="$PHRASE" -v win="$WIN" '
      { ln=$1; sub(/^[0-9]+:/, "", $0); text=$0;
        i=index(tolower(text), tolower(p)); if(i==0) next;
        s=i-win; if(s<1) s=1; len=length(p)+2*win;
        snip=substr(text, s, len); gsub(/^[ \t]+|[ \t]+$/, "", snip);
        printf "  line %-7s …%s…\n", ln, snip }'

# geographic + temporal distribution, if a .meta sidecar is present
meta=""
for c in "$CORPUS.meta" "${CORPUS%.txt}.meta" "${CORPUS%.brain}.meta"; do
    [ -f "$c" ] && { meta="$c"; break; }
done
if [ -n "$meta" ]; then
    tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
    grep -i -n -F -- "$PHRASE" "$CORPUS" 2>/dev/null | cut -d: -f1 > "$tmp"
    tally() {  # $1 = meta field index (2=state, 1=date)
        awk -F'\t' -v lf="$tmp" -v f="$1" \
            'BEGIN{while((getline x < lf) > 0) w[x]=1} (FNR in w){print $f}' "$meta" \
          | sort | uniq -c | sort -rn | head -n "$GEO" \
          | awk '{c=$1; $1=""; sub(/^ +/,""); printf " %s(%s)", $0, c}'
    }
    printf '  where (state):'; tally 2; echo
    printf '  when (date):  '; tally 1; echo
fi
