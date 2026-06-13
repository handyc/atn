#!/bin/sh
# demo-formal.sh — the third sibling of demo-languages.sh / demo-code.sh, for
# FORMAL languages: first-order logic, linear algebra, set theory, calculus,
# lambda calculus, and regular expressions.
#
# Formal systems are defined by GRAMMARS, so (unlike natural-language Wikipedia
# or sampled source code) we GENERATE the corpus from small generators — no
# network, no local data. Then we evolve a population over the mix and see which
# experts form.
#
# Honest result, baked into the closing notes: this is where the method's
# resolution runs out. Calculus, lambda calculus, linear algebra and regex form
# clean, operator-labelled territories — but first-order logic and set theory
# tend to BLUR into look-alike neighbours (to a byte/word n-gram, `∀x (P(x) →
# Q(x))` and `λx. f (x x)` are the *same shape*: binder + variables + parens +
# arrow). The model separates by surface form, not meaning — and these share it.
#
#   ./demo-formal.sh [MINUTES]      # total time target, default 6
#
# Needs: a C compiler + make, python3 (stdlib only). No network, no data.
set -e
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$HERE"
BUDGET="${1:-6}"
T0=$(date +%s)
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1" 2>/dev/null || printf '\n== %s ==\n' "$1"; }
elapsed() { echo "[t+$(( $(date +%s) - T0 ))s]"; }

say "atn formal-languages demo  (target ~${BUDGET} min)"

# 0. build the binary if needed
[ -x ./atn ] || { echo "$(elapsed) building atn ..."; make >/dev/null; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. GENERATE the corpus from grammars (one worksheet of formulas per line)
say "generate — synthesising FOL / linear algebra / set theory / calculus / lambda / regex"
python3 - "$WORK/corpus.txt" <<'PY'
import random, sys
random.seed(1)
PER = 70                       # worksheets per formal system (≈ the language demo)
pick = random.choice
V = ["x","y","z","u","v","w","n","m"]

def fol_term(): return pick(V+["a","b","c","socrates","plato","zero"])
def fol_atom():
    p=pick(["Human","Mortal","Loves","Knows","Parent","Greater","Even","Prime","Wise","King","Equal","Less"])
    return p+"("+",".join(fol_term() for _ in range(pick([1,1,2,2])))+")"
def fol():
    s=fol_atom()+" "+pick(["→","∧","∨","↔"])+" "+fol_atom()
    if random.random()<0.3: s="¬"+fol_atom()+" ∧ ("+s+")"
    return pick(["∀","∃"])+pick(V)+" ("+s+")"

def matrix(r,c): return "["+",".join("["+",".join(str(random.randint(-5,9)) for _ in range(c))+"]" for _ in range(r))+"]"
def linalg():
    t=random.random()
    if t<0.25: return "A = "+matrix(random.randint(2,3),random.randint(2,3))
    if t<0.45: return pick(["det","trace","rank"])+"("+pick("ABMN")+") = "+str(random.randint(-9,20))
    if t<0.65: return pick("ABM")+" * "+pick("xvb")+" = "+pick("byc")
    if t<0.8: return "transpose("+pick("AB")+") * "+pick("AB")
    if t<0.9: return "eigenvalues("+pick("AM")+") = {"+",".join(str(random.randint(-3,7)) for _ in range(random.randint(1,3)))+"}"
    return "||"+pick("vwu")+"|| = sqrt("+str(random.randint(2,99))+")"

def setx():
    S=pick(["A","B","C","S","T","X"]); T=pick(["A","B","C","S","T","Y"]); t=random.random()
    if t<0.3: return S+" ∪ "+T+" = { x | x ∈ "+S+" ∨ x ∈ "+T+" }"
    if t<0.5: return S+" ∩ "+T+pick([" = ∅"," ⊆ "+S])
    if t<0.65: return "powerset("+S+")"
    if t<0.8: return S+" ⊆ "+T
    if t<0.9: return "|"+S+"| = "+str(random.randint(0,12))
    return "complement("+S+") = U \\ "+S

def calc():
    f=pick(["sin","cos","exp","log","tan"]); v=pick(["x","t","u"]); t=random.random()
    if t<0.3: return "∫ "+f+"("+v+") d"+v
    if t<0.5: return "d/d"+v+" "+f+"("+v+")"
    if t<0.7: return "lim_{"+v+"→0} "+f+"("+v+")/"+v+" = 1"
    if t<0.85: return "Σ_{n=1}^∞ 1/n^"+str(random.randint(2,4))
    return "∂f/∂"+v+" = "+str(random.randint(1,9))+v

def lam():
    names=["succ","pred","zero","plus","mult","true","false","pair","fst","snd","compose","identity","church","iszero"]
    t=random.random()
    if t<0.25: return pick(names)+" = λ"+pick("nfxy")+". λ"+pick("fgx")+". "+pick("nfx")+" "+pick("fx")
    if t<0.45: return "("+pick(names)+" "+pick(names)+") → "+pick(names)
    if t<0.6: return "λf. λx. f (f x)"
    if t<0.75: return "true = λx. λy. x ; false = λx. λy. y"
    if t<0.9: return "compose "+pick(names)+" "+pick(names)
    return "λ"+pick("xyz")+". ("+pick("xyz")+" "+pick("xyz")+")"

def rgx():
    cls=pick(["[[:alpha:]]","[[:digit:]]","[[:space:]]","[[:upper:]]","[[:punct:]]",r"\d",r"\w",r"\s",r"\b"])
    grp=pick(["year","month","day","user","host","path","proto","port"])
    t=random.random()
    if t<0.25: return "(?P<"+grp+">[[:alnum:]]+)"+pick(["@","-","/",":"])+"(?P<"+pick(["host","path","tld"])+">"+cls+"+)"
    if t<0.45: return cls+"{"+str(random.randint(2,4))+","+str(random.randint(5,8))+"}"
    if t<0.6: return "match("+grp+"): "+cls+pick(["*","+","?"])
    if t<0.75: return "^"+cls+"+"+pick(["@",r"\."])+cls+"+$"
    if t<0.9: return "("+pick(["alpha","digit","word","anchor"])+"|"+pick(["space","punct","upper"])+")"
    return r"\b(?P<"+grp+">"+cls+r"+)\b"

gens = {"fol": fol, "linear-algebra": linalg, "set-theory": setx,
        "calculus": calc, "lambda-calculus": lam, "regex": rgx}
lines = []
for name, g in gens.items():
    c = 0
    while c < PER:
        d = " ".join(g() for _ in range(random.randint(16, 30)))   # a worksheet of formulas
        if len(d) >= 350:
            lines.append(d); c += 1
    print(f"  {name:16} {c} worksheets", flush=True)
random.shuffle(lines)                       # mix systems: position no longer hints type
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"  total: {len(lines)} worksheets", flush=True)
PY
RAW=$(wc -l < "$WORK/corpus.txt")
[ "$RAW" -gt 100 ] || { echo "generation failed ($RAW lines)"; exit 1; }
echo "  $(elapsed)"

# 2. evolve a population, time-boxed to ~45% of the budget
GA_MIN=$(awk "BEGIN{printf \"%.1f\", $BUDGET*0.45}")
say "evolve — GA population (content loci, symbol-aware) for ~${GA_MIN} min"
echo "  (the symbols ∀ ∃ ∈ ∪ λ ∫ are now tokens, so systems can cluster on them)"
rm -rf demo-formal
python3 atn-ga.py run --corpus "$WORK/corpus.txt" --out demo-formal \
    --pop 30 --minutes "$GA_MIN" --chunk-on '.' --locus content --evolve-orders \
    --span-mb 0.06 --eval-frac 0.1 2>&1 | grep -E "chunks=|content index|gen|budget|honesty|best\]"
echo "  $(elapsed)"

# 3. example queries — most systems route to their own expert; some look-alikes blur
say "classify — route a worksheet of each system to its best-fit expert"
echo "  (calculus / linear algebra / lambda / regex should land cleanly;"
echo "   watch first-order logic and set theory — they often share a look-alike)"
printf '%s\n' \
  "∀x (Human(x) → Mortal(x)) ∧ ∃y Loves(socrates, y) ; ∀z (King(z) → Wise(z)) ; ¬Even(plato)" \
  "det(A) = -3 ; A = [[1,2],[3,4]] ; transpose(B) * v = b ; eigenvalues(M) = {2,5} ; rank(A) = 2" \
  "A ∪ B = { x | x ∈ A ∨ x ∈ B } ; A ∩ B = ∅ ; powerset(S) ; complement(T) ; |A| = 5 ; A ⊆ C" \
  "∫ sin(x) dx = -cos(x) + C ; d/dx exp(x) ; lim_{x→0} sin(x)/x = 1 ; Σ_{n=1}^∞ 1/n^2" \
  "succ = λn. λf. λx. f (n f x) ; true = λx. λy. x ; compose pair fst ; λf. λx. f (f x)" \
  "(?P<year>[[:digit:]]{4})-(?P<month>\\d{2}) ; [[:alpha:]]+ ; match(host): \\w+ ; ^[a-z]+@\\w+\$" \
  | python3 atn-ga.py classify --out demo-formal

say "lightup — SEE what each chosen expert is made of (its operators + vocabulary)"
echo "  linear algebra (separates cleanly — should show det / transpose / eigenvalues):"
python3 atn-ga.py lightup --out demo-formal \
  "eigenvalues(A) = {2,5} ; det(B) = 7 ; transpose(M) * w = c ; rank(A) = 3 ; trace(N) = 1"
echo
echo "  first-order logic (the hard case — note it often lights up the λ expert,"
echo "  because a quantifier+variable+parens body looks just like a lambda term):"
python3 atn-ga.py lightup --out demo-formal \
  "∀x ∃y (Parent(x,y) → Mortal(y)) ∧ Wise(socrates) ; ∀z (Prime(z) → ¬Even(z))"

say "novelty — formal notation is so regular that anything else is wildly surprising"
echo "  (watch the bpb: a formula < English prose < gibberish; the corpus sits ~1 bpb)"
printf '%s\n' \
  "∫ cos(t) dt = sin(t) + C ; lim_{t→0} exp(t) = 1" \
  "the committee reviewed the quarterly report before the annual shareholder meeting" \
  "qx zzt 9999 ;;;; vbnm kkkk wpwp" \
  | python3 atn-ga.py novelty --out demo-formal

say "mixture — the whole POPULATION as one model over the formal corpus"
echo "  (blends every expert per byte; should beat any single expert)"
python3 atn-ga.py mixture --out demo-formal 2>&1 | grep -E "experts,|single|oracle|fixed-share|Bayes|beats|means:|character|complementary|POPULATION" || true

say "done in $(( $(date +%s) - T0 ))s"

cat <<'GUIDE'

────────────────────────────────────────────────────────────────────
WHAT YOU JUST SAW  (and where the method's resolution runs out)
  Same machinery as the language and code demos, on a corpus GENERATED from
  the grammars of six formal systems. The symbol-aware tokenizer lets each
  cluster on its defining operators, and most do separate:

    calculus        ∫ ∂ Σ lim sin cos exp
    lambda calculus λ compose succ true church pair
    linear algebra  det transpose eigenvalues rank trace
    regex           [[:alnum:]] digit host match \d \w

  BUT first-order logic and set theory tend to BLUR into look-alikes. This is
  the honest finding, not a bug: atn judges text by its SURFACE FORM, and to a
  byte/word n-gram

        ∀x (P(x) → Q(x))        and        λx. f (x x)

  are the same shape — a binder, single-letter variables, parentheses, an
  arrow. They mean utterly different things; they *look* identical. Natural
  languages and code separated cleanly because their surfaces differ a lot;
  these formal systems share theirs. Formal notation is also ultra-low-entropy
  (corpus ≈ 1 bit/byte vs ~3 for prose), so the experts sit very close and
  short queries route unreliably — trust longer worksheets and the rankings.

  The lesson of this demo is its limit: surface statistics ≠ meaning. Telling
  ∀ from λ needs a model of what the symbols DO, which n-grams don't have.

TRY IT YOURSELF
  python3 atn-ga.py lightup  --out demo-formal "a worksheet of formulas"
  ./classify.sh demo-formal somefile.txt
  ./ga-step.sh  demo-formal 10        # evolve it 10 more minutes
────────────────────────────────────────────────────────────────────
GUIDE
