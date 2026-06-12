#!/bin/sh
# where.sh — find WHERE a (trending) phrase occurs in a corpus / brain.
# The brain file is the corpus text (one article per line, as built by
# --train), so each match is located by its line = article index, shown with a
# window of surrounding context.
#
#   where.sh CORPUS "phrase"            # locate one phrase
#   autotrend.sh today.brain yest.brain | awk 'NR>1{$1=$2=$3=$4=$5="";print}' \
#     | head -5 | while read p; do where.sh today.brain "$p"; done   # locate the top trends
#
# Env: MAX=8 (matches shown), WIN=45 (context chars each side).
CORPUS="$1"; PHRASE="$2"
[ -n "$PHRASE" ] || { echo "usage: where.sh CORPUS \"phrase\""; exit 2; }
[ -f "$CORPUS" ] || { echo "corpus not found: $CORPUS"; exit 2; }
MAX="${MAX:-8}"; WIN="${WIN:-45}"

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
