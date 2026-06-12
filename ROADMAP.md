# atn "fake transformer" roadmap

Autonomous build session started 2026-06-12. Goal: evolve `atn` from
"attention to files in a filesystem" into "attention in the GPT sense" — a
deterministic, *unlearned* transformer that actually works over file bytes.

Guiding idea: everything stays deterministic (atn's character) — no training,
fixed/derived weights — but it reproduces the real transformer machinery and
produces measurable, useful results (prediction, generation, compression).

## STATUS (live) — what works now
- `-Z`  attention head: self-attention map, stacked layers (feedback loop),
        induction predictor, n-gram LM with honest online bits/byte, temperature
        generation, and generation by the attention softmax itself.
- `-X`  in-memory arithmetic-coding round-trip (lossless, reported).
- `--compress / --decompress`  real .atnz files on disk (bit-exact verified).
- `--corpus DIR`  filesystem-as-corpus: 2-fold held-out per-file surprisal
        (outlier finder) + generate in the directory's style.
- `-Z` also prints the 2-LAYER INDUCTION CIRCUIT (by construction): prev-token
  head (layer 0) -> induction head (layer 1), rendered side by side — shows
  in-context learning emerging from composed attention.
- HEADLINE: order-{2,4,7} model + range coder BEATS gzip -9 on text/code
  (160KB corpus: atn 42485 vs gzip -9 45994), still lossless, and correctly
  refuses to compress random data (~8.05 bpb).
- `-B`  predictive feedback loop: online Bayesian mixing whose weights are
  updated by prediction error (beats fixed backoff), + a model-based surprisal
  map / hot-spot finder.
- TOOLS: `./demo.sh` (narrated 5-act tour), `./explore.sh FILE` (interactive
  menu), `PREDICTION.md` (write-up on the prediction features).
- All modes build warning-free; full regression green. ~3900 LOC, 116K binary.

## Session note (2026-06-12)
User said "got to close the lid in 45 min", so the 5-hour window was cut short.
Completed Phase 3 (induction circuit) + demo this increment. NOT done: logistic
context-mixing (deferred, lower value). No more wakeups scheduled (machine will
sleep). Everything is on disk and tested.

## Session 2026-06-12 ("trending / map-bits")
- [x] trend.sh: score phrases under TWO brains (today vs yesterday) and sort by
      rising surprisal-drop. Demoed: election phrases +4.0 (rising), flood phrases
      -3.9 (fading), neutral ~0. The day-vs-day timeliness diff.
- [x] --map-bits N: runtime-tunable per-map entry cap (2^N, default 22) for
      fidelity-vs-RAM on big corpora. load_weights sizes maps to the exact saved
      entry count, so a brain reloads fully regardless of the query-time cap.

## Session 2026-06-12 ("score / news corpus / probe fix")
- [x] `--score`: per stdin line, print surprisal (bits/byte) under the brain
      (gpt.c score_query). Low = fits the corpus, high = novel/off-topic. Demoed
      on a 16 MB 1934-news brain: "the President said" 1.7 bpb vs "instagram
      selfie" 3.6 vs gibberish 6.0. This is the fit/novelty/"timeliness" signal.
- [x] PERF FIX: bounded linear probing (MAP_PROBE=128). A saturated hash map on a
      high-diversity corpus (news + OCR noise) was degrading to O(cap) per lookup
      and hanging training. Now bounded; excess n-grams drop gracefully. 16 MB
      news trains in ~24s. Raised MODEL_CAP to 64 MiB so 16-32 MB corpora are read.
- News corpus method: dell-research-harvard/AmericanStories on HF (Chronicling
  America OCR by year). ~2.8 MB article text/day in 1934 -> 16 MB ~= a week.

## Session 2026-06-12 ("one-shot / cron / strip-html")
- [x] `--ask`: one stdin line -> one reply line -> exit (gpt.c chat_once). For
      cron/spare-cycle use; brain carries state across invocations (one turn per
      hour). Learns by default; `--no-learn` queries a corpus read-only.
- [x] `--strip-html`: with --train, strip tags/script/style/entities so HTML
      books (Gutenberg) train on prose. autotrain now also prints a learnability
      number (model bits/byte vs order-0 entropy).
- Idea noted (not built): a wrapper could learn idle hours and schedule the
  hourly turns then — but that's an OS/cron layer, not core atn.

## Session 2026-06-12 ("autotrain / weights")
- [x] AUTOTRAIN `atn --train DIR` (gpt.c): recursively ingest every text file
      under DIR into the brain (skips non-text via printable-ratio check),
      rebuild the model, save weights. Then `atn -c` chats. Tested on a 6 MB
      TinyStories slice -> fluent simple-story replies.
- [x] WEIGHTS CACHE: chat now saves atn.brain.weights (binary n-gram tables) and
      reloads it if the transcript matches (else rebuilds). map_put() added.
      NOTE: weights are derived from the transcript (consolidation/speed cache).
- [x] FIX: chat sized hash maps for the initial brain size, dropping n-grams as a
      session grew -> lossy model/weights. model_build_reserve() adds headroom;
      load-from-weights now == rebuild-from-text (verified).
- [x] chat respects --temp; default brain now sits next to the binary; raised
      MODEL_CAP to 16 MiB and MAP_CAP to 4 M so real corpora train fully.

## Session 2026-06-12 ("chat / reality port")
- [x] CHAT MODE `atn -c` (gpt.c chat_session): minimal terminal chat, plain
      stdin/stdout, Ctrl-D or /q to exit, drops back to shell. The chat is the
      model's REALITY PORT — starts untrained (babbles noise), trains online on
      what the USER types (not its own output → avoids self-collapse), replies by
      sampling a continuation, persists a plain-text "brain" (atn.brain next to
      the binary, or --brain FILE) and reloads it next session. Human
      unpredictability = the
      training signal. This is the conversation's whole arc made concrete:
      prediction + online learning + memory + an intermittent reality opening.

## Session 2026-06-12 ("deeper")
- [x] MATCH MODEL added to cm.c — an induction head inside the compressor:
      hash the last 6 bytes, recall the position that followed that context, and
      predict the byte there; an extra mixer input with length-calibrated
      confidence. text 1.98 bpb, periodic crushed to 29B (gzip 50B); lossless.
      NOTE (honesty): context mixing is a ~20-yr-old known method (PAQ/lpaq);
      beating gzip is expected. atn is a small lpaq-style reimplementation, slow,
      16MB-capped — NOT a novel algorithm. See reply to user.
- [x] CONTEXT-MIXING COMPRESSOR (cm.c): the feedback loop made load-bearing.
      Bit-level CM — 7 models (orders 0..8), online-trained logistic mixer, SSE.
      Drives a binary arithmetic coder; lossless round-trip verified (incl tiny
      + empty + binary). BEATS gzip -9: text 2.07 vs 2.40, code 2.17 vs 2.39,
      ELF 3.39 vs 3.83 bpb. Now the engine behind -X and --compress (.atcm);
      --decompress auto-detects .atcm vs old .atnz. 0 warnings.

## Session 2026-06-12 (afternoon, user back at uni)
- [x] DEEPER FEEDBACK LOOP: `-B` predictive feedback — online Bayesian mixing of
      nested backoff experts; posterior weights updated by prediction error each
      byte (the error->weight->prediction loop = a transformer's gradient feedback,
      deterministic + online). Beats fixed backoff on text/ELF/random; converges
      e.g. to 0.99 on <=order-7 for binaries. Includes a model-based SURPRISAL MAP
      (where the tool "looks hardest") + hot-spot offsets. In gpt.c.
- [x] explore.sh  — interactive menu to try each feature (tested headless)
- [x] PREDICTION.md — write-up on the prediction features
- [x] demo.sh — now a fully narrated 5-act auto-demo incl. the feedback step

## Phases

- [x] Phase 0 — attention head `-Z`: soft self-attention map, stacked layers
      (feedback loop), induction next-byte predictor, greedy generation.
- [x] Phase 1 — make generation real:
      - [x] temperature sampling from the full next-byte distribution (escapes
            greedy loops, mixes contexts); deterministic PRNG; `--temp`, `--gen`
      - [x] soft-attention generation (kernel-smoothed prediction via the
            attention softmax, not n-gram tables)
      - [x] bits-per-byte / cross-entropy metric — ONLINE/prequential so it's
            honest (random -> 8.05 bpb, matches gzip; text/ELF beat order-0).
            gpt.c holds the model; attn.c does the soft-attention generation.
- [x] Phase 2 — a fake transformer that *works* end to end:
      - [x] Subbotin range coder driven by the model -> lossless compress (-X)
      - [x] decompress with the same online model -> round-trip LOSSLESS verified
      - [x] competitive with gzip on text (corpus.txt: 43796 vs gzip 43600),
            correctly fails on random (8.06 bpb). In gpt.c.
- [ ] Phase 3 — a real (unlearned) transformer forward pass (LOWER VALUE: random
      weights predict at chance; the n-gram is the model that actually works).
      Reframe as: hand-WIRED 2-layer induction circuit (QK/OV set by construction)
      that demonstrably does in-context copying — ties to the induction-heads
      interpretability result. Optional/illustrative.
- [x] Phase 5 — real file compression I/O: `--compress FILE -o OUT` writes a
      .atnz file; `--decompress` restores it (stdout or -o). Verified bit-exact
      on README.md and gpt.c. The fake transformer is now a usable compressor.
- [x] Phase 6 (tuning) — orders centralised in model_set_orders(); bumped to
      {2,4,7} (order-7 is the max the (ctx<<8)|byte 64-bit key allows). Now
      BEATS gzip -9 on text/code. Round-trip still lossless.
      NOTE: .atnz has no order header yet, so changing orders breaks old files.

## Next (for the continuation)
- [x] Phase 3 (conceptual) — hand-wired 2-layer attention-only INDUCTION circuit
      in attn.c (induction_circuit): prev-token head (layer 0, sub-diagonal) ->
      induction head (layer 1, causal triangle), both rendered side by side.
      By construction, no learning. Accuracy: periodic 100%, ELF 82%, text 21%,
      random 0%. Shows in-context learning emerging from composed attention.
- [x] .atnz header now embeds NORD + orders (magic ATNZ2); decompress validates
      and refuses incompatible files. Done.
- [ ] (deferred, lower value) context-mixing of orders (logistic mix) for even
      better bpb — we already beat gzip -9 on text, so not pursued in the short
      window. Good future direction if revisited.
- [x] DEMO: ./demo.sh walks the whole arc with live numbers (corpus outliers ->
      induction circuit -> bpb -> generation -> beats-gzip lossless compression).
- [x] Phase 4 — filesystem as corpus ("attention to the files") — `--corpus DIR`:
      - [x] builds a byte model over the whole directory tree
      - [x] 2-fold HELD-OUT per-file surprisal (each file scored by a model that
            never saw it — fixes train-on-test; aliens now correctly surface)
      - [x] outlier ranking: planted random/gzip/Chinese files top the list at
            ~8-9 bpb vs source at ~2.4-3.7 bpb
      - [x] "generate in the style of this directory". In fleet.c + gpt.c API.

## Notes / state

- Model lives in attn.c (the `-Z` section). Keep each step compiling + tested.
- Validate with the discipline used so far: text vs random vs periodic vs ELF.
- Determinism: use a fixed-seed xorshift PRNG, never time/rand, so the same
  file always yields the same generation/compression.
