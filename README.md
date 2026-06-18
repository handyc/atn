# atn

A C utility that looks very closely at files — both at the macro level (what
*kind* of thing is this, numerically?) and the micro level (what specific
patterns, routines, and anomalies live inside this exact file?).

> **Try the whole thing in one command** (clean clone, no data needed).
> `./demo-all.sh` runs all four corpus demos below back to back (~20 min);
> or run any one on its own:
> `./demo-news.sh` streams 1920–1940 news from the AmericanStories archive,
> cleans it, evolves a population of GA "brains" over it, then runs example
> classify / novelty / mixture queries — end to end in ~5 minutes.
> `./demo-languages.sh` does the same over a seven-language Wikipedia corpus
> (en/nl/fr/de/es/it/zh), where the experts separate crisply by language (an
> English query lights up the English expert, Dutch the Dutch one, Chinese the
> Chinese one…) — the clearest view of what an expert specialises in.
> `./demo-code.sh` does it for *machine* text instead — C, Python, shell, x86-64
> assembly, and hex/binary dumps sampled from the local filesystem — and the
> experts separate by kind of code (atn on home turf).
> `./demo-formal.sh` generates six *formal* notations (first-order logic, linear
> algebra, set theory, calculus, lambda calculus, regex) and separates all six —
> the close call being first-order logic vs lambda calculus, which share a surface
> shape (binder + variables + parens) yet still split once ∀ and λ are tokenized.
> See [GA.md](GA.md) for the mixture-of-experts they build.
> `./demo-meta.sh` then trains on the previous trainings: it pools those runs'
> corpora and evolves one meta-population spanning all of them, so a query of any
> kind — a 1920s headline, a Dutch sentence, a C snippet, a logic formula — routes
> to its region.
> `./demo-route.sh` builds a 2-level routing tree over the runs: a cheap coarse
> gate picks the domain, then that domain's population picks the expert — sublinear
> routing (a handful of brains scored, not the whole forest).

It answers three questions about any file:

1. **What is it?** — type identification from magic bytes, plus a
   structural breakdown of the recognized type.
2. **What is it *like*, numerically?** — entropy, randomness tests,
   self-similarity, noise, and a windowed entropy map.
3. **What's *in* it worth noticing?** — embedded files, opcode/routine
   patterns, known signatures, and structural anomalies.

## Build

```sh
make            # produces ./atn   (needs a C11 compiler + libm)
make test       # fast, deterministic, network-free regression suite
make install    # to $PREFIX/bin (default /usr/local)
./demo.sh       # narrated tour of the whole "files -> GPT attention -> working transformer" arc
./explore.sh F  # interactive menu to poke at every feature on a file
```

The **[web/](web/)** corpus atlas turns a built population into interactive
teaching visualizations: the GA's learning curve, a corpus **tiling map**, a live
per-character **surprisal heatmap** (watch the model read), a next-byte
**prediction** chart (watch it guess), the routing graph, and live query routing.

See **[PREDICTION.md](PREDICTION.md)** for a focused guide to the prediction
features (`-Z` attention/LM, `-B` feedback loop, `-X` compression, `--corpus`).

## Usage

```
atn [sections] [tunables] FILE...      ('-' reads stdin)
```

With no section flags you get the basic report (size, perms, type, entropy).
Add section flags to go deeper, or `-A` for everything.

### Sections

| flag | section | what it tells you |
|------|---------|-------------------|
| `-S` | statistics | mean/median/std-dev byte, Shannon entropy, estimated compressibility, RLE redundancy, chi-square vs. uniform, serial correlation, Monte-Carlo π, noise (mean adjacent-byte delta) |
| `-E` | entropy map | per-window entropy as a sparkline + flagged high-entropy regions and boundaries (finds embedded/compressed/encrypted blobs, à la binwalk) |
| `-C` | self-similarity | strongest repetition period (record/block size), candidate block sizes, and the most-repeated 8-byte chunks |
| `-T` | structure | type-specific parse: PNG/JPEG/GIF/BMP, WAV/RIFF, gzip, ELF, ZIP central directory, **PE sections**, **MP4/ISO-BMFF box tree**, **PDF objects/streams/actions** |
| `-F` | embedded | carve known file signatures appearing anywhere past the header |
| `-P` | patterns | routine/opcode byte patterns: `INT 21h`, `INT 80h`, `SYSCALL`, function prologues, NOP sleds, GetPC, `RDTSC`, … — each hit is **cross-checked against the disassembler** and marked when it lands on a real instruction boundary |
| `-M` | signatures | EICAR test file, common packer/protector markers (UPX, Themida, …); load more with `--sigs` |
| `-K` | anomalies | extension/type mismatch, truncation, trailing/appended data, invalid UTF-8, mixed line endings, large uniform padding |
| `-D` | disassembly | linear x86/x86-64 disassembly of the ELF `.text` (or whole file); also powers opcode verification under `-P` |
| `-Z` | attention | a hand-wired, **unlearned** transformer over the bytes: self-attention map, stacked layers (feedback loop), induction predictor + 2-layer induction circuit, an n-gram language model with **bits-per-byte** + **temperature-sampled generation**, and generation by the attention softmax itself |
| `-B` | feedback | **predictive feedback loop**: online Bayesian mixing of nested backoff experts whose weights are updated by prediction error each byte (a transformer's gradient feedback, deterministic), plus a model-based **surprisal map** locating a file's information-dense / anomalous regions |
| `-X` | compression | a **context-mixing** coder (7 bit-models + an online-trained logistic mixer + SSE) driving an arithmetic coder, with a verified **lossless round-trip** — the feedback loop made load-bearing, and it **beats gzip -9** on text, code, and binaries |
| `-x` | hex dump | classic hex + ASCII |
| `-s` | strings | printable runs with offsets |
| `-A` | — | all of the above |

`--yara FILE` runs a (subset) YARA scan as its own section; `--sigs FILE`
adds custom byte signatures to `-M`.

### Filesystem scan

```
atn -R DIR        recursively scan a tree, then print aggregate statistics
atn -R -v DIR     also print one summary line per file as it goes
atn -R /          scan the whole filesystem (skips /proc /sys /dev /run,
                  never follows symlinks)
atn -R -P -K DIR  run the per-file opcode + anomaly sections on every file,
                  then the aggregate (combine with any section flag)
```

The aggregate report covers: file/dir/byte totals, text-vs-binary split, mean
entropy and an entropy histogram, a type-distribution table, counts of flagged
files (anomalies, embedded signatures, EICAR/packer hits), and the largest /
highest-entropy files.

By default up to 16 MiB is read per file for the aggregate metrics (true size
still comes from `stat`). When you combine `-R` with section flags (`-S -E -P
-T -D --yara`, …), each file is read in full and the requested sections are
printed per file, followed by the aggregate — e.g. `atn -R --yara rules.yar /`
runs a YARA sweep over the whole filesystem, or `atn -R -P /usr/bin`
disassembly-verifies opcode patterns in every binary.

### Tunables

```
-w N      window size for -E / -C        (default 256)
-n N      bytes shown in hex dump, 0=all (default 256)
-m N      minimum string length for -s   (default 4)
--bits N  force 32 or 64 for -D / -P     (default: auto-detect from ELF/PE)
-g PAT    search for a pattern: 'CD21', 'cd 21', '\xCD\x21', or ASCII text
--sigs F  load extra 'name:hexpattern' signatures for -M
--yara F  scan with a (subset) YARA rule file
-q        quiet: drop the basic report (keep requested sections)
-v        with -R, print one line per file
-h, -V    help, version
```

## Reading the numbers (the `-S` section)

- **entropy** — bits/byte, 0–8. `~8.0` with a low chi-square means random /
  encrypted / well-compressed. Mid (4–6) is typical structured binary.
- **chi-square** (`z` vs uniform) — near 0 ⇒ byte distribution looks uniform
  (random-like). Huge `z` ⇒ strongly structured.
- **serial correlation** — 0 means each byte is independent of the previous;
  toward ±1 means the next byte is predictable from the last.
- **Monte-Carlo π** — uses the bytes as coordinates; a small π-error is another
  independent randomness signal.
- **noise (mad)** — mean absolute difference between adjacent bytes; high in
  busy/random data, low in smooth/repetitive data.

## Custom signatures

`--sigs FILE` reads one rule per line, `name:pattern`, where `pattern` is hex
(`DEADBEEF`), spaced hex (`de ad be ef`), `\xNN` escapes, or literal ASCII.
Lines starting with `#` are comments.

```
# my-sigs.txt
suspicious-marker:DEADC0DE
my-magic:\x7f\x4d\x59
banner:Hello World
```

## Examples

```sh
atn report.pdf                 # quick: type + entropy
atn -A firmware.bin            # everything
atn -E -w 1024 disk.img        # entropy map to spot embedded partitions/blobs
atn -C capture.dat             # find a fixed record size in a binary log
atn -P -g CD21 game.com        # opcode scan + highlight every INT 21h
atn -T -K photo.jpg            # structure + truncation/trailing-data checks
atn -M -s sample.exe           # signature scan + strings
atn -D firmware.bin            # linear x86 disassembly
atn --yara rules.yar a.bin     # subset-YARA scan
atn -R -v ~/Downloads          # scan a tree, line per file + aggregate stats
atn -R /                       # whole-filesystem survey
cat stream | atn -S -          # stats on a pipe
```

## The attention head (`-Z`)

`-Z` turns the self-similarity idea into the transformer's actual mechanism,
with hand-built (not learned) projections. It runs the swept bytes through the
whole transformer loop, in order:

- **Soft self-attention.** Each byte position becomes a token with a fixed
  content embedding plus a sinusoidal positional encoding (from *Attention Is
  All You Need*). It runs scaled dot-product attention with a causal mask and
  softmax over a window, then prints the attention map and its statistics
  (mean attention distance, attention entropy, strongest attend-back).
- **Stacked layers (the feedback loop).** The attention output is added back
  to the representation (residual stream), layer-normalised, and fed in again,
  layer after layer — exactly how depth works in a transformer. The per-layer
  `delta` shows the representation settling as it iterates.
- **Induction head.** The mechanism behind in-context learning: for each
  position it finds earlier positions whose preceding context matches the
  current one and predicts the byte that followed — i.e. it does GPT's job,
  next-byte prediction, as a hard top-1 attention over exact context matches.
  Accuracy is a real, comparable number.
- **2-layer induction circuit (by construction).** The actual circuit from the
  induction-heads literature, hand-wired with no learning: a *previous-token
  head* (layer 0, a clean sub-diagonal) feeds an *induction head* (layer 1, the
  causal triangle), both printed side by side. It shows in-context learning
  *emerging from composing two attention heads* — periodic 100%, ELF ~82%,
  text ~21%, random 0%.
- **Language model + bits-per-byte.** An n-gram-with-backoff byte model (the
  role a trained transformer plays: a next-byte distribution) is scored
  *online/prequentially* — each byte predicted only from preceding bytes — to
  give an honest cross-entropy in bits/byte. Below the order-0 entropy means it
  found structure; random data correctly lands at ~8 bpb (matching gzip).
- **Generation.** Two generators feed their output back, autoregressively:
  temperature sampling from the n-gram distribution (`--temp`, `--gen`;
  deterministic PRNG, so reproducible), and generation by the **attention
  softmax itself** (fuzzy multi-byte context matching via embeddings — no
  tables). Low temperature copies coherent spans; high temperature dissolves
  into noise, exactly like a real model.

The induction accuracy and bits-per-byte are predictability signals that vary
enormously by content:

| file | order-8 induction acc. | online bits/byte |
|------|------------------------|------------------|
| English text | ~65% | ~2.4 (large corpus) |
| periodic data | 100% | ~0.15 |
| random bytes | ~0.4% (1/256 floor) | ~8.05 (≈ gzip) |

Nothing is trained — it stays deterministic, like the rest of `atn` — but it
reproduces *why* a transformer can model structured data and not noise.

## Compression: the fake transformer that works (`-X`)

`-X` proves the model is real by using it to compress, with the feedback loop
load-bearing. A bit-level **context-mixing** predictor — 7 context models
(orders 0..8), a **match model** (an induction head: recall what followed this
context last time), a logistic mixer trained online by prediction error, and an
SSE refinement — drives a binary arithmetic coder; the decoder runs the
*identical* online predictor in lockstep, so the round-trip is provably
lossless. It compresses better than `gzip -9` on text, code, and binaries, and
correctly refuses to shrink random data.

```
atn -X corpus.txt                      # -> ~1.98 bits/byte, lossless round-trip
atn --compress big.log -o big.atcm     # real on-disk compressed file
atn --decompress big.atcm -o restored  # auto-detects .atcm / .atnz
```

| file | atn `-X` | gzip -9 |
|------|----------|---------|
| 144 KB text corpus | 1.98 bpb | 2.40 bpb |
| ELF binary | 3.31 bpb | 3.83 bpb |
| periodic data | 0.06 bpb | 0.10 bpb |
| random bytes | ~8.0 (refuses) | ~8.0 (refuses) |

**This is not a new compression algorithm — see the honest note below.**

## Prior art & honest limitations

`atn`'s compressor is a small, faithful re-implementation of **context mixing**,
a technique that has existed since ~2002. It is *not* novel, and beating `gzip`
on ratio is expected, not a breakthrough.

- **Lineage.** Context mixing is Matt Mahoney's **PAQ** family and its smaller
  relatives **lpaq** and **zpaq**; `cm.c` is closest to lpaq. The components here
  — bit-level context models, a logistic mixer trained online, SSE/APM, and a
  match model — are all standard, named pieces from that literature. These
  compressors are well known for topping ratio benchmarks (the Large Text
  Compression Benchmark, the Hutter Prize).
- **gzip is old and fast, not strong.** DEFLATE (1991) optimises for speed with a
  32 KB window. `bzip2`, `xz`/LZMA, `zstd`, and `brotli` all beat it on ratio
  too. On the source corpus above `atn` also edges out `xz -9` and `bzip2 -9`,
  but that corpus is highly repetitive and small — on other data the ranking
  shifts, and a real PAQ8/cmix would beat `atn` comfortably.
- **The trade is speed and scale.** `atn` codes bit-by-bit with ~8 hash lookups
  per bit: it is **orders of magnitude slower** than gzip/zstd, uses ~120 MB of
  model RAM, is **capped at 16 MiB**, single-threaded, and has a fragile homemade
  container — a teaching implementation, not a production tool.
- **The real (also not-new) idea** is the equivalence at the heart of the whole
  project: *a good predictor is a good compressor* (Shannon; the basis of the
  Hutter Prize). Everything `atn` builds as a "fake transformer" — attention, the
  induction head, online error-feedback mixing — is a prediction engine, so it
  compresses. `atn` makes that idea tangible; it doesn't discover it.

## Chat (`-c`) — the model that learns from you

`atn -c` starts a minimal terminal chat. It's plain stdin/stdout — no screen
clearing, no modes — and you drop back to the shell with Ctrl-D (or `/q`). The
twist: the chat *is* the model's reality port. It starts knowing nothing (its
first "hello" is literal noise), trains online on **what you type**, replies by
sampling a continuation from what it has learned, and persists the whole
conversation as a plain-text "brain" (`atn.brain`, kept next to the binary, or
`--brain FILE`). Next session it remembers. Talk to it for a while and it starts completing your
sentences in your own style — a tiny, deterministic, learns-from-you chatbot
that is just the byte language model running in generative mode.

```
atn -c                    # chat; learns as you go; Ctrl-D to leave
atn -c --brain mybrain    # keep a separate brain file
atn -c --temp 0.4         # lower temperature = more faithful recall
```

It trains only on *your* words (the human is the reality term), not on its own
output — which would just feed back on itself. Human unpredictability is the
feature: it's where the new information comes from.

Alongside the brain it writes `atn.brain.weights` — a binary cache of the
trained n-gram tables, so it reloads instantly next session instead of
rebuilding from the transcript. (For this model the weights are derived from
the transcript, so the cache is a consolidation/speed artifact, not separate
information; it's rebuilt automatically if the brain changes.)

### Autotrain on a corpus

Point `--train` at a directory (or file) of text and it ingests everything
(recursively, skipping non-text), then you chat with the result:

```
atn --train ./tinystories --brain tiny.brain        # train on a folder of stories
atn --train book.htm --brain book.brain --strip-html # clean HTML -> prose first
atn -c --brain tiny.brain --temp 0.4                # then chat in that style
```

`--strip-html` removes tags, script/style blocks, and common entities so a
Gutenberg-style HTML book trains on prose, not markup. After training it prints
a **learnability** number — the model's bits/byte vs the corpus's order-0
entropy — so you can compare how predictable different corpora are.

Trained on a few MB of clean simple text (e.g. TinyStories), the byte model
produces surprisingly fluent story-like replies — *"Once upon a time, there was
a little girl named Lily. She said, 'Thank you!'"* It's still a Markov-style
remixer with no understanding, but it shows how much the same machinery picks up
from a good corpus. The model reads up to 16 MiB of the brain.

### One-shot queries (cron-friendly) — `--ask`

`--ask` answers stdin **line by line**: one piped line gives one reply line and
exits (a single turn); many piped lines are answered as a batch with the brain
loaded just once. The brain carries state between separate invocations too, so a
conversation can run as independent calls spread over time (e.g. one turn per
hour from `cron`, using only spare cycles):

```
echo "Once upon a time" | atn --ask --brain tiny.brain --temp 0.4   # one turn
seq 100 | sed 's/^/prompt /' | atn --ask --no-learn --brain c.brain  # 100 at once
echo "$msg" | nice -n19 atn --ask --brain conv.brain                 # gentle
```

By default `--ask` also *learns* from the input (the conversation accumulates in
the brain); `--no-learn` queries a corpus without modifying it. A `cron` entry
like `0 * * * * echo "..." | nice -19 atn --ask --brain ~/atn.brain` runs one
turn an hour at idle priority — the cycles it uses are ones that would otherwise
be wasted.

### Surprisal scoring — `--score`

`--score` prints, for each stdin line, its **surprisal** (bits/byte) under the
brain, then the line. Low = the text fits the corpus's statistics; high = novel,
off-topic, or foreign. It's read-only. This is what the model actually does
well — measure *fit*, not retrieve documents:

```
printf '%s\n' "the President said" "post a selfie to instagram" \
  | atn --score --brain news1934.brain
#  2.6  the President said            <- typical of 1934 news, low surprisal
#  4.8  post a selfie to instagram    <- out of place, high surprisal
```

Train one brain per day/week and the **same** number becomes a timeliness
signal: a phrase whose surprisal drops sharply vs an earlier brain is *trending*;
text that scores low under today's brain but high under last week's is *newly
prominent*. So the interesting use isn't "search the news" (it would remix and
hallucinate) but "is this typical of / novel to this slice of the news."

**`trend.sh`** does exactly that diff — score phrases under two brains and sort
by what's rising:

```
printf '%s\n' "the election results" "the flood waters rose" \
  | ./trend.sh today.brain yesterday.brain
#  delta   new    old    phrase
# +4.000   0.77   4.76  the election results       <- surged today
# -3.891   4.67   0.78  the flood waters rose       <- faded
```

**`autotrend.sh`** goes one step further: you don't supply phrases at all. It
mines the most frequent content phrases from *today's* corpus and ranks *those*
by rise, so it surfaces the day's emerging topics on its own:

```
TOPN=12 ./autotrend.sh today.brain yesterday.brain
#  score   rise    freq  new   old    phrase
# +13.33  +4.629   758  0.62  5.25  election results came   <- frequent AND rising
# +12.06  +4.213   728  0.99  5.21  polls closed at
# ...
```

`score = rise × log10(freq+1)`, so a phrase that is both frequent today and
newly fitting outranks a rare-but-rising one.

**`where.sh`** then shows *where* a trending phrase occurs — each match located
by line (= article index, as `--train` stores one article per line) with
context, so you can read the actual passages:

```
./where.sh today.brain "election results came"
# "election results came" — in 758 article(s)/line(s) of today.brain
#   line 1     …the election results came in tonight…
#   line 17    …the election results came in tonight…

# trending topics AND their locations, together:
TOPN=5 ./autotrend.sh today.brain yest.brain | tail -n +2 \
  | awk '{$1=$2=$3=$4=$5=""; sub(/^ +/,""); print}' \
  | while read -r p; do ./where.sh today.brain "$p"; done
```

For big or noisy corpora (OCR'd news), `--map-bits N` raises the per-map entry
cap to 2^N (default 22) for higher fidelity at the cost of RAM and a bigger
weights file — use the same `N` for training and querying.

#### Building a news corpus (e.g. 1934) — `build-corpus.sh`

`atn` ships no data. For historical newspapers, the **Library of Congress
"Chronicling America"** OCR is the public-domain source; the easiest access is
the HuggingFace mirror **`dell-research-harvard/AmericanStories`**, one
`faro_YEAR.tar.gz` per year (~1.09 GB for 1934 = the whole national press ≈
**~2.8 MB of article text per day**, so 16 MB ≈ a week). `build-corpus.sh`
streams a slice and writes two line-aligned files — the corpus text and a
metadata sidecar (date / state / paper per article):

```
./build-corpus.sh 1934 news1934 16000000   # -> news1934.txt + news1934.meta
./atn --train news1934.txt --brain news1934.brain
./where.sh news1934.txt "the president"     # context + by-state + by-date
```

That `.meta` sidecar is what lets `where.sh` report *where* (which state) and
*when* (which date) a phrase appears — on real 1934 data "the president"
concentrates in the District of Columbia and clusters on particular dates.

### Performance (rough, one laptop core)

| corpus | `--train` | brain.weights | per query |
|--------|-----------|---------------|-----------|
| ~180 KB (a play) | ~0.2 s | ~4 MB | ~0.05 s |
| ~6 MB (TinyStories) | ~15 s | ~20 MB | ~1.9 s standalone, ~0.1 s in a batch |

Per query is dominated by loading the weights file (≈3× the corpus size). Running
many queries as **one piped batch** loads it once and then costs ~0.1 s each, so
N queries take roughly `load + N × 0.1 s` instead of `N × (load + 0.1 s)`. The
training time is mostly the one-time learnability pass over the corpus.

### Preparing data for a real model — `--prep` (fast, training-free)

To prepare a corpus for actually training a neural model you don't need atn's
n-gram models at all — you need to **clean, de-duplicate, and quality-filter the
text**, which is the standard front of an LLM data pipeline. `--prep` does that
in a single streaming pass (no model trained, ~100s of MB/s, a few MB of RAM):

```
atn --prep raw1.txt raw2.txt > clean.txt      # files
build-corpus.sh 1934 d - 16000000 | ...        # or pipe a corpus in
cat corpus.txt | atn --prep > clean.txt
```

It drops, in order: control chars / whitespace noise (cleaned), too-short and
OCR-garbage lines (quality filter), exact duplicates *including* case/punctuation
variants (normalised fingerprint), and **near-duplicates** — reworded reprints,
the dominant redundancy in news — via MinHash + LSH. It also drops **OCR garbage** — lines whose
tokens mostly aren't real words (no vowels, broken length) — which is common in
scanned newspapers. On 8 MB of article-length text with 10 k planted reprints it
removed all of them in 0.13 s. Tunables: `PREP_MINLEN` (default 40),
`PREP_MINALPHA` (0.55), `PREP_MINWORD` (0.60, the word-shape threshold),
`PREP_NEAR=0` to disable near-dedup. Pass several corpora at once
(`atn --prep d1.txt d2.txt ...`) to dedup *across* them in one pass. This is the recommended path to a clean training set; the
surprisal-based `bundle --novel` below is the alternative when you want the
filtering driven by the brains' own models.

#### One command to a train-ready dataset — `prepare-llm.sh`

`--prep` gives you a clean corpus; `prepare-llm.sh` turns that into the actual
handoff a (GPU) trainer wants — cleaned, deduped, **deterministically shuffled**,
and split into `train.txt` / `val.txt`, with a `manifest.txt`:

```
prepare-llm.sh OUTDIR raw1.txt raw2.txt        # prep + shuffle + split + manifest
prepare-llm.sh data/run1 news1934.txt          # -> data/run1/{train,val,manifest}.txt
```

The shuffle orders lines by a fixed content hash (blake2b), so the same inputs
always produce the same split — reproducible across machines, no RNG. Env:
`VAL_PCT=1` (percent held out for eval), `PREP_SKIP=1` if the inputs are already
cleaned, and any `PREP_*` knob is passed through to the cleaning pass. The
manifest records line/byte counts, an estimated token count (~bytes/4), the prep
drop stats, and the settings used — everything you need to log a training run.

### Combining many brains (toward a real model)

You can't merge n-gram brains into one neural net — the parameter types are
incommensurable, and the counts are a lossy summary of the text the brains
already hold. But a *collection* of brains is useful in three honest ways, one
script each (all just orchestrate `--score` and the corpora):

- **`route.sh BRAIN_DIR "query"`** — a mixture-of-experts router: scores the
  query under every brain and picks the one that fits best (lowest surprisal).
  A cheap, interpretable "which domain/day/topic is this about" front-end.
- **`recall.sh BRAIN_DIR "context"`** — non-parametric retrieval: returns the
  *real* passages that followed that context, with provenance `[brain:line]`.
  Grounded source text (the surface-level cousin of a kNN-LM datastore), not a
  remix — so no hallucination.
- **`bundle.sh BRAIN_DIR out.txt [--novel]`** — the actual path to a real model:
  merge the brains' transcripts and de-duplicate into one clean corpus, then
  fine-tune a neural model on `out.txt`. The counts are discarded; the *text* is
  the asset the trainer relearns and surpasses. With **`--novel`** it splits the
  brains into two folds, trains a model on each (sampling a slice of every brain
  so the fold fits the model cap), and keeps each brain's lines that the
  *opposite* fold finds surprising — so boilerplate and stories shared across
  brains are dropped and the corpus keeps more signal per byte. It's two
  trainings regardless of how many brains, so it scales to dozens at a time
  (`NOVEL_BPB` sets the threshold, default 3.0).

```
route.sh ./brains "the federal reserve raised rates"   # -> finance (1.4 bpb)
recall.sh ./brains "the federal reserve"               # -> the real passages
bundle.sh ./brains corpus.txt                          # -> a training set
bundle.sh ./brains corpus.txt --novel                  # -> distinctive lines only
```

### Evolving a population that tiles a huge corpus (`atn-ga.py`)

The scaling story: instead of one brain on a big corpus (which saturates), grow a
**population** of cheap brains and use a genetic algorithm to evolve *where each
one sits*, so together they cover a corpus of any size as a routable mixture of
experts. Fitness is **coverage** (how much each brain lowers the population's
held-out bits/byte); a query "lights up" the brain whose territory it falls in.

```
python3 atn-ga.py run --corpus big.txt --out run --pop 24 --gens 14
python3 atn-ga.py run --corpus big.txt --out run --locus content   # gather by topic
python3 atn-ga.py lightup --out run "some query text"              # route a query
python3 atn-ga.py mixture --out run                                # soft online mixture
python3 atn-ga.py export  --out run --format both                  # portable CSV + SQLite
```

The driver needs **no third-party packages** — pure Python standard library. The
content signatures (MinHash / TF-IDF SimHash) and the nearest-neighbour table now
live in C (`atn --neighbors`, see `content.c`), and the mixture is plain Python.
**Non-Latin scripts work end to end** — `atn` trains on UTF-8 text (Chinese,
Cyrillic, accents) instead of skipping it as binary, and each CJK character is its
own token, so on a mixed-language corpus the experts separate cleanly by language
(`./demo-languages.sh`; an English query lights up an English expert, a Chinese
query a Chinese one). `lightup` now reads each expert's own articles to show what
it *specialises in* (its distinctive words + a sample line), and every command
prints a plain-English legend.

On a 5-language test corpus the experts self-organized by language with no
labels, and coverage beat a single brain (3.11 → 2.72 bpb). A **soft online
mixture** of the experts (`mixture`) beats any single brain by ~22% with no
hindsight — at 100 MB Wikipedia scale it reaches 2.44 bpb, beating even the
hindsight per-line oracle (2.68). Genes can address **content** (`--locus
content`) instead of position, gathering topically-similar chunks via MinHash
LSH. Paired with **document-aware chunking** (`--chunk-on '<title>'`, one article
per chunk) on 100 MB of Wikipedia, content tiling decisively beats positional
(2.70 vs 2.81 bpb) — the chunk *unit* matters more than the signature. And with
**`--evolve-orders`** the GA tunes each expert's n-gram context lengths to its
territory (now a runtime `atn --orders` gene), the biggest single win: coverage
2.69 → 2.55, mixture 2.37. A run is a **disk checkpoint**, so `ga-step.sh OUTDIR
MINUTES` advances it by a time-boxed slice and exits — drop it in cron to evolve
forever, resuming bit-for-bit (RNG state is checkpointed) and reporting an
eval-vs-test gap each tick to keep itself honest. Full design, results, scale
tests, and options in **[GA.md](GA.md)**.

**Consuming a finished run.** `atn-ga.py export` writes the population as
framework-agnostic, model-shaped data — `experts.csv` / `passages.csv` /
`edges.csv` plus a self-contained `atlas.db` (tables `run`, `expert`, `passage`,
`edge`) — ready to load into any downstream project. **[web/](web/)** is one such
consumer: a small Django "corpus atlas" that browses each expert's territory and
distinctive vocabulary, visualises the routing graph, and **routes live queries**
against the real brains (the web version of `lightup`). See [web/README.md](web/README.md).

## The filesystem as a GPT corpus (`--corpus`)

This is "attention to the files in the filesystem" meeting GPT attention:
`--corpus DIR` builds one byte language-model over the whole tree, then scores
every file's **surprisal** under it (held-out, two-fold, so no file is scored
by a model that memorised it). Files that fit the corpus score low bits/byte;
alien files — encrypted, compressed, a foreign language, the wrong type — score
near 8 and rise to the top as outliers. It also generates "in the style of the
directory."

```
atn --corpus ~/src     # ranks files by how well the corpus model predicts them
```

So the same surprisal number is, at the byte level, a language-model loss and,
at the tree level, a content-grounded anomaly score.

## YARA subset

`--yara FILE` understands a practical subset of the YARA language:

- text strings `$a = "abc"` with `nocase` and `wide` modifiers;
- hex strings `$a = { DE AD ?? BE [2-4] EF }` with nibble wildcards (`??`,
  `?A`, `A?`) and jumps (`[n]`, `[n-m]`, `[n-]`);
- conditions: `and` / `or` / `not` / parentheses, `$a`, `#a <op> N` (match
  count), `all|any|N of them`, `all|any|N of ($a*)`, and `filesize <op> N`.

Not handled (such terms evaluate to false, with a note): regex strings,
positional operators (`$a at X`, `$a in (…)`), `uintN(…)` reads, modules.

## The cellular-automaton computer & CA-OS (the `dissemination/` labs)

A separate exploration in this repo, grown from the "fake transformer" thread: build a *computer* — and
then an *operating system* — out of a hexagonal, 4-state (K=4) cellular automaton, and run it in the
browser. There are **27 self-contained HTML labs** in `dissemination/` (open `dissemination/index.html`);
each is generated locally by a `build_*.py` script. The arc:

- **Rule → gates.** The hex K=4 rule and its gliders; a mutual-annihilation **latch** (one bit of
  memory), a **NAND** gate, an inverter, a self-routing wire, a circulating register — all real CAs
  running on verified rule tables (labs 1–10).
- **A computer.** `cacpu.py` wires those primitives into **CA-1**, an 8-bit accumulator machine (latch
  RAM + a CA-NAND-gate ALU). `ca1sys.py` makes it a **parameterized family** — CA-1/2/3/4 at
  8/32/128/1024-bit — from one core; the genuine CA ripple-adder is verified bit-for-bit, including at
  256/512-bit on an HPC run.
- **An OS.** `caos_ca2.py` is **CA-OS/2**, a 32-bit desktop (Writer/Sheet/Calc/Paint) where the CA draws
  every pixel and the browser is a dumb terminal: draggable windows, a **multilingual antialiased Writer**
  (16×16 GNU-Unifont / WenQuanYi held in the CA's own memory — Latin/Greek/Cyrillic/CJK/Hangul/kana),
  full-keyboard Unicode input, file save/load. The *same* OS source boots on 32/64/128-bit (width-clean).
- **The pact.** Two nodes share a seed, run **identical** CAs (no data crosses — shared randomness), and
  communicate only by **AES-256-GCM-sealed input deltas** keyed by the CA state (`SHA-256(domain‖seq‖CA
  state)`); the receiver brute-forces a small generation window. lab24 shares a live desktop over this
  line (cut/restore, a zero-trust relay); lab26 is the bare envelope. This mirrors the velour *spoeqi*
  design (`envelope.py`).
- **The whole OS in 64 KB.** `build_pactbundle.py` + `build_pactelf.py` emit `./notesync`, a ~34 KB
  **standard Linux ELF** that looks like an ordinary note utility; given the key it regenerates the
  entire CA-OS from its embedded program and serves it to your browser, and in `host`/`join` mode relays
  sealed deltas to a second node — "send the whole OS through the pact," with almost nothing actually sent.

**Honest scope.** The gate/latch/adder *primitives* are genuine CA, verified byte-for-bit; the running
desktop is **ISA-emulated for speed**, not literally computed by colliding gliders (that would be ~10⁸×
too slow). The pact's confidentiality/integrity rest on **AES-256-GCM** (a vetted AEAD) — the CA is the
*key schedule*, not the cipher — and there is **no forward secrecy**; security reduces to seed secrecy.
This is a **teaching instrument and an art/worldbuilding piece**, not a security product or a competitor
to silicon. (Run `make test` for the regression suite that locks in these invariants.)

## Layout

```
main.c       CLI + orchestration
util.c       histogram, sparkline, pattern parsing, byte search
magic.c      type identification + embedded-signature carving
stats.c      statistics, entropy map, self-similarity
structure.c  per-type structural parsers (incl. PE / MP4 / PDF)
scan.c       opcode patterns, signatures, anomalies, grep
disasm.c     x86 / x86-64 length disassembler + linear sweep
attn.c       hand-wired attention head (soft self-attention + induction + soft-attn generation)
gpt.c        n-gram language model: bits/byte, temperature generation, range-coder compression, corpus API
cm.c         context-mixing coder (the .atcm compressor)
prep.c       corpus prep: clean + dedup + quality-filter text (UTF-8 aware), streamed to stdout
content.c    content addressing for atn-ga: MinHash/SimHash signatures + exact/LSH neighbour table (atn --neighbors)
yara.c       subset-YARA parser and matcher
fleet.c      recursive directory scan + aggregate statistics
dump.c       basic report, hex dump, strings
atn.h        shared declarations

atn-ga.py    evolve/route a population of brains over a corpus (run/lightup/mixture/classify/novelty/export) — stdlib only
web/         Django "corpus atlas": browse territories, visualise the routing graph, route live queries
GA.md        the atn-ga manual: design, results, options
```

## Caveats

- The disassembler decodes the standard x86/x86-64 instruction space and was
  validated to reproduce `objdump`'s `.text` instruction boundaries exactly on
  real ELF binaries. It does **not** decode VEX/EVEX (AVX) encodings, which can
  cause a linear sweep through AVX-heavy code to desync locally.
- Under `-P`, a hit marked "at instr boundary" was confirmed by the
  disassembler; an unmarked hit is a coincidental byte match (e.g. a `CD 21`
  inside an immediate or displacement), not an `INT 21h` instruction.
- The signature and YARA scans are indicators, **not** a substitute for a real
  antivirus engine.
- Single-file inspection reads the whole file into memory; `-R` reads up to
  16 MiB per file for its metrics.
