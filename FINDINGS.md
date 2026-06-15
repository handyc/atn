# Class-4 cellular automata as reservoirs and programmable substrates — findings

A consolidated, honest report of a multi-session investigation into using the
user's class-4 hexagonal cellular automata (the "mandelhunt" 7→1, K=4 hex rule)
for byte prediction and computation. It states plainly what is confirmed, what is
prior art we re-derived, what is contested, and what appears genuinely novel.
Companion docs: `CA-LAB-LOG.md` (chronological log), `LITERATURE.md` (novelty map).

## TL;DR

1. **Structured ≫ random, robustly.** An evolved network of class-4 hex CAs used as
   a reservoir beats a random-rule reservoir decisively and consistently (8 seeds ×
   3 corpora, Cohen's d = 2.2–3.9). This overturned an early blanket "CA-as-predictor
   doesn't work" conclusion.
2. **But class-4 is *not* uniquely special.** Head-to-head, class-4 rules **tie**
   structured *linear* (class-3) rules; both crush random. So the real claim is
   "structured beats random," not "class-4 is the magic ingredient" — matching the
   reservoir-computing literature.
3. **The fractal rule-generator is the novel, valuable piece.** Posterising
   Mandelbrot/Julia/Newton escape-time images into K=4 hex rule tables yields class-4
   rules at a **dimension-invariant ~⅓ rate** (N=2→5), where random search yields ~0%
   at N≥2. Julia/Newton beat Mandelbrot for yield. No prior art was found for
   escape-time-fractal → CA-rule generation.
4. **The prediction ceiling is the linear readout, not the reservoir.** Scaling
   (more nodes, depth, islands), symmetry priors, extra input ports (cell8/10/11), and
   data-conditioned rule selection all hit the same ceiling. Mixing reservoir features
   into an n-gram decoder gives the only (tiny, +0.037 bpb) gain over the n-gram.
5. **cell-11 as a programmable CA:** instruction-driven ops + glider signal transport
   + a port-controlled 1-bit gate all work; glider-collision logic gates are
   structurally blocked because fractal-derived rules are anisotropic (unidirectional
   gliders → no collisions).

## Prior art (independently re-derived — NOT novel)

- **Reservoir Computing with CAs (ReCA):** Yilmaz 2014–15 (arXiv:1410.0162,
  1503.00851); named by Margem & Yilmaz 2016; Nichele's group 2017 (arXiv:1702.03812).
- **GA over CA rules for computation:** Mitchell, Crutchfield & Hraber 1993
  (adap-org/9303003); Packard 1988.
- **Coupled / non-uniform CA reservoirs:** Nichele & Gundersen 2017.
- **Hexagonal K=4 CAs (the substrate itself):** Wuensche & Gómez-Soto, DDLab iso-rules
  (arXiv:2008.11279) — explicit "v4k4 hex 2d" examples + input-entropy classification
  for glider/class-4 dynamics. Wuensche+Adamatzky Spiral rule (hex multi-state
  computation). **The 7→1 hex K=4 class-4 CA is Wuensche territory.**
- **"Edge of chaos is best" is contested in the literature** (and we confirmed it):
  best ReCA rules are often class-3 (Yilmaz 2015); λ alone insufficient (Sakai-Kanno
  2002 λ-F; Mitchell 1993 refutes the λ-clustering claim); Carroll 2020 "Do Reservoir
  Computers Work Best at the Edge of Chaos?" Fractals link to class-3, not class-4
  (Culik & Dube 1989).

## Confirmed results (with numbers)

**Class-4 reservoir vs random (held-out, 8 seeds × 3 corpora):**

| corpus | class-4 acc | random acc | Cohen's d |
|---|---|---|---|
| news | 0.199±0.039 | 0.127±0.027 | 2.2 |
| code | 0.101±0.023 | 0.033±0.007 | 3.9 |
| languages | 0.177±0.027 | 0.096±0.020 | 3.4 |

**Class-4 vs linear class-3 vs random** (same protocol): class-4 ties linear
(news d+0.2, code d+0.6, langs d0.0); both ≫ random. → structure, not class-4 per se.

**Fractal generator — class-4 yield by family** (100 samples each): Julia 45% ·
Newton 35% (most diverse) · Burning Ship 30% · Mandelbrot 25% · Multibrot z³ 17%.

**Dimension-invariance** (N-dim von Neumann, 9,600 fractal rules): %class-4 =
32.5 / 33.6 / 31.1 / 31.5 % at N = 2 / 3 / 4 / 5 — flat ~⅓; random rules ~0% at N≥2.
A 2D-hex class-4 rule run as a 3D cubic rule stays class-4 **91%** of the time
(54k-rule library).

**Symmetry prior** (hex C6/D6): shrinks rule space 5.9×/9.5× but *lowers* class-4
yield (43%→26–28%; isotropy over-stabilises) → a soft, GA-selectable prior, not a
hard constraint.

**Reservoir vs n-gram:** reservoir ≈ 3.78 bpb, atn n-gram ≈ 3.51 bpb (n-gram wins).
Arithmetic mixture (0.88 n-gram + 0.12 reservoir) = 3.771 vs 3.807 → reservoir adds a
little complementary info; small and single-run.

## Negative / null results (honest)

- **Scaling the reservoir doesn't help.** A large island-GA with depth-3 hierarchical
  reservoirs, up to 10 nodes / 40×40, 384-rule pools → converged to *small* nets, no
  gain. The ceiling is the linear readout's feature span.
- **Extra input ports (cell8/10/11) don't help prediction.** Free-routing GA turns
  ports off; forced-on rich routing loses to ports-off (additive port modulation
  pushes toward chaos).
- **Data-conditioned rule selection (matching pursuit)** ties a random draw on fresh
  data (train-residual greedy overfits; held-out greedy ties random).
- **Collision-based logic gates are unreachable with fractal rules:** 0 of 2,500
  rules had a convergent glider pair — fractal posterisation breaks rotational
  symmetry → unidirectional gliders → no collisions.

## Genuinely novel (not found in surveyed literature; absence-of-evidence)

1. **Escape-time-fractal → CA-rule generation** (mandelhunt: posterise a Mandelbrot/
   Julia/Newton escape image into a K=4 hex LUT). Existing fractal-CA work is the
   reverse (CAs *generate* substitution fractals).
2. **Dimension-invariant class-4 yield** of fractal-derived rules (N=2→5).
3. **Routable-input CAs (cell8/10/11):** rule table indexed by neighbourhood + k extra
   routable ports, inert-by-default, usable as a conditional/programmable interface.

Caveat: the targeted novelty search did not exhaustively cover Wuensche's full DDLab
corpus, hex-CA art, or demoscene sources; treat novelty as "not found," not "proven."

## Reproducibility (artifacts)

`caca.py` (vectorised hex CA reservoir + readouts), `caga.py`/`caga2.py`/`caga3.py`
(GA / island GA / Julia+Newton+symmetry GA), `cell10*.py` / `cell11*.py` (extra-port
CAs + programmable demo), `fractals.py` / `genpool.py` (fractal rule generators),
`ndca.py` (N-dim survey), `symmetry.py`, `mix.py` (n-gram mixture), `ca_mp.py`
(matching pursuit), `glider_screen.py` / `collide.py` / `collide2.py` (glider +
collision search). ALICE bundles in `alice/` (`c4lib-*` rule library, `ndca-survey-v1`,
`ga-sweep-v1/v2`) run via the retry-tolerant push/sbatch/pull pipeline.

## What to claim, and to whom

The defensible, publishable-flavoured contributions are (1) the **fractal escape-time
→ class-4 rule generator** and its **dimension-invariance**, and (2) the rigorous
**structured ≫ random** reservoir result *with* the honest correction that class-4 is
not uniquely best. Frame against ReCA (Yilmaz/Nichele) and Wuensche/DDLab; cite the
edge-of-chaos skeptics (Carroll, Mitchell). The byte-prediction angle is not
competitive with n-grams and should be presented as characterisation, not a SOTA claim.
