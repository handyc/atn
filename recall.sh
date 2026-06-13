#!/bin/sh
# recall.sh — non-parametric retrieval. Given a context, return the REAL text
# that followed it in the corpus/brain(s), with provenance. Unlike the chat
# (which remixes and can hallucinate), this shows actual source passages — the
# surface-level cousin of a kNN-LM datastore lookup.
#
#   recall.sh BRAIN_OR_DIR "context phrase"
#
# Env: MAX=6 (passages per source), AFTER=90 (chars of continuation shown).
SRC="$1"; PHRASE="$2"
[ -n "$PHRASE" ] || { echo "usage: recall.sh BRAIN_OR_DIR \"context\""; exit 2; }
MAX="${MAX:-6}"; AFTER="${AFTER:-90}"

if [ -d "$SRC" ]; then files=$(ls "$SRC"/*.brain 2>/dev/null); else files="$SRC"; fi
[ -n "$files" ] || { echo "no corpus/brain found at $SRC"; exit 2; }

printf '\033[1mrecall "%s":\033[0m\n' "$PHRASE"
hits=0
for f in $files; do
    grep -i -n -F -- "$PHRASE" "$f" 2>/dev/null | head -n "$MAX" \
      | awk -F: -v p="$PHRASE" -v after="$AFTER" -v src="$(basename "$f")" '
          { ln=$1; sub(/^[0-9]+:/,"",$0); text=$0
            i=index(tolower(text), tolower(p)); if(i==0) next
            cont=substr(text, i, length(p)+after)
            gsub(/^[ \t]+|[ \t]+$/,"",cont)
            printf "  [%s:%s] …%s…\n", src, ln, cont }'
    n=$(grep -i -c -F -- "$PHRASE" "$f" 2>/dev/null); hits=$((hits + ${n:-0}))
done
[ "$hits" -gt 0 ] || echo "  (no occurrences found)"
