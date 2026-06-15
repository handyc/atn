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
