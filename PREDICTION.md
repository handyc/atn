# Using atn's prediction features

`atn` doesn't just describe a file statically — it tries to **predict** it, byte
by byte, the way a language model predicts text. Everything here is
deterministic and **unlearned**: there is no training and no neural network, just
counts gathered as the file is read, plus the same attention/feedback machinery a
transformer uses. The point is that prediction is a measurement: *how predictable
a file is, and where it surprises the model, tells you a lot about it.*

This guide covers the four prediction features and how to read their output.

---

## 1. The attention head — `-Z`

```sh
atn -Z FILE
```

One section, several parts, top to bottom:

- **soft self-attention** — each byte becomes a token (content embedding +
  sinusoidal position); a causal scaled-dot-product softmax attention map is
  printed. This is the literal transformer operation with fixed weights.
- **stacked layers** — the attention output is fed back in as input, layer after
  layer (a residual stream). The `delta` column shrinks as the representation
  settles — that's depth/feedback.
- **induction head** + **2-layer induction circuit** — the mechanism behind
  in-context learning: find where the current context occurred before and predict
  what followed. The circuit view shows a *previous-token head* (layer 0) feeding
  an *induction head* (layer 1), built by construction.
- **language model** — an n-gram-with-backoff byte model scored *online*: each
  byte is predicted from only the preceding bytes. Reports **bits/byte**.
- **generation** — autoregressive sampling, feeding each output back in.

### Reading it
- **induction accuracy** ("acc(covered)"): of the times this context had been
  seen before, how often the next byte was predicted correctly. ~65% on English,
  100% on periodic data, ~0.4% (chance) on random.
- **cross-entropy (bits/byte)**: the model's average surprise per byte. Lower =
  more predictable. Compare it to the printed *order-0 entropy*: beating it means
  the model found sequential structure (not just a skewed byte histogram).

---

## 2. The predictive feedback loop — `-B`

```sh
atn -B FILE
```

This is the deepest "transformer feedback" piece. Several **expert** predictors
(nested backoff models, from unigram up to the full order-7 model) each propose a
next-byte probability. They are blended, and after every byte the blend weights
are updated by the prediction error (Bayesian model averaging with a fixed-share
term to stay adaptive). That **error → weights → better prediction** loop is, in
miniature and online, the same shape as the gradient feedback that trains a
transformer — but deterministic and with no pre-training.

### Reading it
- **mixed vs fixed-backoff bits/byte**: the mix is guaranteed competitive with
  the full model and usually a bit better — the gain *is* the feedback.
- **posterior weights (start → end)**: which context length the model *learned to
  trust* for this file. Text leans on short/medium orders; binaries often
  converge near 1.0 on the longest order.
- **surprisal map**: per-window model bits/byte as a sparkline. Tall = the model
  is surprised there = information-dense or anomalous. The **hottest regions**
  are file offsets worth looking at closely (embedded blobs, encrypted sections,
  format boundaries). This is "looking very closely" driven by prediction.

---

## 3. Compression — `-X`, `--compress`, `--decompress`

This is the feedback loop made **load-bearing**. A bit-level **context-mixing**
predictor (7 models at orders 0..8, each predicting the next bit; a logistic
mixer whose weights are trained online by the prediction error; then an SSE/APM
refinement) drives a binary arithmetic coder. The decoder runs the identical
online predictor in lockstep, so the round-trip is provably lossless. The mixer
*is* a one-layer neural net learning as it reads — the same shape as a
transformer's gradient feedback, but deterministic and untrained.

```sh
atn -X FILE                       # in-memory: size, bits/byte, verified round-trip
atn --compress FILE -o OUT.atcm   # write a real compressed file
atn --decompress OUT.atcm -o RESTORED
```

### Reading it
- **bits/byte** is the achieved compressed size × 8 / original.
- It **beats `gzip -9`** on text, source code, and binaries — e.g. text ~2.07
  bits/byte vs gzip's ~2.40; an ELF ~3.39 vs gzip's ~3.83. On already-random or
  encrypted data it correctly refuses to shrink (~8 bits/byte).
- `--decompress` auto-detects the format (the context-mixing `.atcm` stream, or
  the older byte-model `.atnz`).

---

## 4. The filesystem as a corpus — `--corpus`

```sh
atn --corpus DIR
```

Builds one byte model over a whole directory tree, then scores **each file's
surprisal** under it (two-fold held-out, so no file is graded by a model that
memorised it). Files that fit the tree score low bits/byte; files that don't —
encrypted, compressed, a foreign language, the wrong type — score near 8 and rise
to the top as **outliers**. The same number is a language-model loss at the byte
level and a content-grounded anomaly score at the tree level.

---

## Quick recipes

```sh
atn -B firmware.bin            # where is this binary most information-dense?
atn -Z -q paper.txt            # how predictable / what does the model "think"?
atn --compress logs.txt -o logs.atnz   # actually compress it
atn --corpus ~/project/src     # which file in my source tree doesn't belong?
./explore.sh somefile          # interactive menu over all of the above
./demo.sh                      # narrated tour with live numbers
```

## The one idea

A file's **predictability** is a measurement. atn computes it with the real
transformer mechanisms — attention, induction, layered feedback, error-driven
reweighting — but deterministically and untrained. Low surprise means structure
the model captured; high surprise, localised by the surprisal map, is exactly
where a file is hiding something worth a closer look.
