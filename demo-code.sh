#!/bin/sh
# demo-code.sh — demo-languages.sh's sibling, but the "languages" are CODE.
#
# Samples the LOCAL filesystem (no network) for five kinds of machine text —
# C, Python, shell, x86-64 assembly, and hex/binary dumps — shuffles them into
# one corpus, and evolves a population of GA brains over it. With the kinds
# mixed together the experts self-organise by *kind*, so `classify`/`lightup`
# route a C snippet to the C expert, a hex dump to the hex expert, and so on —
# which is fitting, since atn is a file/binary analysis tool to begin with.
#
#   ./demo-code.sh [MINUTES]      # total time target, default 6
#
# Needs: a C compiler + make, python3 (stdlib only), and ideally objdump + xxd
# (falls back to atn's own -D / -x if those are missing). No pre-existing data.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
BUDGET="${1:-6}"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }
elapsed() { echo "[t+$(( $(date +%s) - T0 ))s]"; }

say "atn code demo  (target ~${BUDGET} min)"

# 0. build the binary if needed
[ -x ./atn ] || { echo "$(elapsed) building atn ..."; make >/dev/null; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. gather a code corpus from the local filesystem (one document per line)
say "gather — sampling C / Python / shell / asm / hex from the filesystem"
python3 - "$WORK/corpus.txt" <<'PY'
import os, sys, glob, random, shutil, subprocess
out = sys.argv[1]
random.seed(1)
PER, CAP, MIN = 70, 3000, 220

def collapse(t):
    return " ".join(t.split())[:CAP]

def is_elf(p):
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except Exception:
        return False

def sample_text(paths, want, pred=None):
    paths = list(paths); random.shuffle(paths)
    docs = []
    for p in paths:
        if len(docs) >= want:
            break
        if not os.path.isfile(p) or os.path.islink(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                t = f.read(20000)
        except Exception:
            continue
        if pred and not pred(t):
            continue
        c = collapse(t)
        if len(c) >= MIN:
            docs.append(c)
    return docs

def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=timeout).stdout.decode("utf-8", "ignore")
    except Exception:
        return ""

cats = {}
# --- source languages ---
cats["c"] = sample_text(glob.glob("/usr/include/**/*.h", recursive=True)
                        + glob.glob("*.c") + glob.glob("*.h"), PER)
cats["python"] = sample_text(glob.glob("/usr/lib/python3*/**/*.py", recursive=True)
                            + glob.glob("*.py"), PER)
def is_sh(t):
    first = (t.splitlines() or [""])[0]
    return first.startswith("#!") and ("sh" in first or "bash" in first)
cats["shell"] = sample_text(glob.glob("/usr/bin/*") + glob.glob("/bin/*") + glob.glob("*.sh"),
                            PER, pred=is_sh)

# --- assembly + hex, from ELF binaries (objdump/xxd, atn fallbacks) ---
elfs = [p for p in glob.glob("/usr/bin/*") + glob.glob("/usr/lib/**/*.so*", recursive=True)
        if not os.path.islink(p) and is_elf(p)]
random.shuffle(elfs)
have_objdump, have_xxd = shutil.which("objdump"), shutil.which("xxd")
asm, hexd = [], []
for p in elfs:
    if len(asm) >= PER and len(hexd) >= PER:
        break
    if len(asm) < PER and os.path.getsize(p) < 300000:     # keep disasm bounded
        o = (run(["objdump", "-d", "--no-show-raw-insn", p]) if have_objdump
             else run(["./atn", "-q", "-D", p]))
        c = collapse(o)
        if len(c) >= MIN:
            asm.append(c)
    if len(hexd) < PER:
        o = (run(["xxd", "-l", "1600", p]) if have_xxd
             else run(["./atn", "-q", "-x", "-n", "1500", p]))
        c = collapse(o)
        if len(c) >= MIN:
            hexd.append(c)
cats["asm"], cats["hex"] = asm, hexd

lines = []
for k, v in cats.items():
    print(f"  {k:7} {len(v):4d} docs", flush=True)
    lines += v
random.shuffle(lines)                       # mix kinds: position no longer hints type
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"  total: {len(lines)} documents", flush=True)
PY
RAW=$(wc -l < "$WORK/corpus.txt")
[ "$RAW" -gt 100 ] || { echo "too few documents gathered ($RAW) — unusual filesystem?"; exit 1; }
echo "  $(elapsed)"

# NB: no --prep here. prep's quality filter is tuned for natural-language prose
# and would drop low-letter text like hex dumps and assembly as "garbage" — which
# is correct for LLM data prep, but wrong for a corpus that is *meant* to be code.

# 2. evolve a population, time-boxed to ~45% of the budget
GA_MIN=$(awk "BEGIN{printf \"%.1f\", $BUDGET*0.45}")
say "evolve — GA population (content loci) for ~${GA_MIN} min"
echo "  (experts should self-organise into one territory per kind of code)"
rm -rf demo-code
python3 atn-ga.py run --corpus "$WORK/corpus.txt" --out demo-code \
    --pop 28 --minutes "$GA_MIN" --chunk-on '.' --locus content --evolve-orders \
    --span-mb 0.05 --eval-frac 0.08 2>&1 | grep -E "chunks=|content index|gen|budget|honesty|best\]"
echo "  $(elapsed)"

# 3. example queries — each kind of code should route to its own expert
say "classify — route a snippet of each kind to its best-fit expert"
echo "  (watch the expert id change from C to Python to shell to asm to hex)"
printf '%s\n' \
  "static int cmp(const void *a, const void *b) { return *(const int*)a - *(const int*)b; }" \
  "def load(path): import json; return json.load(open(path)) if path.endswith('.json') else None" \
  "for f in \"\$@\"; do [ -f \"\$f\" ] && echo \"\$f\" || printf 'missing %s\\n' \"\$f\"; done" \
  "push %rbp ; mov %rsp,%rbp ; sub \$0x10,%rsp ; callq 1040 <printf> ; xor %eax,%eax ; leaveq ; retq" \
  "00000000: 7f45 4c46 0201 0100 0000 0000 0000 0000  .ELF............" \
  | python3 atn-ga.py classify --out demo-code

say "lightup — route ONE snippet and SEE the chosen expert's own vocabulary"
echo "  C snippet -> C expert (its words should be C keywords/identifiers):"
python3 atn-ga.py lightup --out demo-code \
  "int main(int argc, char **argv) { struct node *p = malloc(sizeof(*p)); return p ? 0 : 1; }"
echo
echo "  hex line -> the hex/binary expert:"
python3 atn-ga.py lightup --out demo-code \
  "00001a40: 4889 e5 4883 ec20 488d 3d12 0000 0048  H...H.. .H.=....H"

say "novelty — surprise climbs as text gets less code-like"
echo "  (watch the bpb column rise: a code line < English prose < gibberish."
echo "   the corpus is so predictable that the NOVEL flag's auto-threshold is"
echo "   strict — it's the ordering that's the signal, same as with lightup.)"
printf '%s\n' \
  "int x = 0; while (x < 10) { x = x + 1; }" \
  "the quick brown fox jumps over the lazy dog near the quiet river at dawn" \
  "qx zzt 9999 ;;;; vbnm kkkk wpwp" \
  | python3 atn-ga.py novelty --out demo-code

say "mixture — use the whole POPULATION as one model over the code corpus"
echo "  (blends every expert per byte; should beat any single expert)"
python3 atn-ga.py mixture --out demo-code 2>&1 | grep -E "experts,|single|oracle|fixed-share|Bayes|beats|means:|character|complementary|POPULATION" || true

say "done in $(( $(date +%s) - T0 ))s"

cat <<'GUIDE'

────────────────────────────────────────────────────────────────────
WHAT YOU JUST SAW
  Same machinery as demo-languages.sh — only the corpus changed from human
  languages to MACHINE text: C, Python, shell, x86-64 assembly, and hex /
  binary dumps, all sampled from this machine's own filesystem. With the
  kinds mixed and shuffled, the GA's cleanest grouping is by KIND, so each
  expert becomes a specialist: the C expert keys on include/struct/int, the
  Python one on def/import/self, asm on mov/push/call, hex on its narrow
  0-9a-f alphabet. This is atn on home turf — it began as a tool for telling
  what a file *is* from its bytes.

    classify : each snippet routes to the expert for its kind of code
    lightup  : shows that expert's actual vocabulary (keywords / mnemonics)
    novelty  : best-expert surprise — climbs from code to prose to gibberish
    mixture  : blends all experts into one model over the code

TRY IT YOURSELF
  # route your own snippet (one line works best):
  python3 atn-ga.py lightup  --out demo-code "your line of code here"

  # batch-classify or novelty-check a file (one item per line):
  ./classify.sh demo-code somefile.txt
  ./novelty.sh  demo-code somefile.txt

  # keep evolving this population for 10 more minutes (resumable):
  ./ga-step.sh  demo-code 10
────────────────────────────────────────────────────────────────────
GUIDE
