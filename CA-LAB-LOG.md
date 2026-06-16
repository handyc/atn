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

## FROM-SCRATCH synthesis + article figures (2026-06-16)
`synthesize.py`, `figures.py`.

DE-NOVO SYNTHESIS: built a glider rule from NOTHING but the direction law — a
directed excitable medium (quiescent bg; dead cell born if exactly one TRAILING-side
neighbor active; live cell survives only while trailing-supported). By construction
F points at phi=target-180, so the law predicts heading=target. Result (sparse-birth
template): clean directional movers, per-rule R=1.0; **6/8 headings within ~10 deg**
(median ~8): 0->0, 45->43, 135->145, 180->180, 225->-128, 315->-57. The vertical
pair (90,270) comes out exactly 180deg FLIPPED — a chirality degeneracy of the simple
excitable front along the hex vertical. Denser-birth templates spread (don't localize).
Honest: DIRECTION is controllable from scratch (movers go where designed, very
cleanly), but these are directed excitable FRONTS, not guaranteed-localized gliders,
and the simple template has a vertical 180 degeneracy. Robust localization for every
heading needs a better bulk template — expected, since the class-4 BULK is the part
the literature SEARCHES for; what's new is that its DIRECTION is analytically
prescribable.

FIGURES (figures.py -> fig1..fig5 *.png, matplotlib installed --break-system-packages):
F1 rule-as-image; F2 measured-vs-predicted heading all families (med err N 3, J 16,
M 7, B 9 deg) — points on the y=x law line; F3 2D steering field arrows; F4 surgery
dial (clean 360deg diagonal, 100% survival); F5 speed-vs-|F| null (R^2 0.15). F2 and
F4 visually confirmed publication-quality.

Article `glider-steering.md` updated: added Section 4.1 (from-scratch synthesis),
real figure list (Section 8), reproducibility + abstract. Draft is arXiv-ready
modulo reference formatting + F1 schematic polish.

## Vertical-flip diagnosis — it's the template, not the law (2026-06-16)
`vflip.py`. The de-novo synthesis 180-deg flip at headings 90/270 is NOT in the
direction law:
- (1) LAW via surgery on real glider bulks tracks the vertical band fine: 90->94
  (err 4), 270->-95 (err 5), all of 70-110 & 250-290 within ~5-19 deg. The law
  heading=angle(F)+180 is uniform over the full circle.
- (2) The de-novo flip is a ~+-15 deg BAND (75/90/105 and 255/270/285 all snap to the
  opposite pure-vertical heading); fine elsewhere (60,120,240,300 ok).
- (3) Cause = hex OFFSET-LATTICE geometry: no pure N/S neighbor (only nw/ne, sw/se
  pairs) and offset-row PARITY alternates each diagonal neighbor (b[i-1,j-1] vs
  b[i-1,j]) by row, so the crude excitable front propagates anomalously along the
  vertical. Even asymmetric single-neighbor builds misbehave near vertical -> NOT a
  simple symmetric tie (my first guess was only partly right); it's parity geometry.
Conclusion: the flip is an artifact of a PARITY-NAIVE excitable template, not the
law. Real localized gliders (and surgery) have no vertical issue. Fix = parity-aware
bulk template (future). Article 4.1 updated with the resolved diagnosis.

## Parity-aware synthesis attempt + article finishing (2026-06-16)
`synth_clean.py` — tried to fix the de-novo vertical band; both attempts are honest
NEGATIVES:
- (A) ADVECTION rule (cell copies a fixed neighbor) = exactly np.roll = a TRIVIAL
  RIGID SHIFT, Wolfram class 3, NOT an emergent glider. It moves toward the copied
  source (heading=angle(F), no +180) — a different/trivial regime, out of scope for
  the growth-glider law. So it neither needs nor confirms the law (my "advection
  confirms the law" idea was misconceived).
- (B) PARITY-SYMMETRIC birth (born only if BOTH north or BOTH south neighbors active)
  decays to class 1-2, no glider. The vertical band genuinely resists a one-line
  template. Robust vertical de-novo glider needs a real multi-cell motif (future).
Reaffirmed: the LAW is clean at vertical (surgery, err ~5deg); only simple de-novo
TEMPLATES struggle there. Added a scoping note to the article: the law is about
growth/birth-driven gliders; rigid-copy rules are a separate trivial regime.

ARTICLE FINISHED for posting: references formatted (14 entries, years/arXiv, with a
"verify before submission" note); F1 upgraded to a proper schematic (7-cell hex
neighborhood + bit-layout + rule-as-image, `fig1_schematic.png`). glider-steering.md
is arXiv-ready (nlin.CG) modulo a final DOI/year pass.

## THEORY — the direction law is the linear front drift (2026-06-16)
`theory.py`. Derived the empirical law heading=angle(F)+180 from a linearization of
the update at the quiescent state. At the leading edge (low density invading 0):
   n_{t+1}(x) = a_self*n(x) + sum_p a_p*n(x+d_p),
with a_p the single-neighbor activation and a_self=frac_v[LUT[v<<12]>0]. A feature is
transported by -d_p with weight a_p, so mean drift = -F/(a_self+sum a_p) ->
heading = angle(-F) = angle(F)+180. DERIVED, not fitted.

Numerical confirmation:
- (1) DIRECTION: simulating the LINEAR operator alone (real-valued, no threshold)
  from a point source reproduces the measured glider heading to MEDIAN 3 deg
  (circ-corr 0.94), identical to analytic angle(-F). The linearization IS the
  mechanism. The +180 is explained: density flows FROM the firing neighbor TO center.
- (2) SPEED: the derived DRIFT speed |F|/(a_self+sum a_p) predicts measured glider
  speed at R^2=0.36 (corr 0.60) — 3x the raw-|F| R^2=0.12. The marginal-stability
  pulled-front speed v*=min_lambda (1/lambda)ln[a_self+sum a_p e^{lambda d_p.F/|F|}]
  doesn't predict speed (gliders are localized/pushed, not pulled) but UPPER-BOUNDS
  it for 82% of rules. Speed = transcendental saddle-point functional -> no closed
  form in |F| (the speed null EXPLAINED); partial law via drift speed.
- VERTICAL: linear angle(F) points anywhere (continuous combo of 6 d_p) -> vertical
  reachable (surgery confirms). The de-novo XOR ("exactly one of nw,ne") birth rule is
  NONLINEAR -> breaks superposition -> the vertical-band template artifact; the theory
  applies to the additive growth regime.

Upgrades the result from empirical to DERIVED: direction = exact kernel first moment
(median 3 deg); speed = partially derived (drift R^2 0.36) + linear upper bound (82%).
Article (local-only) gained Section 3.1; abstract + speed section updated.

## Glider routing (heterogeneous CA) — PRELIMINARY, fragile (2026-06-16)
`route.py`. Build rules from one base via surgery (differ only in the 18 direction
entries), tile across space, route a glider. First-pass results are WEAK:
- (A) sharp 90deg domain wall (east|south): glider survived 94 ticks but did NOT
  reach/cross the wall (slow + heading -15 not 0); inconclusive crossing.
- (B) graded steering field heading(col) 0->90: glider DID curve (col 18->42,
  row 30->57 = east+south) but heading-vs-field median err 37deg (loose tracking).
  Proof of life for a steering field, not yet clean.
- (C) cross-domain head-on (east|west): exploded; inconclusive.
Honest read: surgically-retargeted gliders are fragile across spatial rule changes —
they survive but don't cleanly cross sharp walls, and field-following is loose.
GRADED fields (B) look more promising than sharp walls. Needs: a fast/robust base
glider (verify strong glide per region first), gentler heading gradients, bigger
board/longer runs. Routing is plausible but not yet demonstrated. fig_route.png saved.

## ALICE gen-v1 (universality) + collide-v1 (collisions) — results (2026-06-16)
Two big array jobs landed.

UNIVERSALITY of heading=angle(-F) (gen-v1, ~180k gliders across substrates):
- sq-vN  K2 corr 1.00 (1deg, 100% growth); K3 0.90 (5deg); K4 0.55 (21deg); K5 0.60 (27deg)
- sq-Moore K2 0.96 (3deg); K3 0.33 (17deg)
- cube-vN (3D) K2 med-angle 178deg (60% COPY regime!); K3 50deg; K4 46deg (64% growth)
The law is EXACT for low-state 2D CAs on EVERY lattice tested (square vN, Moore, hex),
degrades with K, and in 3D / high-K shifts into the COPY regime (motion TOWARD F,
heading=angle(F), no +180). The growth%<->accuracy coupling confirms the linearization:
the +180 sign is growth-specific. => the direction law is a GENERAL PRINCIPLE of
growth-driven CA gliders, not a hex-K4 quirk. (Random K4 gliders are noisier than
fractal-generated ones, which select cleaner gliders.)

CROSS-DOMAIN COLLISIONS (collide-v1, 644 clean tests): surgery one base into east|west
domains so two gliders meet at the wall. 582 passthrough, **55 ANNIHILATE, 7 PRODUCT**
=> 62/644 (10%) INTERACT; strongest annihilations reach min_ratio 0.00 (mutual
destruction). Single-rule collisions are blocked (anisotropy), but HETEROGENEOUS
(surgery'd) domains RE-OPEN the collision frontier: ~10% of bases give interacting
opposing gliders. Candidate collision-logic primitive (annihilation = presence-gates).
Caveat: these are bounded translating structures (some large), not guaranteed minimal
gliders; need collide-v2 (impact parameter, consistent product, truth table) to claim
a gate. Strongest annihilators near cx~-0.09..-0.18, cy~-0.0..-0.03, span~0.3..0.44.

## ALICE gen-v2 (hex K-sweep) + speed-v1 (speed law) — results (2026-06-16)
gen-v2 (direction law on HEX vs K, ~72k gliders): hex K2 med 2deg/100% growth (corr
0.67 noisy on discrete axes but errors tiny), K3 14deg, K4 24deg, K5 29deg, K8 36deg;
growth% 100->83. Same K-degradation + growth->copy drift as square/cube => the
K-dependence holds on the paper's own hex lattice.

speed-v1 (7307 glider speeds, 4 fractal families): drift speed |F|/(a_self+sum a_p) is
the leading predictor — R^2: newton 0.43, julia 0.67, mandelbrot 0.64, burning 0.62,
ALL **0.53** (vs raw |F| 0.21, v* ~0). Multi-feature (drift,v*,lambda) R^2 0.58 overall
(mandelbrot 0.72). v* UPPER-BOUNDS measured speed for **89%** => gliders are
pushed/localized, slower than the linear pulled front. Speed law: partly DERIVED
(drift, R^2~0.5-0.7) + linear upper bound (v*, 89%), residual nonlinear. Completes the
speed section. ALL FIVE ALICE JOBS (route/gen-v1/collide/gen-v2/speed) now in.

## ALICE collide-v2 (gates) + gen-v3 (dimension crossover) — results (2026-06-16)
collide-v2 (40 interactor bases -> gate truth tables vs impact parameter):
COLLISION LOGIC PRIMITIVES EXIST. Best AND/product gate and_frac **1.00** (cx=-0.122
cy=-0.012 span=0.502); best XOR/annihilation gate xor_frac **0.70** (cx=-0.178
cy=-0.032 span=0.414). 3/40 consistent (>60% one type); most impact-parameter-
sensitive. Heterogeneous (surgery-tiled) CA collisions CAN implement gate primitives;
needs collide-v3 (fine impact/timing scan) for a stable truth table. Re-opens
collision logic that single-rule anisotropy blocks.

gen-v3 (growth->copy crossover vs dimension & K, von Neumann, ~56k gliders):
- vn2 (2D): K2 corr 1.00 (0deg, 100% growth); K3 0.89 (8deg, 99% growth)  -> GROWTH
- vn3 (3D): K2 179deg (0% growth, PURE COPY); K3 135deg/27%; K4 120/38%; K5 106/42%;
  K6 93deg/45% growth  -> COPY at low K, drifting to ~50/50 as K rises
- vn4 (4D): K2 1deg (73% growth); K3 45deg (68% growth)  -> GROWTH again
STRIKING: the regime is DIMENSION-PARITY-like — 2D & 4D are growth-dominated (+180
law holds), 3D is copy-dominated (motion toward F). Non-monotonic in dimension. Within
3D, higher K shifts back toward growth (clean K-crossover). The growth%<->accuracy
coupling is exact. Open: does 5D revert to copy (true even/odd parity)? -> gen-v4.

## ALICE gen-v4 (dimension 2-6D) + collide-v3 (stable gates) — results (2026-06-16)
gen-v4 (growth%/dimension, von Neumann, enlarged high-D boards): vn2 100% growth (0deg);
vn3 0% (180deg, copy); vn4 73% (1deg, GROWTH); vn5 0% (178deg, copy); vn6 1% (179deg,
copy); vn5/vn6 K3 ~2% (copy). VERDICT: NOT even/odd parity — 6D is even yet copy. Real
pattern: growth at 2D and a RE-ENTRANT GROWTH ISLAND at 4D; copy dominates 3D and >=5D.
Non-monotonic, surprising; the +180 sign is dimension-specific (4D anomaly open for theory).

collide-v3 (dense impact x timing x seed scan of 41 interactors): ROBUST GATES EXIST.
2 bases have a stable gate region (>25% of operating points, fidelity 1.0):
- robust XOR/annihilation gate: cx=-0.178 cy=-0.032 span=0.414, **xor_region 0.64**
- robust AND/product gate:      cx=+0.058 cy=-0.100 span=0.333, **and_region 0.69**
7/41 bases have a perfect-fidelity gate point. So surgery-tiled heterogeneous CA domains
implement robust XOR and AND glider-collision gates (collide-v2's coarse readout was
operating-point-sensitive; the fine scan confirms genuine robust regions). Collision
logic re-opened and demonstrated. NINE ALICE jobs this session complete.

## Consolidation: figures, draft tightening, 4D-island theory probe (2026-06-16)
1. FIGURES from ALICE data (`alice_figures.py` -> dissemination/): F6 universality
   (median err vs K per 2D lattice + growth% vs dimension showing the 4D island), F7
   speed law (measured vs drift, 7307 gliders, R^2=0.53), F8 robust collision gates
   (XOR/AND fidelity over impact x timing). NOTE: gates are coord-sensitive at the 4th
   decimal — F8 must use full-precision base coords (rounding 0.0576->0.058 killed the
   AND gate); fixed by reading exact coords from collide-v3 outputs.
2. DRAFT tightened: added contributions 5-6 (universality map, collision gates),
   an Open Questions section (4D island, speed prefactor, gate-family completeness,
   deriving the +180 sign), embedded F6-F8, updated figure index. PDF rebuilt.
3. 4D-ISLAND THEORY (`island_probe.py`): tested the SELECTION hypothesis (growth
   gliders blow up except in growth dims) -> RULED OUT. Per-dim (vN K2): explode%
   rises monotonically 2D 7.6 -> 5D 20.8 (NOT min at 4D); transl% falls 56->11;
   among survivors growth% = 2D 100, 3D 0.4, 4D 78, 5D 0; 3D survivors GAIN mass
   (+0.43) yet move copy-ward. So the regime is intrinsic to the dynamics, not a
   survival filter. The 4D island stays a genuine open puzzle (honest negative).

## Stacked glider environments + linguistics application demo (2026-06-16)
STACKING (`stack.py`): L=3 hex-CA layers, each surgically steered to a different glider
direction, coupled at intersections (cells where >=2 layers active). Three coupling
modes over 6 seeds each:
- none (independent): all alive, ~8947 cells, layers just fill/pass through.
- ignite (intersection turns cells on): all EXPLODE — runaway positive feedback.
- annihilate (intersection destroys, matching our collision result): all ALIVE,
  bounded ~3600 cells, with SUSTAINED ~913 intersection-cells/step. The interesting
  regime: an annihilation-coupled stack self-organises around moving intersections
  (bounded + persistently interacting) rather than exploding or merely overlapping.
Honest: ignite=explode, none=fill, annihilate=bounded-sustained-interaction.

LINGUISTICS DEMO (`dissemination/linguistics-demo.html`, self-contained JS, local):
text steers a single glider char-by-char (each char -> a heading via the direction
law), tracing a trajectory = a deterministic, ORDER-SENSITIVE signature of the string.
Verified (python mirror): identical 100%, anagram listen/silent 85% (<100 -> order
encoded), minimal pair cat/cut 56%, spelling colour/color 89% (graded). Honest pitch
for a linguist: a transparent GPU-free order-sensitive sequence-FEATURE extractor for
DH (clustering/variation/authorship/similarity), a teaching instrument, and reservoir-
computing-on-text with interpretable encoding — NOT a replacement for statistical NLP.

## Wiring the linguistics encoder to a corpus — HONEST verdict (2026-06-16)
Tested whether the glider-trajectory fingerprint is a useful TEXT FEATURE on real
tasks (`verify_corpus.py` + variant test), leave-one-out 1-NN:
- LANGUAGE id (40 texts, 5 langs, chance 20%): glider PATH 12% (BELOW chance!),
  glider DIR-HIST 18%, letter-freq baseline 32%. The single-glider trajectory is a
  SEQUENCE-IDENTITY signature (high within-class variance) -> poor distributional
  classifier.
- SPELLING-VARIANT clustering (36 strings, 6 groups, chance 17%): glider PATH 69%,
  DIR-HIST 75% (well above chance -> it DOES capture string similarity) BUT
  letter-freq 100% and edit-distance 100% (the standard baselines beat it).
VERDICT: the glider encoder UNDERPERFORMS trivial standard methods on every real text
task tried. It is NOT a competitive text-analysis tool. Its honest value is
pedagogical/visualization + the physics, not classification. Built
`dissemination/corpus-explorer.html` accordingly: an interactive 2D map of texts as
glider fingerprints (PCA), with the baseline-comparison table shown alongside so the
result is transparent, + optional STACKED (×3 annihilation-coupled) encoding toggle.
Did NOT oversell it as a classifier. (stack.py annihilation-coupling = the real
bounded-interaction regime, reused as the stacked encoder.)

## NAND artifact (rejected) + stackga-v2 emergent gliders (verified) (2026-06-16)
NANDGA-V1: 70/70 islands "100% NAND" — but REJECTED on verification. Replaying a
winning genome on 8 fresh seeds with a FIXED threshold: detector mass is input-
INDEPENDENT (~31-32 for all of 00/01/10/11; separation ratio 0.97). The "100%" was a
fitness artifact (per-genome calibrated threshold over only 3 seeds overfit). So
universality is NOT demonstrated. We DO have robust AND+XOR (collide-v3, held-out-
verified) but {AND,XOR} isn't complete; a real NAND/NOT in-substrate remains unshown.
Fix for a retry: held-out-seed fitness + fixed threshold (non-gameable).

STACKGA-V2 (deeper stacking): VERIFIED REAL. Best genome motion 1.00, driftR 1.00,
occ 0.002 (~10-cell intersection structure) on train seeds AND on 8 HELD-OUT seeds
(motion 1.00+-0.00, alive 8/8) -> generalizes, not overfit. 66/80 islands found an
emergent intersection-glider (motion>0.4, driftR>0.6, localized, persistent). So
stacking 2-3 glider environments reliably breeds a coherent, localized, TRANSLATING
structure at the layer overlap that no single layer has. Winning ops diverse (setmax
29, birth 16, kill 13, flip/decay 11); L=2 dominant (51/80); vertical coupling mostly
UNUSED (top-20 vc mean 0.06) -> emergence is from same-cell coupling + diverse rules,
not the vertical axis. Verification discipline: caught the NAND fake, confirmed this real.

Glider Lab 3 built (local, dissemination/glider-lab3.html): rule studio (4 families,
import/export rulesets, scrollable 7->1 rule sidebar + cell-11 additional-elements list)
+ word->glider linguistics tab + "why it matters" framing for LLM-curious non-mathematicians.

## Feedback stacks (bottom->top loop) on the verified substrate (2026-06-16)
`feedback.py`: feed the bottom layer's output back as input to the top layer, on the
3 best stackga-v2 emergent-glider genomes, sweeping feedback strength vf=0..0.6, 3 seeds.
Findings (honest):
- STABLE: all stay alive (no explode/dead) up to vf=0.6 — the closed loop does NOT
  destabilise the emergent glider. Feedback is viable on this substrate.
- Feedback GROWS the intersection structure (e.g. mass 10->20) and INDUCES/raises
  PERIODICITY (recurrence): genome#2 periodicity 0.00->0.39 at vf=0.3; genome#1
  0.21->0.28. So closing the loop turns a translating glider into a more recurrent/
  oscillatory (memory-like) structure — as expected (recurrence -> attractor/oscillation).
- genome#3 (L=2 setmax) is ALREADY strongly periodic (0.90) with no feedback — a
  naturally looping emergent structure; feedback leaves it unchanged.
Verdict: bottom->top feedback is a stable, viable mechanism that adds a recurrence/
memory timescale to the emergent intersection-glider. Modest so far (periodicity ~0.2-0.4).
To push it: a v3 GA with a FEEDBACK-AWARE fitness (reward sustained periodicity/memory
under the loop) should find stacks that compute with recurrence.

## Feedback reservoir (stackga-v3) — REJECTED by the memory-capacity test (2026-06-16)
stackga-v3 evolved feedback stacks scoring high on the autocorr "memory" fitness
(memory~30 steps, periodicity~0.9, 19/20 top genomes keep feedback vf~0.38). BUT the
decisive standard test (`reservoir.py`: drive with a random bit-stream, train linear
readouts to recover u_{t-k}) REJECTS it:
- feedback ON (vf=0.47): memory capacity MC = 0.08, 0 delays recovered (>0.1 R^2)
- feedback OFF (vf=0):    MC = 0.09, 0 delays recovered
- per-delay R^2 ~ 0 for all k>=1; ON is NOT better than OFF.
VERDICT: the stacks evolved OSCILLATORS, not reservoirs. High autocorr "memory time"
came from PERIODICITY (a cycle ignores the input) — the fitness was gamed exactly as
feared (recurrence -> attractor/oscillator, not working memory). The closed loop adds
NO recoverable input memory. So: feedback stacks do NOT compute with memory by this
route. Honest negative; verification discipline caught it (autocorr metric gameable;
input-driven MC is the real test). CORRECT FIX for a v4: put MC ITSELF in the fitness
(drive with input + readout each eval) rather than a periodicity proxy.
No reservoir to "show off" -> not building a reservoir demo. (Building instead the
requested word-list trajectory atlas, which is an honest visualization.)

## CA flip-flop / latch — persistent memory by DESIGN works (2026-06-16)
`flipflop.py`: two mutually-annihilating CA layers (each kills the other where they
overlap = winner-take-all). Territory rule = newton cx=-0.255 cy=-0.077 span=0.270
(sustained fill 0.34). Protocol SET(pulse A)->HOLD->RESET(pulse B)->HOLD:
- after SET: massA=2738, massB=0 -> A fills & HOLDS (a stored bit, persists, no input).
- after RESET: massA=1254, massB=824 -> A still dominant; B can't overpower the incumbent.
VERDICT: a WRITE-ONCE persistent latch works (real 1-bit memory by design) — the honest
positive the reservoir route failed to give. NOT yet a flippable flip-flop (reset can't
overwrite). This is the right kind of memory (digital bistable latch) vs the failed
analog reservoir (oscillator). Next: GA over rule+coupling+pulse for a clean FLIPPABLE
flip-flop (set->A, reset->B, set->A again, each persisting). Answers the user's "network
of CAs like a JK flip-flop -> memory storage?" -> yes for storage; flippability pending.

## CA memory register — chained flip-flops store a multi-bit word (2026-06-16)
`register.py`: N mutual-annihilation latch cells (the flip-flop) in isolated column-cells
on a shared board; write a random N-bit word (pulse layer A=1 / layer B=0 per cell),
HOLD (no input), read each cell (A>B -> 1). Even with a FALLBACK (un-optimised) genome:
- N=4/8/16-bit: readback 100% at hold 10 AND hold 30, decaying to ~50% (chance) by hold 59.
=> a working multi-bit CA memory register: store a 16-bit word, hold, recall exactly,
for ~30-40 steps before DECAY. Behaves like DRAM (finite retention, needs refresh), not
SRAM. Robust (works un-optimised). The flip-flop GA (job 3772715), which selected for
persistence, should extend retention; rerun register.py on the best genome when it lands.
Progression this session: analog reservoir FAILED -> digital flip-flop (1 bit, rewritable)
WORKS -> chained into an N-bit register WORKS (with DRAM-like decay). Honest memory result.

## Register refresh (DRAM-style) — helps, but needs a stable cell (2026-06-16)
Added refresh to `register.py`: every R steps, read each cell and re-pulse its winning
layer. Fallback genome, long hold=160: NO-refresh decays to ~50% by hold 80; refresh-
every-15 holds 86-88% at hold 80 but still falls to ~50% by hold 159. So refresh extends
retention but doesn't fully stabilise the (unstable) fallback latch — re-pulsing the
winner locks in errors if a cell drifted before the refresh. CONCLUSION: need a flip-flop
cell optimised for LONG-HOLD persistence (v1's fitness only checked hold~45). Plan: (1)
land flipflopga-v1 POC + rerun register on its best, (2) if retention still short, evolve
flipflopga-v2 with a LONG-HOLD-stability fitness, (3) thorough ALICE register sweep
(N x hold x words x seeds x refresh), (4) update Glider Lab. Methodical: POC -> measure
-> evolve better -> verify -> complexify.

## SOLID: stable CA memory register on the evolved flip-flop (2026-06-16)
flipflopga-v1: 60/60 islands found CLEAN flippable flip-flops on HELD-OUT seeds (best
fit 0.995, set->(647,0) reset->(0,653) set->(635,9) — near-total dominance, loser=0).
Best genome: layerA=[-0.105,-0.135,0.152] layerB=[-0.205,-0.24,0.276] psize=24 pt=10.
register.py on this evolved genome: N=8 AND N=16-bit registers read back **100% at
hold 10, 80, AND 159 — NO refresh, NO decay** (vs the fallback which decayed to chance).
=> a STABLE, SRAM-like multi-bit CA memory register. The evolved latch's perfect
dominance (loser=0) makes cells non-volatile, so chaining gives a stable register.
Memory arc complete: analog reservoir FAILED -> evolved digital flip-flop (verified)
-> stable N-bit register. Next: thorough ALICE sweep (N up to 32, hold to 600, many
words x seeds, top-K genomes) to map capacity & true retention; then complexify.

## Register THOROUGHLY VERIFIED on ALICE (2026-06-16)
regtest-v1 (30 runs: top-5 evolved flip-flop genomes x N{8,16,32} x hold{250,600},
12 random words each): EVERY condition = 100% bit-accuracy AND 100% whole-word-perfect.
=> stable, non-volatile CA memory register, >=32 bits, 600 steps, no refresh, NO
cross-talk between cells on a shared board, robust across 5 genomes. Proof of concept
LANDED and rigorously tested. The verification discipline that rejected reservoir+NAND
confirms this is real. Next (complexify, since we're sure it works): a shift register
(serial data movement), then toward a datapath. Glider Lab 5 (CA memory register demo)
built; caption updated with verified numbers.

## CA shift register — serial memory works (clock-orchestrated) (2026-06-16)
`shiftreg.py`: N=6 latch cells as a serial-in/serial-out shift register. A 24-bit stream
fed in emerged at the output delayed by exactly N=6 clocks, 18/18 = 100% fidelity. The
storage survives the repeated write/hold/shift cycle cleanly. HONEST framing: the CA
cells STORE (verified stable); the SHIFT is done by a clock controller (read all cells,
rewrite shifted) -- NOT yet autonomous in-substrate transport. Memory hierarchy now:
flip-flop (1 bit) -> parallel register (>=32 bits, verified) -> serial shift register
(delay line). GENUINE next step: autonomous substrate shift (a steerable glider carries
the bit cell-to-cell, no controller) -- ties back to the glider-routing work; harder.
Honest caveat: a full pure-CA sequential machine still needs reliable GATE COMPOSITION
(the NAND search failed/overfit), so autonomous clocking/logic is the real open problem.

## Gate composition — the honest bottleneck (nandga-v2, 2026-06-16)
Disciplined search (anchored threshold + 10 seeds + input-dependence + held-out on 14
fresh seeds), 64 islands: best HELD-OUT 39%, median 35%, 0/64 >=95%. One genome hit
TRAIN 92% but HELD-OUT 38% -- the exact overfit the held-out check exposes (and confirms
v1's "100% NAND" was this artifact). VERDICT: no generalising universal gate emerges from
the routing-fabric/glider-collision approach. EVIDENCE-BACKED MAP of the CA-computer
question:
- MEMORY: works & robust (flip-flop 60/60, register 32-bit/100%/held-out, shift register) ✓
- SINGLE GATES: AND/XOR robust only at tuned operating points (collide-v3) ~
- GATE COMPOSITION: does NOT generalise (this result) ✗  <- the wall
Gliders route ~14%, gates are impact-parameter-sensitive; composing many fragile
operations that all generalise across input-seed randomness fails. Consistent with why
collision-based computers stay mostly theoretical. So "a transformer/CPU entirely out of
these CAs" is blocked at composable logic, not at memory. Honest, calibrated, evidence-
based -- the calibrated-voice payoff. Not spinning more gate searches (64 islands is
conclusive); the bottleneck is structural, not a search-budget issue.

## "Storage IS memory" — confirmed on the memory-capacity benchmark (2026-06-16)
`memcap.py`: the SAME benchmark the analog reservoir failed (recall u_{t-k}), run on the
shift-register storage. N=8 cells, 5 seeds x 60-bit streams: recall = 1.00 at EVERY delay
k=1..8 -> memory capacity MC = 8.0 bits. vs the analog reservoir's MC = 0.08 bits (0
delays). A 100x difference. So the earlier "memory failed" was specifically the ANALOG
reservoir route; the DIGITAL storage route SOLVES working memory perfectly (MC = N).
Corrected honest map of the CA-computer question:
- WORKING MEMORY: SOLVED (register/shift-register, MC=N, held-out verified). ✓
- SINGLE GATES: robust at tuned operating points (collide-v3). ~
- GATE COMPOSITION (autonomous logic): the bottleneck (nandga-v2, 0/64 generalise). ✗
=> a CA machine can REMEMBER reliably; what it can't yet do autonomously is COMPUTE
(compose logic). Memory ✓, logic ✗ — the precise, evidence-based boundary.

## BREAKTHROUGH: universal gate from the latch -> functional completeness (2026-06-16)
The "gate composition is the bottleneck" verdict was MECHANISM-specific (collision-
routing). The user's prompt ("can you do NAND or NOR?") led to the right mechanism:
build the gate from the WORKING LATCH (threshold logic), not collisions.
`gatecell.py`: a decision cell — constant BIAS seeds the output-1 layer, inputs A/B seed
the output-0 layer, winner-take-all (mutual annihilation) decides. Tune bias-vs-input:
- NOR  (bias 14, in 22): train 100%, HELD-OUT 100%  {00:1,01:0,10:0,11:0}
- NAND (bias 18, in 14): train 100%, HELD-OUT 100%  {00:1,01:1,10:1,11:0}
Both generalise (unlike collision-routing) because they reuse the robust latch.
`compose.py`: build NOT/AND/OR/XOR/HALF-ADDER purely from the CA NAND gate (each gate =
one CA decision-cell run; XOR chains 5) -> ALL 100% over seeds. => FUNCTIONAL COMPLETENESS.
UPDATED, corrected map of "a computer out of these CAs":
- WORKING MEMORY: solved (latch -> register -> shift register, held-out). ✓
- UNIVERSAL GATE: SOLVED via latch-threshold (NAND & NOR, held-out 100%). ✓
- COMPOSITION: SOLVED (NAND -> AND/OR/XOR/half-adder, 100%). ✓
=> the substrate is FUNCTIONALLY COMPLETE: NAND + register = a CA datapath. Universal
computation demonstrated with verified, generalising components built on ONE robust
mechanism (the mutual-annihilation latch). HONEST CAVEAT: each GATE is a CA computation;
the WIRING between gates is controller-orchestrated (passes bits). Fully AUTONOMOUS
in-substrate wiring (gates physically driving each other, no controller) is the remaining
engineering step. But functional universality (gates + memory) is now real and verified.
The earlier collision-routing negative stands for THAT mechanism; the latch mechanism
resolves it. Verification discipline (held-out + composition) makes this trustworthy.

## Autonomous wiring — input-side works (2026-06-16)
`autowire.py`: a universal gate whose INPUTS are not injected at the gate but placed at
the far LEFT and must PROPAGATE ~76 cells to the gate at the RIGHT, in ONE continuous CA
run, NO controller. Mechanism: input/signal layer Z on a spreading rule (territory front
= wire), gate bias O a stable latch layer, mutual annihilation decides. TRAIN 100%,
HELD-OUT 100%, truth = NOR {00:1,01:0,10:0,11:0}. So autonomous INPUT wiring + a universal
gate, verified. (Bugfix: the 0.6 mass cap tripped on Z's healthy 0.68 fill -> raised to 0.92.)
HONEST CAVEAT: the wire FLOODS omnidirectionally (Z fills the board), not a confined
directional channel -> multiple wires would cross-talk. Needs WALLS/channels to confine
each wire. The remaining hard piece = gate1 OUTPUT autonomously driving gate2 INPUT
(output is a stable territory; a wire needs a propagating carrier -> the stable-vs-propagate
conflict). Next: confined channels + a 2-gate autonomous cascade.

## AUTONOMOUS CA LOGIC CIRCUIT — frontier solved (2026-06-16)
`autowire2.py` / `autowire3.py`: confined channels (walls) + the spreading-carrier/latch
mechanism give controller-free wiring. Progression, all HELD-OUT 100%:
- autowire.py: gate INPUTS self-propagate to the gate -> NOR (input wiring) ✓
- autowire2.py: gate1's output travels a WALLED CHANNEL to gate2 (no flooding) -> gate2
  reproduces NOR(A,B) (confined gate-to-gate wire) ✓
- autowire3.py: gate1 NOR(A,B) wired into gate2, combined with a fresh input C ->
  NOR(A,B,C) truth {000:1, else 0}, ONE continuous run, NO controller (autonomous
  2-gate LOGIC circuit) ✓
=> a controller-free CA logic circuit exists: multi-gate composed function computed by
the CA dynamics alone. With the latch register (memory), the substrate supports BOTH
autonomous logic AND memory -> the real foundation of a CA computer with no external
controller. The collision-routing negative is fully superseded: the latch-threshold gate
+ confined territory-spreading wires + walls give robust, generalising, autonomous
computation. Verification discipline (held-out) maintained throughout.

## Image-behaviour classifies rule-types for the computer (2026-06-16)
`retain.py` (user's insight: retained-image vs wipe-effect settings). Seed the full grid
with a structured image, run each rule, classify. 400 Newton rules: RETAIN 29 (retention
0.98 -> identity-like = WIRE/MEMORY; e.g. newton(-0.407,-0.237,0.564)), SHIFT/WIPE 9
(image translates, e.g. (0,-4) at newton(-0.038,0.035,0.828) -> TRANSPORT/carrier), GROW
201 (fills -> flooding carrier used in autowire), CHAOS 161 (destroys -> useless). So a
rule's image-behaviour CLASSIFIES which computer component it can be: RETAIN=wire/store,
SHIFT/WIPE=directional transport, GROW=flooding carrier, CHAOS=discard. A useful map: to
build a circuit, pick wires from RETAIN, carriers from SHIFT/GROW. Confirms the user's
"wipe = something moving" intuition = directional signal transport.

## Closing the loop: a clocked SEQUENTIAL circuit (2026-06-16)
`seqcircuit.py` (user's hunch: redesign the failed feedback now that we know retain/shift
rules). The old ANALOG feedback (feedback.py reservoir loop) gave only autocorr-gaming
oscillators (MC=0.08). DIGITAL redesign: retain-rule latch = holds a bit between ticks;
feedback = route the output bit back to the input. Two rungs, each checked vs an EXACT
math reference on HELD-OUT seeds (unfakeable, unlike the reservoir metric):
  RUNG 1 RING -- close the shift register into a loop; pattern 10110 (N=5) circulates
    intact and returns to start every N clocks. Rotates correctly on all seeds incl.
    held-out (101,250). Pure storage+shift -> output->input feedback WORKS as a process.
  RUNG 2 LFSR -- ring + an XOR feedback tap, the XOR computed by the CA NAND gate
    (gatecell decide, composed 4-NAND XOR). init 1000 (N=4) -> CA reproduces the EXACT
    reference sequence 000100110101111 (period 15, maximal for a primitive 4-bit poly)
    on train AND held-out seeds (0,7,100,250), match=True every time.
State = CA latch (verified), logic = CA gate (verified), and now the LOOP is closed:
a closed feedback loop computing a correct STATEFUL sequence over time = a sequential
circuit, not just combinational logic. The analog reservoir FAILED this test; the digital
redesign PASSES it. Honest scope unchanged: the per-tick shift/route + the clock are
controller-orchestrated (as in shiftreg.py; a real CPU also has an external clock);
autonomous in-substrate transport (channels carrying bits, cf. autowire2) is the next
step. dissemination/glider-lab8.html (local, gitignored) runs this live with the REAL
embedded latch+gate LUTs (verified byte-identical to seqcircuit.py): RING circulation +
LFSR-vs-reference match, the genuine substrate dynamics in-browser. build_lab8.py emits it.

## CA "Photoshop": the rule taxonomy as image filters (2026-06-16)
`select_presets.py` + `build_lab9.py` (user: a mini-photoshop using the image-wiping CAs on
arbitrary images). The retain.py categories ARE image effects, so each becomes a filter:
PRESERVE (retain-rules, retention ~0.99 — wire/memory), WIPE ←↙→↖ (shift-rules binned by
direction — directional transport), DISSOLVE/GROW (flooding carriers, fill->1.0), GLITCH
(chaos-rules, change ~0.9). select_presets.py scans 900 Newton coords, classifies, picks
faithful exemplars per category (4 distinct wipe DIRECTIONS), and exports their REAL rulehub
LUTs (packed base64). dissemination/glider-lab9.html (local, gitignored): load any image ->
posterize to 4 states (full grid, like retain.py) -> apply a filter; an "amount" slider scrubs
CA steps (frames cached), "bake" stacks filters, PNG export. All 10 embedded filter LUTs
verified byte-identical to rulehub (faithful, not a fake effect). Ties the computer-search
rule taxonomy (Preserve=wire, Wipe=transport, Dissolve=carrier) to a creative tool.

## CA Photoshop v2: 21 filters across 4 families + pure-JS video reel (2026-06-16)
Expanded glider-lab9 (user: more effects + stitch runs into a video using just JS).
select_presets.py now scans ALL four fractal families (Newton/Julia/Mandelbrot/Burning
Ship, 4000 coords) and classifies into PRESERVE (retention ~1.0), WIPE (all 8 directions
↑↓←→↖↗↙↘, binned by shift sign), DISSOLVE (grow), GLITCH (chaos), and a new STYLIZE bucket
(settles to a stable pattern: low change, mid retention). 21 exemplars, all embedded LUTs
verified byte-identical to rulehub. VIDEO: pure-JS reel — queue filter clips (each with its
own step count), they play in order each continuing from the previous output (stitched), and
record to a downloadable .webm via MediaRecorder + canvas.captureStream off a 3x hi-res
canvas (no libraries; Chrome/Firefox). Plus live scrub/animate/bake-stack/PNG export from v1.
dissemination/glider-lab9.html (local, gitignored); build_lab9.py emits it.

## CA-1: putting it together — a machine that runs a real program (2026-06-17)
`cacpu.py` (user: assemble the primitives into a system with real storage + real computation
that runs a small program). CA-1 is an 8-bit accumulator machine whose DATAPATH is genuine CA:
  STORAGE — 16 bytes of RAM + an accumulator, every bit a real mutual-annihilation latch
    (flipflopga-v1 genome). Roundtrip over all 128 RAM bits: 16/16 bytes exact (not toy).
  ALU — add8 (ripple-carry full-adders), sub8 (two's complement), bitwise AND, and a zero
    flag, EVERY bit computed by the verified CA NAND gate (gatecell, bias18/in14) composed
    via NOT/AND/OR/XOR. add8 10/10 + sub8 10/10 correct on random operands.
  CONTROL — fetch-decode-execute over a tiny ISA (LOADI/LOAD/STORE/ADD/SUB/AND/JMP/JZ/OUT/
    HALT); PC + decode orchestrated by controller (honest: like any CPU's control unit; the
    "latch holds without decay" was separately verified, so idle holding isn't re-simulated).
    The conditional branch (JZ) is DECIDED BY THE CA (zero flag = CA NOR-tree over ACC bits).
PROGRAMS RUN CORRECTLY (output matches reference, real loops + CA-decided branches):
  multiply by repeated addition: 7*6=42 (50 instr), 9*5=45, 3*4=12;
  sum 1..N: 1..5=15, 1..8=36 (66 instr).
So the proven primitives compose into one system: genuine CA storage + genuine CA arithmetic
running a real program with control flow. Remaining rung: place RAM+ALU as autonomous walled
regions with in-substrate routing (autowire2) so the datapath self-wires, not just self-computes.

## autowire4: the autonomous wiring kit composes — depth + fan-out (2026-06-17)
`autowire4.py` (next rung after CA-1: can the confined-channel wire self-compose so the
datapath wires itself, not just computes?). Tests the two primitives missing beyond a single
autowire2 hop, both held-out:
  TEST A ROUTING DEPTH — NOR(A,B) carried across TWO channel hops + an intermediate relay
    chamber (no bias, pure conduction): TRAIN 100%, HELD-OUT 100%. Signals cross the chip.
    (First run showed all-0 — a geometry bug: readout bias at col 128 but readout region
    cols 140-156, and the bias rule LO doesn't spread, so the region was empty; the 01/10/11
    cases reading 0 actually proved the carrier crossed. Moved bias into the readout region
    -> 100%. Verification discipline: the "failure" was mine, not the mechanism's.)
  TEST B FAN-OUT — gate1 NOR(A,B) forks through a vertical bus to TWO readouts; both
    reproduce NOR(A,B): TRAIN 100%/100%, HELD-OUT 100%/100%. A branching wire works.
VERDICT: with gate-combining (autowire3, 2-gate NOR(A,B,C)) + long-distance relay routing +
fan-out, the autonomous (no-controller) wiring kit is COMPLETE. The remaining gap to a
self-wiring CA-1 datapath is a PLACE-AND-ROUTE LAYOUT ALGORITHM (software that positions
chambers/channels/walls for an arbitrary gate netlist), not a missing CA primitive. Sharpens
the standing caveat: not "autonomous wiring is unsolved" but "auto-layout is the open work."

## The inverting repeater works — and pins the autonomy boundary precisely (2026-06-17)
`cainv.py`: testing the crux primitive for autonomous universality. The passive autowire
carrier is MONOTONE (chamber floods = OR of inputs; only the readout inverts) -> it alone
realises a single NOR level. Tested an ACTIVE inverter: a self-emitting Z source (re-seeded
each step at the chamber) that spreads down the output channel = "emit a carrier", SUPPRESSED
where an opposite-layer O input (centered on the source, larger than it) annihilates it.
Result: NOT 100%, NOR2 100%, NOR3 100% (train AND held-out). So an active NOR that emits a
ROUTABLE carrier exists. (First attempt 50/25/12% — input patches were off-center from the
source; centering them -> 100%. A sweep confirmed emit(no-input)=368 vs emit(input)=0.)
PRECISE BOUNDARY (the honest finding): the inverter's INPUT must be on the stable layer O
(to annihilate the Z source), but its OUTPUT is a spreading Z carrier. Only Z spreads, so a
routed INTERNAL carrier (Z) cannot suppress another Z source (same layer = merge, not
annihilate). Thus inversion is available only on EXTERNAL inputs (delivered on O) -> the
autonomous substrate computes single-level functions over (possibly-negated) literals, NOT
universal multi-level logic. Universal AUTONOMOUS logic needs a SECOND SPREADING LAYER so
internal carriers can invert each other. That is now the one concrete open primitive (was a
vague "self-wiring gap"). Orchestrated-transport routing (calayout) remains universal today.

## calayout: a place-and-route COMPILER for the CA gate fabric (2026-06-17)
`calayout.py` (answering "can you do it?" for the compute fabric). Give it ANY boolean
function as a truth table; it SYNTHESISES a sum-of-products netlist over the universal CA
NAND, PLACES the gates into layers automatically (floorplan: layers, depth, max fan-out),
RUNS every gate as a REAL CA NAND (the verified latch-threshold gate), and VERIFIES vs the
reference over ALL input combinations x held-out seeds. Results, all PASS:
  XOR(a,b)        -> 9 gates, 5 layers  : 16/16 over 4 inputs x 4 seeds
  MUX(s,a,b)      -> 29 gates, 11 layers: 32/32 over 8 inputs x 4 seeds
  ADD.sum(a,b,c)  -> 31 gates, 11 layers: 32/32
  ADD.carry(a,b,c)-> 28 gates, 11 layers: 32/32
So arbitrary logic compiles to a verified CA-gate circuit AUTOMATICALLY (synth->place->run
real CA->verify) — the hand-laying of the COMPUTE fabric is gone. Honest scope: inter-gate
transport is controller-orchestrated (as in CA-1 / any CPU control unit); the autonomous
wiring primitives are verified (autowire2-4) and the one missing primitive for fully-
autonomous universality is pinned (cainv: a 2nd spreading layer). So "can you do it": the
automatic place-and-route compiler — YES; fully-autonomous universal self-wiring — blocked
on one concrete, named primitive, not a vague gap.
