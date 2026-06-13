#!/bin/sh
# regression.sh — fast, deterministic, network-free regression suite for atn.
# Locks in the invariants this codebase relies on. Run: make test  (or ./tests/regression.sh)
set -u
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0 fail=0
ok()   { pass=$((pass+1)); printf '  \033[32mPASS\033[0m %s\n' "$1" 2>/dev/null || printf '  PASS %s\n' "$1"; }
bad()  { fail=$((fail+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1" 2>/dev/null || printf '  FAIL %s\n' "$1"; }

echo "== build =="
make >/dev/null 2>&1 && [ -x ./atn ] && ok "atn builds" || { bad "atn builds"; echo "build failed"; exit 1; }

echo "== core atn =="
# 1. lossless compression round-trip
printf 'the quick brown fox jumps over the lazy dog, again and again.\n%s\n' \
  "$(seq 1 50)" > "$TMP/c.txt"
./atn --compress "$TMP/c.txt" -o "$TMP/c.atcm" >/dev/null 2>&1
./atn --decompress "$TMP/c.atcm" -o "$TMP/c.out" >/dev/null 2>&1
cmp -s "$TMP/c.txt" "$TMP/c.out" && ok "compress -> decompress is lossless" || bad "compress round-trip"

# 2. --score is deterministic
printf 'hello world this is a test line\n' > "$TMP/s.txt"
./atn --train "$TMP" --brain "$TMP/b.brain" -q >/dev/null 2>&1
A=$(printf 'a deterministic query line\n' | ./atn --score --brain "$TMP/b.brain" 2>/dev/null)
B=$(printf 'a deterministic query line\n' | ./atn --score --brain "$TMP/b.brain" 2>/dev/null)
[ "$A" = "$B" ] && [ -n "$A" ] && ok "--score is deterministic" || bad "--score determinism"

# 3. --seed changes generation, but a fixed seed is reproducible
G1=$(printf 'seed test\n' | ./atn --ask --brain "$TMP/b.brain" --no-learn --seed 111 2>/dev/null)
G2=$(printf 'seed test\n' | ./atn --ask --brain "$TMP/b.brain" --no-learn --seed 111 2>/dev/null)
G3=$(printf 'seed test\n' | ./atn --ask --brain "$TMP/b.brain" --no-learn --seed 222 2>/dev/null)
[ "$G1" = "$G2" ] && [ "$G1" != "$G3" ] && ok "--seed reproducible yet varies" || bad "--seed behaviour"

echo "== text vs binary (is_texty) =="
mkdir -p "$TMP/mix"
printf 'plain english training text for the ingest check here today.\n' > "$TMP/mix/a.txt"
printf '这是中文文本用于训练目的需要足够长以通过文本检测阈值的句子内容。\n' > "$TMP/mix/zh.txt"
head -c 4000 /dev/urandom > "$TMP/mix/rand.bin"
N=$(./atn --train "$TMP/mix" --brain "$TMP/mix.brain" -q 2>&1 | grep -oE 'ingested [0-9]+' | grep -oE '[0-9]+')
[ "$N" = "2" ] && ok "is_texty: UTF-8 in (incl. Chinese), binary out (2 files)" || bad "is_texty ingested $N (expected 2)"

echo "== prep keeps non-Latin =="
printf '%s\n%s\n%s\n' \
  '这条河流穿过山脉向北流入大海靠近那座古老的城市和港口附近的村庄居民生活' \
  'qx zzt 9999 ;;;; vbnm' \
  'the committee reviewed the quarterly report before the meeting today here' > "$TMP/p.txt"
KEPT=$(./atn --prep "$TMP/p.txt" 2>/dev/null \
  | python3 -c "import sys,re; print(sum(1 for l in sys.stdin if re.search('[㐀-鿿]', l)))")
[ "${KEPT:-0}" -ge 1 ] && ok "--prep keeps Chinese (not dropped as garbage)" || bad "--prep dropped Chinese"

echo "== content neighbours determinism =="
: > "$TMP/terr.txt"; off=0; : > "$TMP/idx.tsv"
i=0
for w in alpha beta gamma delta alpha beta gamma delta epsilon zeta alpha beta; do
  line="the $w $w token line number $i with $w repeated for signature"
  printf '%s\n' "$line" >> "$TMP/terr.txt"
  blen=$(printf '%s\n' "$line" | wc -c)
  printf '%d\t%d\t%d\n' "$i" "$off" "$blen" >> "$TMP/idx.tsv"
  off=$((off+blen)); i=$((i+1))
done
./atn --neighbors "$TMP/terr.txt" --nn-index "$TMP/idx.tsv" -o "$TMP/n1.bin" 2>/dev/null
./atn --neighbors "$TMP/terr.txt" --nn-index "$TMP/idx.tsv" -o "$TMP/n2.bin" 2>/dev/null
cmp -s "$TMP/n1.bin" "$TMP/n2.bin" && [ -s "$TMP/n1.bin" ] && ok "--neighbors is deterministic" || bad "--neighbors determinism"

echo "== atn-ga pipeline + export =="
python3 -c "import ast; ast.parse(open('atn-ga.py').read())" 2>/dev/null && ok "atn-ga.py parses" || bad "atn-ga.py parse"
# tiny end-to-end run (distinct kinds -> experts), then export
{ for k in 1 2 3 4 5 6; do
    printf 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi\n'
    printf 'mov push call rax rbp rsp lea xor ret jmp test sub add cmp leaveq endbr\n'
    printf 'def import return self class lambda yield assert except finally raise with\n'
  done; } > "$TMP/corpus.txt"
if python3 atn-ga.py run --corpus "$TMP/corpus.txt" --out "$TMP/run" --atn ./atn \
     --pop 6 --gens 2 --chunk-on '.' --locus content --eval-frac 0.2 >/dev/null 2>&1; then
  ok "atn-ga run completes"
  python3 atn-ga.py export --out "$TMP/run" --name t --dest "$TMP/run" >/dev/null 2>&1
  for f in experts.csv history.csv terms.csv edges.csv atlas.db; do
    [ -s "$TMP/run/$f" ] && ok "export produced $f" || bad "export missing $f"
  done
  python3 - "$TMP/run/atlas.db" <<'PY' && ok "atlas.db has all tables" || bad "atlas.db tables"
import sqlite3, sys
t = {r[0] for r in sqlite3.connect(sys.argv[1]).execute("select name from sqlite_master where type='table'")}
sys.exit(0 if {"run","expert","passage","edge","generation","term"} <= t else 1)
PY
else
  bad "atn-ga run completes"
fi

echo "== web app config =="
if command -v python3 >/dev/null && python3 -c "import django" 2>/dev/null; then
  python3 web/manage.py check >/dev/null 2>&1 && ok "django check passes" || bad "django check"
else
  echo "  SKIP django check (django not installed)"
fi

echo
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
