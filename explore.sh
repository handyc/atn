#!/bin/sh
# explore.sh — an interactive menu for poking at atn's features on one file.
# Usage:  ./explore.sh [FILE]      (prompts for a file if none given)
A=./atn
[ -x "$A" ] || { echo "build first:  make"; exit 1; }

FILE="$1"
prompt_file() {
    printf 'File to inspect: '
    IFS= read -r FILE
}
[ -n "$FILE" ] || prompt_file

pause() { printf '\n\033[2m(enter to continue)\033[0m'; IFS= read -r _; }

menu() {
    clear 2>/dev/null
    printf '\033[1m┌─ atn explorer ─────────────────────────────┐\033[0m\n'
    printf '  file: %s\n' "$FILE"
    cat <<'EOF'
  ────────────────────────────────────────────
   1  overview        (type, size, entropy)
   2  statistics      (-S  chi2, serial corr, noise)
   3  entropy map     (-E  find embedded/encrypted)
   4  structure       (-T  parse the format)
   5  attention head  (-Z  the fake transformer)
   6  feedback loop   (-B  context mixing + surprisal map)
   7  predict / bits  (-Z, just the LM numbers)
   8  generate text   (-Z --temp, sampling)
   9  compress        (-X  context-mixing, beats gzip -9)
  10  hex dump        (-x)
  11  strings         (-s)
  12  opcode scan     (-P)
  ────────────────────────────────────────────
   k  chat with atn   (-c  learns from what you type)
   f  change file      a  EVERYTHING (-A)      q  quit
EOF
    printf ' choose: '
}

run() { printf '\n'; "$A" "$@" 2>&1 | ${PAGER:-cat}; }

while :; do
    menu
    IFS= read -r c || break
    case "$c" in
        1)  run "$FILE" ;;
        2)  run -q -S "$FILE" ;;
        3)  run -q -E "$FILE" ;;
        4)  run -q -T "$FILE" ;;
        5)  run -q -Z "$FILE" ;;
        6)  run -q -B "$FILE" ;;
        7)  printf '\n'; "$A" -q -Z "$FILE" 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' \
                | grep -E "cross-entropy|would compress|induction head|next-byte|order|m=8" ;;
        8)  printf 'temperature [0.7]: '; IFS= read -r t; t=${t:-0.7}
            printf '\n'; "$A" -q -Z --temp "$t" --gen 240 "$FILE" 2>/dev/null \
                | sed 's/\x1b\[[0-9;]*m//g' | grep -A1 'generated .* bytes' ;;
        9)  run -q -X "$FILE" ;;
        10) run -q -x "$FILE" ;;
        11) run -q -s "$FILE" ;;
        12) run -q -P "$FILE" ;;
        k|K) "$A" -c ;;
        a|A) run -A "$FILE" ;;
        f|F) prompt_file; continue ;;
        q|Q) break ;;
        *)  printf '?\n' ;;
    esac
    pause
done
echo "bye."
