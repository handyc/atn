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
