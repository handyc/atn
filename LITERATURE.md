# Literature survey: novelty map of the class-4 / Mandelbrot / CA-reservoir program

Deep-research pass (2026-06-15): 5 angles, 21 primary sources, 25 claims adversarially
verified (20 confirmed / 5 killed). What's established prior art vs genuinely novel.

## Established — we independently reinvented it
- **Reservoir Computing with CAs (ReCA)** for symbol/sequence prediction:
  **Yilmaz 2014–15** (arXiv:1410.0162, 1503.00851), named by **Margem & Yilmaz 2016**,
  extended by **Nichele's group 2017** (arXiv:1702.03812). Our "CA reservoir for byte
  prediction" is ReCA, rediscovered.
- **GA over CA rules:** **Mitchell, Crutchfield & Hraber 1993** (adap-org/9303003);
  Packard 1988. The canonical evolve-CA-for-computation reference.
- **Coupled / non-uniform CA reservoirs:** **Nichele & Gundersen 2017** ("parallel
  loosely-coupled CA reservoirs"; complementary rules combine, mirrored-complements
  make dead regions). Our network-of-CAs is largely published; only MoE-routing over a
  GA-evolved graph looks underexplored.

## CONTESTED — the literature challenges "class-4 is the key"
- **Class-4 is NOT uniquely best as a reservoir.** Best 5-bit-memory rules are **class-3**
  (90,150,182,22; Yilmaz 2015). "All four categories represented among successful rules"
  (McDonald 2017). **Carroll 2020**, *"Do Reservoir Computers Work Best at the Edge of
  Chaos?"* — skeptical.
- **Edge-of-chaos/λ hypothesis refuted (1993):** evolved rules cluster near λ≈0.5, not at
  critical-λ; Packard's edge-of-chaos clustering was a GA artifact (Mitchell et al.).
- **λ alone is insufficient:** classes II/III/IV coexist at fixed λ → need a 2nd parameter
  (Sakai-Kanno F, nlin/0211015; cf. Wuensche's Z / input-entropy).
- **Fractals link to class-3, not class-4** (Culik & Dube 1989) — weakens the
  "fractal self-similarity ⇒ class-4" premise behind mandelhunt.

**Implication for our result:** we showed class-4 fractal rules ≫ **random** rules. Random
K=4 rules are *destructive* chaos, so that's **"structured ≫ random,"** which is solid and
matches the field. We have NOT shown class-4 ≫ *good* class-3 (linear/additive rules like
90/150, which the literature says actually win). That head-to-head is the open test →
`ga-sweep-v2` adds a **linear-rule (structured class-3) arm**.

## Genuinely novel (no prior art found — but absence-of-evidence)
- **Deriving CA rules from escape-time fractals (Mandelbrot/Julia posterization)** — the
  mandelhunt move — appears unexplored. Existing fractal-CA work goes the opposite way
  (CAs *generate* Sierpinski-type substitution fractals).
- **Class-4 persistence across lattice dimensions** (2D-hex rule reused as 3D cubic) —
  unexplored as posed.
- **Hex K=4 CAs + routable input ports (cell8/cell10)** — not located.
- **Caveat (from the report):** did NOT exhaustively search **Wuensche's DDLab** corpus,
  hex-CA/ALife art, or demoscene — the likeliest places latent prior art hides. Treat
  novelty as "not found," not "proven new."

## People / venues to read
Yilmaz; Nichele (& Gundersen, Molund); Mitchell / Crutchfield / Hraber; Packard; Langton;
Wuensche (DDLab, Z-parameter); Sakai & Kanno (F-parameter); Carroll (edge-of-chaos
skepticism); ReLiCADA 2023 (linear-rule pre-selection, arXiv:2308.11522). Venues:
*Complex Systems*, *Artificial Life*, arXiv nlin.CG / cs.NE, *Chaos*.

## Refuted in verification (do NOT cite as support)
- "ReCA needs orders of magnitude less compute than ESNs" — refuted (0-3).
- "Fractal-generating rules exhibit class-4 transients" — refuted (1-2).

## Lit-review checkpoint 2026-06-16 — direction law + surgery + fractal generation
Searched (WebSearch) for prior art on the three claims behind glider-steering.md.

- CLOSED-FORM GLIDER-DIRECTION PREDICTOR from the transition table: none found.
  Glider velocity is defined/measured as displacement/period; Wuensche's
  Z-parameter / input-entropy predict glider LIKELIHOOD, not direction. => our
  18-entry single-neighbor activation law (heading = angle(F)+180, corr 0.86-0.98)
  appears NOVEL.
- GLIDER "DESIGN": prior art = evolutionary SEARCH for gliders/glider-guns (Sapin,
  Bull, Adamatzky; GA approaches). Direct ANALYTIC construction by editing 18 table
  entries ("glider surgery") not found => NOVEL.
- CA ANISOTROPY / direction-from-neighbor-asymmetry: studied, but as an ARTIFACT to
  REDUCE (solidification/diffusion front anisotropy; grid-anisotropy reduction
  methods) or as a property to ENCODE in graph CA — never as a predictive/generative
  closed-form steering law. Context, not precedent. (Sci.Direct S0303264796016644;
  "Grid anisotropy of propagation fronts in CA and its reduction methods".)
- FRACTAL-IMAGE -> CA-RULE (posterize escape-time -> K=4 LUT): not indexed. The known
  direction is the REVERSE (CA generate fractals — Wolfram, "Inherent Generation of
  Fractals by CA"). => fractal-walk generation appears NOVEL (modulo indexing).
- COLLISION LOGIC: Adamatzky & Martínez (arXiv:1803.05496), Rule 54 gates — isotropic
  rules. Confirms our blocked-collision result is consistent with the field.
- CONTINUOUS-CA STEERING: Lenia velocity optimization (arXiv:2508.04167) is LEARNED,
  not closed-form; closest cousin to our coordinate dial.

Verdict: three defensible novel pieces (direction law, surgery, fractal generation);
prior art is substrate (hex K=4: Wuensche/DDLab), ReCA, and collision logic. Next
review trigger: after the speed problem or a from-scratch (no base rule) glider
construction.
