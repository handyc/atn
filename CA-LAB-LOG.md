# CA-network lab log

A running notebook for the "network of class-4 CAs" investigation: what we tried,
what worked, what didn't, and where we're pushing next. Newest entries at the top
of the timeline. Companion to `CA-NETWORK.md` (results writeup) and the memory note
`atn-ca-reservoir.md`.

---

## ★ The headline: class-4 is the right direction — and here's WHY

This is the load-bearing finding, so it goes first and stays first.

**A network of cellular automata only works as a predictor if the CAs are class-4
("edge of chaos").** When we swap the evolved class-4 rules for random rules of the
exact same architecture, the reservoir collapses from 0.302 accuracy to ~0.11 —
*below the unigram floor* (worse than guessing). The structure, not the wiring, is
what carries the signal.

**Why class-4 specifically (the mechanism):**
- **Class 1/2 (dies / freezes):** dynamics settle to a fixed point or short cycle.
  The board stops responding to input → features are constant → nothing to read out.
- **Class 3 (chaotic):** sensitive dependence on initial conditions. Any input
  perturbation is amplified and smeared across the board within a few ticks → the
  recent-input information is destroyed → features are effectively noise. (This is
  what random rules do, and why they score below unigram.)
- **Class 4 (edge of chaos):** persistent, localized, moving structures (gliders)
  with long transients. Input perturbations are neither killed nor scrambled — they
  are *preserved and transported* through the board in a recoverable form. A linear
  readout can then decode them. This is exactly the "edge of chaos" hypothesis from
  reservoir-computing theory (Langton; Bertschinger & Natschläger): computation —
  the simultaneous storage AND combination of information — lives at the phase
  transition between order and chaos. Class 4 *is* that transition.

So the user's original instinct was correct on substance: the *right* CAs, in the
*right* arrangement, do bridge the system toward something with real predictive
structure. The "right" is doing a lot of work — and "right" means **class-4**.

Corollary for the project: the mandelhunt Mandelbrot-walk isn't just a novelty-rule
generator; it is a **reservoir-rule generator**. Fractal self-similarity → class-4 →
good reservoirs. That pipeline is now dual-use.

---

## Timeline

### 2026-06-15/16 — federated rule-discovery swarm ("BitTorrent for rulesets", rulehub.py)
- Built `rulehub.py`: a federated class-4 rule-DISCOVERY swarm. Each node owns a SHARD
  of fractal-space (distinct seed), discovers class-4 hex rules, publishes each as a
  CONTENT-ADDRESSED piece (sha256(LUT)=piece id -> automatic dedup across peers) with
  rich metadata (c4, 3D-class, glider, C6/D6 symmetry, family, fractal coords). Modes:
  node / index (tracker: merge+dedup) / query (pull-by-criteria). Calibration: this is
  the RIGHT reading of the BitTorrent idea — distribute the EXPENSIVE-to-find rules
  (class-4 rare; cheap to use), NOT per-tick lookups (fatal latency). Infrastructure
  win (build huge diverse libraries collaboratively), not a capability/prediction win.
- ALICE `swarm-v1` (160 peer-nodes, job 3695071): **16,180 UNIQUE class-4 pieces**
  discovered + content-address-deduped across the swarm. By family: newton 5142,
  julia 4726, burning 3539, mandelbrot 2773. 13% gliders, **89% survive as 3D
  class-4** (confirms dimension-transfer at scale), ~47-48% C6/D6-stable. Pull-by-query
  works: "3D-class4 gliders" -> 1980 hits; "julia c4>=0.8" -> 836; "D6-symmetric" ->
  7731. Some pieces satisfy ALL properties (2D+3D class-4 + symmetric + glider) and are
  instantly queryable. = a working federated discovery swarm: content-addressing
  (sha256=piece id) for dedup, shard-partitioned peers, index=tracker, query=pull.
  (Library blobs ~260MB live in outputs/, gitignored; tool + bundle committed.)

### 2026-06-16 — fractal location CONTROLS glider direction (novel, causal)
- **`glider_dir.py`:** glider velocity vs fractal location (1119 Newton gliders). Global
  angle alignment R=0.54 (multi-modal — several directions), but WITHIN a fractal region
  R=0.87 -> each region emits gliders heading a specific way. Speed vs log(span/zoom)
  r=-0.18 (shallower zoom -> faster gliders).
- **`dir_control.py` (causal):** picked two regions (predicted headings 74.5 vs -121.9 deg),
  generated fresh rules in each -> gliders went 69.0 deg (R=0.92) and -115.7 deg (R=0.89).
  Generated headings match predictions AND differ -> fractal location CAUSALLY controls
  glider direction. Fractal-space = a steering wheel for glider dynamics (presence +
  direction + roughly speed). Strongest fractal->behaviour result; extends mandelhunt's
  founding hypothesis into a quantitative, controllable map.

### 2026-06-16 — saturation + fractal-geometry->behaviour (mining the 164k library)
- **Saturation (`saturation.py`):** 89% of the 164k rules are BEHAVIOURAL duplicates;
  marginal discovery decayed ~30x (1000->34 new behaviours/1k). Discrete dynamical-class
  space saturates within a few thousand rules; residual novelty is just finer c4/act
  bins. -> bigger swarm = finer measurement, NOT new dynamics (confirms the 100,000x
  refusal empirically).
- **Geometry->behaviour (`geomap.py`):** tests mandelhunt's founding hypothesis at 164k
  scale. GLIDERS are regionally concentrated in fractal-space (Newton: top-10% of regions
  hold 83% of gliders; zoom corr -0.32) — but class-4-ness / 3D-survival / symmetry / c4
  are LOCATION-INDEPENDENT (~uniform). So fractal structure predicts glider-capability
  specifically, not class-4-ness in general.
- **Causal test (`target_gen.py`):** targeting the glider-rich Newton region (cx~0,cy~0,
  span~0.4-0.65) -> 18.0% glider yield vs 9.8% blind walk = 1.8x. Fractal location is
  CAUSAL for gliders; a targeted generator out-yields the blind walk. (Tighter targeting
  would beat 1.8x.) Novel + actionable: a smarter glider generator.

### 2026-06-16 — swarm-v2: 10x scale-up -> 164k-piece distributed library
- ALICE `swarm-v2` (800 peer-nodes x 600 candidates, job 3695457): **164,034 unique
  class-4 pieces** (~10.1x swarm-v1). newton 52327 / julia 46913 / burning 36304 /
  mandelbrot 28490. 13% gliders, 89% 3D-survival, ~48% C6/D6-stable — proportions
  IDENTICAL to v1 -> discovery yield is stable/uniform, swarm scales linearly.
  Queries: 3D-glider -> 20363; premium (3D+glider+D6-sym) -> 11055. Ran in ~3-5 min
  wall (high cpu-short concurrency). Pulled MANIFESTS ONLY (index light); ~2.6GB of
  pieces stay distributed on ALICE -> the federated model done right at scale.

### 2026-06-15 — cell-11 programmable frontier: gliders + a port-controlled signal GATE
- **`cell11_prog.py`:** cell-11 as a programmable CA — port command = instruction
  (RUN/INC/SHIFT/CLEAR), programs execute exactly (8/8), base dynamics resume when
  ports off. But these ops are local slice-writes (representationally easy).
- **`glider_screen.py` / `cell11_glider.py`:** our fractal class-4 rules have GLIDERS
  in abundance — 1136/8000 quiescent-bg rules transport a localized signal (disp 30-39
  cells/40 ticks). FIXED gate test (sink barrier = port writes 0s, not a nonzero source;
  the first test was broken — nonzero wall acted as a source): found ~4 PROGRAMMABLE
  GATES (rule#1579/47830/8615 etc.) where a glider crosses the board when open and is
  fully ABSORBED when a port writes a sink barrier. = non-local, dynamics-driven 1-bit
  gate under program control. The step from programmable transforms to COMPUTATION.
- **Honest scope:** it's a controllable signal channel / 1-bit gate (collision-computing
  PRIMITIVE), NOT yet a logic gate (AND/XOR need glider-glider collisions w/ conditional
  outputs — Adamatzky territory).
- **Collision-logic FRONTIER — structural null (collide.py/collide2.py):** 0 of 2500
  quiescent fractal class-4 rules had a CONVERGENT glider pair — glider direction is fixed
  by the RULE (seed-independent), so the rules are anisotropic/UNIDIRECTIONAL and two
  same-velocity gliders can never collide. Mandelbrot/Julia posterisation breaks rotational
  symmetry -> no collisions -> no collision-based logic gates with this rule family.
  Did NOT fire an ALICE job: the limitation is structural, not search-size, so scaling
  would only confirm the null. The path to logic gates is ISOTROPIC rules (Wuensche
  iso-rules / Spiral rule), a different generator — not the fractal walk. See [[atn-ca-literature]].

### 2026-06-15 — decoder lever + cell-11 + novelty correction
- **n-gram + reservoir MIXTURE (lever 1, `mix.py`):** arithmetic mix beats the n-gram
  alone, 3.807 -> 3.771 bpb, tuned weight a=0.88 (interior) -> reservoir adds a LITTLE
  complementary info. FIRST thing to beat the n-gram; small & single-run, needs replication.
  (Watch readout LR: at lr=0.5 on wide standardized input the logistic DIVERGED to 7.2 bpb;
  lr=0.1 fixed it.)
- **cell-11 (`cell11.py`, base 7->1 + 4 inert-by-default trainable ports, LUT 4^11):**
  (a) conditional-MUX verified — ports-off=base, each port-command executes a distinct
  action exactly (ports = extra address lines -> independent behaviour slices). But this is
  representationally trivial (slices independent by construction). (b) reservoir A/B null:
  4 additive ports HURT (0.177 vs base 0.232) — same as cell10. cell-11's only promise is
  conditional COMPUTATION (Q/K/V lineage), not prediction.
- **NOVELTY CORRECTION:** hex K=4 CA substrate = PRIOR ART (Wuensche/DDLab arXiv:2008.11279,
  v4k4 hex + input-entropy class-4 classification). Only fractal-gen + routable-input ports
  remain plausibly novel (2nd search cut off by session limit). NO more deep-research
  workflows (token cost). See [[atn-ca-literature]].

### 2026-06-15 — ALICE confirmation suite: structured>>random YES, class-4-specifically NO
- **ga-sweep-v2 (ALICE, 8 seeds x 3 corpora, class4 vs LINEAR-class3 vs random):** class4
  TIES linear-class3 (news d+0.2, code d+0.6, langs d0.0); BOTH crush random. -> the
  confirmed claim is "structured >> random," NOT "class-4 is uniquely special." Matches
  the literature (Yilmaz: class-3 rules work; edge-of-chaos not uniquely best). The
  class-4-vs-random gap (ga-sweep-v1) is real & large (d=2.2-3.9); the class-4-vs-linear
  gap is ~0.
- **Matching pursuit (data-conditioned rule selection, the user's idea):** train-residual
  greedy OVERFITS and loses to random (-0.052 test); held-out-residual greedy fixes the
  overfit (val climbs, beats random on val) but TIES random on fresh test (0.249=0.249).
  -> selecting among class-4 rules by data-fit doesn't beat a random draw on fresh data;
  random structured reservoirs are a strong baseline (readout is the ceiling).
- **N-dim STRUCTURED class-4 survey (ALICE, 9600 fractal rules):** %class-4 is FLAT ~1/3
  across N=2..5 (32.5/33.6/31.1/31.5%) while RANDOM is ~0% at N>=2. The Mandelbrot/Julia
  walk finds class-4 at a stable ~1/3 rate independent of dimension (Julia/Newton ~40%,
  Mandelbrot ~20%). Dimension-robust generator — clean, likely-novel.
- **Literature (deep-research):** ReCA (Yilmaz/Nichele), GA-over-CA (Mitchell), coupled-CA
  reservoirs (Nichele&Gundersen) are PRIOR ART; "class-4 best" is CONTESTED (now confirmed
  contested by our own v2); NOVEL = fractal->rule generation, dim-transfer, hex/ports. See
  LITERATURE.md / [[atn-ca-literature]].

### 2026-06-15 — GENERALITY: class-4 essential on CODE and LANGUAGES too (+ caga3 result)
- **caga3 (Julia+Newton pool + per-node symmetry gene, news):** best both_acc 0.281,
  just BELOW the mandelhunt ceiling 0.3037; GA kept symmetry mostly OFF. Generator
  upgrades don't move the readout-capped prediction number. (As expected.)
- **CODE (demo-code) class-4-vs-random, fresh region:** class-4 reservoir res_acc
  0.253 vs RANDOM 0.061 (×4; random far below unigram). class-4 essential CONFIRMED.
  Note: on code, deep literal ctx is strong (ctx-16 acc 0.308) — code has long-range
  repetition — but class-4+ctx (0.322) still edges it; the class-4≫random gap is huge.
- **LANGUAGES (demo-langs) class-4-vs-random, fresh region:** class-4 res_acc 0.145
  vs RANDOM 0.079–0.096 (~×2; random hurts, negative lift). class-4 essential CONFIRMED
  (tiny corpus → noisier, but the gap is clear).
- **Conclusion:** the "class-4 is doing the work, random rules collapse" result is now
  replicated across THREE corpora (news, code, languages). The user's central hunch is
  robust and general. (The prediction *ceiling* is still the linear readout everywhere.)

### 2026-06-15 — forced-on rich routing (cell10ga2): LOSES to ports-off, even forced
- **`cell10ga2.py` + `cell10net2.py`:** ports FORCED on (no off, port_w in {1,2,3}),
  rich source menu (node/self/input/pbyte/pboard/clock/func) per the user's "connect
  the extra inputs to the right things" hypothesis. Honest fitness (held-out both_acc).
- **Result:** best 0.2743, LOSES to the ports-off 7->1 ceiling 0.3037. The winner used
  current-state sources (self/node/input), NOT the temporal ones; forcing ports on
  could not turn them into a net gain. CAVEAT: this is the ADDITIVE injection mechanism
  (perturbs the class-4 base toward chaos) -> rules out "additive ports help," not
  "genuine 4^10-LUT ports help" (untested; readout ceiling likely still caps it).

### 2026-06-15 — symmetry / wallpaper as a rule prior: ~6-10x smaller space, but lower yield
- **`symmetry.py`:** enforce hex C6 (rotations) / D6 (rotations+reflections) on the rule.
  Space shrinks 16384 -> C6 2800 (5.9x) / D6 1720 (9.5x). But class-4 yield DROPS (Julia
  43% -> C6 26% / D6 28%) because enforced isotropy over-stabilises (more dies/freezes);
  the symmetric class-4 rules that survive are activity-centred (~0.32, ideal). Verdict:
  symmetry is a real search-space reducer but a TRADE-OFF, not free -> use as a SOFT,
  GA-selectable per-node prior over the 9 hex-compatible wallpaper groups, not a hard
  global constraint. (17 wallpaper groups is a real theorem; "17 = node-connection ways"
  is not, and only 9 are hex-compatible.)

### 2026-06-15 — fractal source comparison: Julia ~2x Mandelbrot's class-4 yield; Newton most diverse
- **Built `fractals.py`:** generate 7->1 LUTs (4^7) by posterising several escape-time
  fractals, classify each as 2D-hex, report class-4 YIELD + activity + diversity.
- **Result (100 samples/family):** Julia **45%** class-4 | Newton 35% (diversity 0.625,
  highest) | Burning Ship 30% | Mandelbrot 25% | Multibrot z^3 17% (mean_act 0.625 ->
  chaotic). Julia's mean activity 0.434 is closest to the 0.32 sweet spot.
- **Conclusion:** the user's Julia hunch is confirmed by data. Mandelbrot is NOT the
  best generator. Recommended pipeline upgrade: draw the rule pool from **Julia (yield)
  + Newton (diversity)** instead of Mandelbrot alone. Calibration: this improves the
  GENERATOR (more/better/varied class-4 rules), not the prediction ceiling (still the
  linear readout) — better raw material, same decoder limit.

### 2026-06-15 — N-dimensional class-4 survey: class-4 exists at every N but is a vanishing sliver
- **Built `ndca.py`:** N-dim von Neumann "neighbour+self" CA (m=2N+1, LUT 4^(2N+1)),
  vectorised. 2D-hex and 3D-cubic both have m=7 -> the SAME 4^7 LUTs are valid 3D rules.
- **hex3d:** ran the mandelhunt 2D-hex class-4 LUTs as 3D von Neumann: **76% stay
  class-4** (c3=18%, died/froze=6%), mean activity 0.39. -> a 3D analog exists AND
  your existing rules largely transfer to it unchanged.
- **survey (RANDOM rules, %class-4 by N):** N=1: 8.3% | N=2: 0.0% | N=3: 0.0% |
  N=4: 0.0% | N=5: 0.0% (random rules peg at mean_act ~0.75 = class-3 chaos). So
  among random rules class-4 is essentially ABSENT at N>=2 and gets rarer with N.
- **Conclusion:** class-4 is findable at *every* dimension (proven by the 3D
  transfer), but it is a measure-~zero sliver that random search never hits at N>=2.
  The Mandelbrot walk is therefore LOAD-BEARING, not decorative: fractal
  self-similarity is what locates the sliver. Going higher-N: LUT explodes as
  4^(2N+1) AND the sliver shrinks, so you need ever-better structured search; the
  rules transfer across N, so reusing the 2D pool in 3D is the cheap win.

### 2026-06-15 — cell10 routing GA: evolution turned the ports OFF (port_w->0 by gen 2)
- **`cell10ga.py`** evolved per-node 3-port wiring with port_w=0 (off) ALLOWED as a
  control. It drove port_w->0 by gen 2 and settled at a 2-node pure-7->1 net,
  both_acc 0.3037 (== the 7->1 ceiling). Given the choice, the search discarded the
  cell10 ports for byte prediction -> the random-routing +0.007 bump was not robust.
  Next (user's ask): FORCE ports on + a far richer source menu (esp. temporal:
  previous bytes/board states) to find whether there's a wiring that earns its keep.

### 2026-06-15 — cell10 (3 routable extra-input ports): small consistent positive, readout still caps
- **Built:** `cell10.py` — the user's 2D-hex CA with 3 routable ports (4^10 LUT,
  cell8-consistent layout `in3|in2|in1|self|nw|ne|r|se|sw|l`), verified exact
  reduction to 7->1 with ports off; Mandelbrot-walk generator extended to 1024x1024
  (works but SLOW ~render + LOW class-4 yield under self-routed probe -> pivoted to
  embedding the proven 7->1 pool). `cell10net.py` — a graph reservoir where each
  node's 3 ports route to {another node's board, self, the input signal, off};
  cell10 rule family = `out = rule7[hexkey] + w*(p1+p2+p3) mod 4` (fast, faithful
  to "7->1 rule + 3 inputs"; a restricted subset of full 4^10 LUTs).
- **First A/B (same rules/structure, ports off vs routed, ridge acc):** in-sample
  both_acc 0.254 -> 0.264; FRESH 0.255 -> 0.262. Cell-level port routing gives a
  small (~+0.007-0.010) but consistent, GENERALISING bump.
- **Read:** the mechanism does something real, but modestly — consistent with the
  readout being the ceiling. Untested: EVOLVING the routing (a GA over port routes,
  the user's "graph network" vision) and a richer port rule (full 4^10 LUT vs
  additive). Those are the next levers if we push cell10 further.

### 2026-06-15 — SCALE-UP (islands/depth/meta/diversity): the search chose SMALL — ceiling is the readout
- **Tried (`caga2.py`):** the full "go bigger" program — up to 10 nodes / 40x40
  boards, fan-in 4, DEPTH-3 hierarchical reservoirs (`caca.DeepHexNet`, the
  meta-node/meta-network), 384-rule diverse pool, 4 ISLANDS with ring migration,
  self-adaptive mutation. 18 gens on news.
- **Result:** winner converged to **3 nodes, 16x16, depth 1** (same neighbourhood
  as the simple GA). Fresh region: reservoir 0.308 acc / 3.746 bpb vs the simple
  GA's 0.302 / 3.777 — **identical within noise** (+0.006 acc / -0.03 bpb). Bigger
  nets were CULLED, not selected; depth>1 never led.
- **Conclusion (the honest one):** scale / depth / islands / meta-layers improve the
  SEARCH, not the CEILING. The sweet spot is SMALL and we are already on it. The cap
  is the **linear readout** (a context-encoder class that tops out below a real
  n-gram at 3.51 bpb), NOT the number of CAs. This is the project's recurring lesson
  confirmed with data in this domain: stacking scale/meta buys organization, not
  capability. Marginal helpers: more readout cells (rcells 128) + a bit more
  connectivity; non-helpers: nodes, board size, depth, islands, meta.
- **Implication for next push:** to raise the ceiling, change the READOUT/decoder
  (e.g. feed class-4 features into atn's n-gram mixture), not the reservoir size.

### 2026-06-15 — honest n-gram baseline: reservoir beats linear control, n-gram beats reservoir
- **Tried:** `ngram_baseline.py` — atn's real n-gram on the same fresh test bytes
  (train 85% / test 15%).
- **Result:** linear ctx-4 4.552 bpb · evolved CA reservoir **3.777** · atn n-gram
  (2,4,7) 3.569 · atn n-gram (2,4) **3.506**. The reservoir sits BETWEEN the linear
  control and the n-gram. **Honest claim:** the reservoir is a strong nonlinear
  context *encoder* that crushes a linear context model, but does not (yet) beat a
  proper n-gram. Beating the n-gram is a future lever, not a current result.

### 2026-06-15 — GA over CA networks: the negative flipped to a controlled positive
- **Tried:** evolve a directed-graph network of class-4 *hex* CAs (the real
  mandelhunt 7→1 K=4 rule) as a reservoir; GA gene = {nodes, side, ticks, decay,
  couple, reps, rcells, lut_ids, parents}; fitness = held-out accuracy lift of
  (context+reservoir) over a linear context control, scored on a VAL split (TEST
  kept clean). Corpus: demo-news (`demo-run/eval.txt`). 30 generations.
- **Worked:** val both_acc 0.210 → 0.301 over generations; converged to a SMALL net
  (3 nodes, 16×16, ticks 4, decay 0.2). On a FRESH region the GA never saw:
  reservoir 0.302 acc / 3.777 bpb vs linear ctx-4 0.201 / 4.552 (unigram 0.168).
  Generalises out-of-sample → not scorekeeper overfitting.
- **Controls (the important part):**
  - Deeper plain context gets WORSE (ctx-4/8/16 → 0.201/0.184/0.149 acc): the win is
    NOT "just longer memory."
  - Random-rule ablation (same architecture, uniform-random K=4 LUTs): 0.105–0.110
    acc, below unigram, stable over 2 seeds → **class-4 is essential.**
- **Didn't (yet):** compare against atn's REAL n-gram (script `ngram_baseline.py`
  ready; blocked by a transient infra outage at session end). Until then, "beats a
  *linear* context model" is the honest claim, not "beats n-grams."
- **Files:** `caca.py`, `caga.py`, `eval_finalist.py`, `controls.py`,
  `ngram_baseline.py`, `CA-NETWORK.md`, run dir `caga-news/`.

### 2026-06-15 — single hand-built hex network: still negative
- **Tried:** one arbitrary network of class-4 hex CAs (correct CA this time) on news.
- **Didn't work:** reservoir below unigram, hurt the combined model. Lesson: the CA
  class is necessary but not sufficient — the *arrangement* matters, which is what
  motivated the GA. (One arbitrary draw ≠ a good reservoir.)

### 2026-06-15 — corrected the substrate: 1-D elementary → 7→1 hex K=4
- **Tried/fixed:** the first reservoir attempt (`reca.py`) used 1-D *elementary*
  rules (110, 54, …) — the wrong CA. Rebuilt on the real mandelhunt hex CA,
  numpy-vectorised, verified bit-exact vs `mandelhunt.c` `hex_step` (caught a uint8
  overflow bug in the test reference along the way; the implementation was right).

### 2026-06-15 — first attempt: ReCA with elementary CAs — NEGATIVE
- **Tried:** `reca.py`, a network of 1-D elementary class-4-ish rules as a reservoir
  for next-byte prediction, logistic readout, matched linear control.
- **Didn't work:** reservoir below unigram floor; hurt the combined model. Honest at
  the time, BUT used the wrong CA and only hand-built nets. Superseded by the hex+GA
  result above. Kept as a documented negative.

---

## Revised direction (post scale-up, 2026-06-15)
The size question is answered: **don't scale the network — change the readout.** The
class-4 reservoir is a good feature extractor; the linear readout is the ceiling.
Highest-value next experiment: feed the reservoir features into atn's existing
n-gram MIXTURE (a stronger decoder) instead of a bare linear/logistic layer, and see
if the combination beats the n-gram alone. Stop growing nodes/depth/islands.

## What we're pushing next (planned)
1. **(a) Finish the honest baseline + commit.** Run `ngram_baseline.py` (atn's real
   n-gram on the same fresh test bytes) so we know where 3.78 bpb stands vs n-grams;
   commit the whole CA-network toolkit.
2. **(b) Generality of the class-4 win.** Re-run the class-4-vs-random ablation on
   CODE and LANGUAGES corpora (`demo-code/`, `demo-langs/`). Prediction: class-4
   beats random everywhere; if it ever doesn't, that's a key boundary condition.
3. **(b) Does the lift scale?** Sweep reservoir size (nodes, board side, rcells,
   spacetime readout) — does the advantage grow with capacity or plateau? Plateau →
   it's a fixed-capacity feature trick; growth → genuine headroom.
4. **Later levers:** compare against a generic echo-state/GRU reservoir (is class-4
   *better* than any reservoir, or just *a* reservoir?); feed reservoir features into
   atn's existing mixture (hybrid); evolve the Mandelbrot-walk coords jointly with
   the network (search rule-space and arrangement together).

## Open questions / honesty watch
- Is class-4 better than a *generic* good reservoir, or merely better than random?
  (The random ablation only rules out "any rules work"; it doesn't yet show class-4
  beats, e.g., a tuned echo-state network.)
- The reservoir is a context *encoder*; does it ever beat atn's n-gram, or only the
  linear control? (Pending baseline.)
- Does the small-network preference (3 nodes, 16×16) hold across corpora, or is it
  news-specific?

## Boundary-region / collision-logic thread — closed (2026-06-16)
Hypothesis: rules near a direction-DOMAIN boundary (dir_control showed fractal
location sets glider direction) might be bistable and emit gliders in TWO
directions from one rule -> two opposing gliders on one lattice -> a COLLISION
becomes possible (re-opening collision-based logic for our anisotropic fractal
rules). Tested in `boundary.py` (within-rule direction spread, 385 Newton glider
rules) + `collide_one.py` (head-on collision of the one flagged rule).

Result — NEGATIVE, cleanly:
- Within-rule angle alignment R = **0.99** mean; **0%** of rules genuinely
  multi-directional (R<0.6). Single fractal rules are essentially UNIDIRECTIONAL.
- The lone flagged exception (0d9ff49, R=0.49, maxgap 179deg, 7 gliders) *does*
  have a seed pair 180deg apart (seed 1034 @ -39deg, seed 1067 @ 141deg) — but
  those gliders are SLOW (speed ~0.21-0.26, just above the 0.15 floor) and DECAY
  to ~1 cell; in a head-on setup their mass tracks superposition exactly
  (ratio 1.00) — they pass through WITHOUT interacting. The flag was small-sample
  noise on near-threshold structures.

Verdict: collision-based logic remains BLOCKED for fractal-walk K=4 hex rules —
they are anisotropic/unidirectional, exactly as Wuensche's X-rule (gliders only
E-W) and the collision-logic literature (Adamatzky/Martinez) imply. The route to
collisions is ISOTROPIC rules (Wuensche iso-rules, Spiral rule), not boundary
rules. The genuinely novel, defensible result stays: the continuous
fractal-coordinate -> glider-DIRECTION control map (dir_control.py, causal).

Lit review (WebSearch, 2026-06-15/16): closest prior art —
- Martinez & Adamatzky, "Logical Gates via Gliders Collisions" (arXiv:1803.05496)
  — collision logic, but in isotropic rules.
- Wuensche, anisotropic X-rule (gliders only E-W) — matches our unidirectionality.
- Lenia velocity optimisation (arXiv:2508.04167) — continuous-CA glider steering,
  but learned, not a closed-form fractal-coordinate dial.
No prior work found mapping a continuous fractal coordinate to glider direction;
that map appears novel. Collision logic itself is well-trodden and isotropy-bound.

## fractal -> glider-DIRECTION, deepened (2026-06-16)
Pushed the one genuinely-novel result (fractal coordinate controls glider
direction) from "two regions differ" to a characterized, invertible control law.
Scripts: `fractal_dir_deep.py` (continuity + mechanism), `fractal_steer.py`
(inverse control). Newton glider region cx~0.007 cy~-0.028 span~0.53.

1. CONTINUITY (confirmed, strong). Sweeping cx with cy/span fixed gives a smooth,
   near-monotone glider-angle progression (64 -> 100 -> 173 -> -116 -> -56 deg as
   cx: -0.27 -> +0.17), **circular-linear corr(cx,angle) = 0.97**, mean
   within-coordinate alignment R = 0.88. So fractal cx is a CONTINUOUS analog dial
   for glider heading, not just a region label. (The script's "swing" line is a
   bad metric — circular max-min understates a wrapped sweep that actually spans
   ~240 deg; the 0.97 corr is the right statistic.)

2. MECHANISM (hypothesis FALSIFIED, cleanly). The posterised fractal image IS the
   LUT (pixel index = neighborhood key; row=key>>7 set by self+north neighbors,
   col=key&127 by south/west), so I hypothesized fractal-field ORIENTATION sets the
   propagation axis -> rotating the sampling grid by phi should rotate the glider.
   It does NOT: R(theta-phi)=0.09, R(theta+phi)=0.14, circ-circ corr(phi,theta)
   =-0.19, while R(theta)=0.46 (weak substrate bias independent of phi). The fixed
   raster->neighborhood bit-map is not rotation-equivariant; rotating the image
   scrambles the LUT. Direction is driven by the COORDINATE-dependent change in the
   LUT's directional bias, not by image rotation. ("fractal orientation = glider
   orientation" is dead.)

3. INVERSE CONTROL (works). Built the cx->angle transfer function (19 control
   points), then for 8 requested headings inverted to a cx, generated fresh rules,
   and measured the realized heading: **mean steering error 22 deg (median 17)**,
   reachable arc ~296 deg, per-point R ~ 1.00. A "fractal-coordinate glider
   compass": request a heading, get it within tens of degrees. The two worst
   targets (+0, +135) fell in sparse GAPS of the reachable arc, not control errors.

Net: the novel, defensible contribution is now a continuous + invertible
fractal-coordinate -> glider-direction control law. No prior work found mapping a
continuous fractal coordinate to a steerable glider heading (closest: Lenia
LEARNED velocity steering, arXiv:2508.04167 — ours is closed-form via the
fractal-walk coordinate). Open: 2D (cx,cy) steering field; the true LUT-intrinsic
direction statistic (since rotation-equivariance is out); speed (span) as a second
orthogonal knob.

## 2D (cx,cy) glider steering FIELD (2026-06-16)
Extended the cx dial to the full fractal plane: `fractal_field2d.py` maps (cx,cy)
-> mean glider heading over an 11x11 grid at fixed span (~0.53), renders it as an
arrow field, and runs 2D inverse control. Output field saved to
`fractal_field2d.json` (cx, cy, heading_deg, R, n) for possible web viz.

Findings (honest):
- SPARSE but CLEAN: only 36/121 cells (30%) host a clean directed glider (gliders
  are spatially concentrated, as geomap found) — but where present, mean
  within-cell alignment R = 0.98. Glider-rich locus is a diagonal band near the
  library-median cy ~ -0.028.
- FULL CIRCLE represented across the plane (~359 deg of headings appear somewhere).
- cx is the DOMINANT dial (circular-linear corr cx=0.58); cy is NOT an independent
  steering axis (corr 0.05). The 2D field's benefit is a richer candidate set (more
  cells -> finer heading match), not a genuine second control knob.
- 2D INVERSE CONTROL improves precision: mean steering error 15 deg (median 8) vs
  22 deg for the 1D cx-only dial; most targets land within single-digit degrees.
- BOUNDARY CONDITION: two headings stay hard even in 2D — 0 deg (->, err 55) and
  -90 deg (up, err 26). Those directions are genuinely scarce in this Newton region:
  a hex-LATTICE anisotropy (favored glider axes) that the fractal coordinate cannot
  override. Consistent with the unidirectionality seen in the collision thread.

Takeaway: the steerable region is real and now precise (median 8 deg), but bounded
by the substrate's preferred axes. Next levers: vary SPAN (does another zoom open
the 0/-90 deg gaps + give an orthogonal SPEED knob?); the LUT-intrinsic direction
statistic (mechanism, since rotation-equivariance is out).

## SPAN sweep — speed knob? gap-filling? (2026-06-16)
`fractal_span.py`. Two questions about zoom (span).

A) Is span an ORTHOGONAL knob (speed), independent of the coordinate dial
   (direction)? PARTIAL. Span is a STRONG speed dial: corr(log span, speed) =
   -0.89 (zoom out -> slower glider, robust across coordinates). BUT direction
   also DRIFTS with span (mean drift 98 deg; one coordinate swung 149 deg). So
   speed and direction are COUPLED, not orthogonal — you can't retune speed
   without moving the heading. We do NOT have clean two-axis (dir,speed) control.

B) Do the scarce headings (0 deg ->, -90 deg up) OPEN at other zooms? NO. Their
   counts stay 0 at every span tested (0.20, 0.53, 1.30). Reachable headings
   cluster on specific oblique hex axes (down-right, west, up-left, up-right) and
   never hit due east/north/south. Confirms the 2D-field gap is a real HEX-LATTICE
   ANISOTROPY (gliders ride lattice bond directions), not a sampling gap.

Net: span = a (coupled) speed dial; the reachable heading set is a discrete-ish
set of preferred lattice axes fixed by the hex substrate. The clean controllable
quantity remains DIRECTION (within the supported arc) via the coordinate.

## MECHANISM FOUND — single-neighbor activation law (2026-06-16)
The "why does fractal coordinate set glider direction" question is ANSWERED, and
the answer is a substrate law, not a fractal one. `mechanism.py`,
`mechanism_general.py`.

First candidate (FAILED): a global flow vector F = sum_p corr(neighbor_p, output)
* dir_p only weakly predicts heading (circ-circ corr ~0.4, median err 70deg). The
static first-order correlation is not the mechanism.

Winner: the SINGLE-NEIGHBOR ACTIVATION probe. For each of the 6 hex directions p,
read the LUT output for the neighborhood where ONLY neighbor p is active (center +
all other neighbors dead) — i.e. lut[v<<shift_p] for v in {1,2,3}: "does an
isolated upstream cell in direction p fire the center?". Let
   F = sum_p  mean_v[ lut[v<<shift_p] > 0 ]  *  unit_dir(p)
Then **glider heading = angle(F) + 180deg** (one global, parameter-free sign flip;
motion is ANTI-parallel to the activation vector, because if cells on side p fire
the center, the pattern grows toward -p).

Result (Newton, 546 rules): circ-circ corr **+0.95**, residual alignment R **0.96**,
**median heading error 4deg**, 98% <45deg, 100% <90deg. Computed from just **18 LUT
entries**, NO simulation.

Generality (mechanism_general.py): holds for ALL families — newton corr 0.95/med
5deg, julia 0.86/18deg, mandelbrot 0.98/7deg, burning 0.92/6deg. So it is a
property of the HEX SUBSTRATE (LUT geometry), independent of LUT origin.

This CLOSES the arc with an explanation: the fractal coordinate steers the glider
because moving (cx,cy,span) changes the posterised escape-time values at exactly
those 18 single-neighbor configurations, tilting F and rotating the glider. The
0deg/-90deg heading gaps (span sweep) are now explained too: the 6 hex dir_vec(p)
only span certain axes, so achievable angle(F) (hence headings) is constrained to
the lattice's bond directions. Full chain: fractal coordinate -> 18 LUT activation
entries -> activation vector F -> glider heading (angle(F)+180, ~4deg), bounded by
hex bond axes. Novel and closed-form.

## DIRECT-DESIGN INVERSION — the law is GENERATIVE ("glider surgery") (2026-06-16)
`design.py`. Took 18 working Newton glider rules and, for each of 12 target
headings, EDITED ONLY the 18 single-neighbor LUT entries to aim F at the target
(a_p ~ max(0,cos(ang_p - phi))), leaving the rest of the rule intact. Result:
- glider survival after surgery: **100%** (editing 18 entries never killed it).
- mean steering error to requested heading: **4 deg**; the edited rule's own
  angle(F)+180 prediction matches the realized heading at residual R = 0.99.
- CONTINUOUS 360 deg: off-axis targets (30,150,210,330) hit within 1-10 deg while
  sitting 23-31 deg from the nearest hex axis -> gliders go where DESIGNED, they do
  NOT snap to lattice axes. err->target (4) < err->nearest-hex-axis (15).

CORRECTION to the span-sweep claim: the 0deg/-90deg "gaps" are NOT a hard hex-
lattice anisotropy — they are a SAMPLING BIAS of the fractal generator (escape-time
geometry rarely yields F pointing there). By direct design those headings are
reached at ~6 deg (0->-6, 90->+95.6, 270->-95.2). The substrate forbids no
direction; only the fractal walk under-samples some.

=> The single-neighbor activation law is GENERATIVE, not merely predictive: steer a
glider to any heading by editing 18 LUT entries, no fractal search. ("Glider
surgery" — also a candidate app/tool name per the user.)

## SPEED sub-law — weak / emergent (2026-06-16)
`speed_law.py`. Tested whether a LUT-intrinsic statistic predicts glider SPEED the
way the 18-entry activation vector predicts DIRECTION. It does NOT, cleanly: over
551 Newton glider rules (speed 0.56+-0.24 cells/tick), corr(|F|, speed)=+0.39,
corr(aniso,speed)=+0.38, births ~0, lambda -0.11; best single-feature linear
R^2=0.15, 2-feature (|F|,births) R^2=0.21. So there's a sensible weak trend (more
activation anisotropy -> faster) but speed is governed by more of the bulk dynamics
than these single-neighbor features capture. Asymmetry of the result: DIRECTION has
a near-exact closed-form law (~4 deg); SPEED does not. Speed remains controllable
only coarsely (via span, coupled) — an open problem.
