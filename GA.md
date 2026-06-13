# atn-ga — an evolved mixture of brains that tiles a large corpus

`atn-ga.py` grows a **population of atn brains**, each trained on a region of a
much larger corpus, and uses a genetic algorithm to search over *where each
brain sits* so that — used together as a mixture of experts — they compress
held-out text as well as possible. The result is a routable network: any query
"lights up" the brain whose territory it falls in.

This is the scaling story for atn. A single brain saturates on a big, diverse
corpus; a *population* of cheap brains can cover one of any size, because the GA
evolves the **partition** (which expert owns which region), not the weights, and
only the addressed slices are ever read. Point it at 25 MB of news today or a
Wikipedia / Library-of-Congress dump later — the machinery is identical.

## The idea in atn terms

| Concept | Realized as |
|---|---|
| an expert / node | one atn brain (`--train`, counts not gradients — trains in ~ms) |
| a gene | `(start_chunk, span, map_bits)` — the brain's region + capacity |
| fitness | **coverage**: how much a brain lowers the population's held-out bits/byte (its *marginal* contribution, via `--score`) |
| selection | steady-state: keep useful experts, replace the redundant ~0-marginal ones with children of survivors |
| the graph | per held-out line, `owner = argmin bpb`, `fallback = 2nd best` → directed edges |
| "lighting up" | brains are files; only the winning expert is loaded from disk at query time |

**Why coverage fitness needs no separate dedup penalty:** a brain that merely
duplicates a sibling's territory rarely wins the per-line argmin, so its marginal
value is ~0 and it is selected out. Redundancy is punished for free.

**Why steady-state:** coverage is a property of the whole *set*. Full-population
churn keeps destroying good tilings. Replacing only the worst (≈0-marginal)
experts each generation means the population can only ratchet down — and it
retrains far fewer brains per generation (survivors' brains are cached on disk by
gene signature).

## Validated result (5-language corpus)

A 4.7 MB corpus was built by concatenating five Project Gutenberg books into
contiguous regions — English (Austen), Spanish (Quijote), French (Proust),
German (Grimm), Italian (Dante) — so that *position correlates with content*.
24 brains, 14 generations, ~0.3 MB per brain:

```
python3 atn-ga.py run --corpus corpus_multi.txt --out run \
    --pop 24 --gens 14 --span-mb 0.3 --replace-frac 0.3
```

- **Coverage dropped monotonically** 2.83 → **2.72 bpb** (finalized at the best).
- **Beats a single brain** trained on the whole corpus: 3.11 → 2.72 bpb (~13%).
- **Experts self-organized by language with no labels** — purely from coverage
  pressure. Brains at locus 0.0–0.14 cover English, 0.17–0.36 Spanish, 0.68
  French, 0.84–0.90 Italian; each owns held-out lines from its own region.
- **Routing works:** an English query lights up an English-region expert, a
  Spanish query a Spanish one, a French query the French one. The fallback graph
  wires same-language neighbors (French→French, Spanish→Spanish, …).

(German, a narrow 6% region, got absorbed by neighbors — expected when the per-
brain span is wider than the region. Shrinking `--span-mb` recovers it.)

## Scaling up: 100 MB of real Wikipedia (enwik8)

The same loop, pointed at enwik8 (the standard 100 MB Wikipedia benchmark) —
48 brains, 16 generations:

```
# positional (contiguous loci)
python3 atn-ga.py run --corpus enwik8 --out wiki --pop 48 --gens 16 \
    --span-mb 0.6 --eval-frac 0.01
# content loci at document granularity (LSH index, topical signature)
python3 atn-ga.py run --corpus enwik8 --out wikic --pop 48 --gens 12 \
    --locus content --chunk-kb 4 --df-max 0.2 --span-mb 0.6 --eval-frac 0.01
python3 atn-ga.py mixture --out wikic
```

- **It scales:** 100 MB (20× the toy corpus) indexed and evolved in **3.5 min**,
  peak **300 MB RAM** — only the addressed slices are ever read.
- **The soft mixture wins big at scale:** best single expert 3.12 bpb → online
  fixed-share mixture **2.44 bpb** (−22%), which here even **beats the hindsight
  per-line oracle (2.68)** — real Wikipedia lines benefit from blending different
  experts *within* a line, which one-expert-per-line routing can't capture.
- **Positional evolution stalls on dump-ordered text.** With contiguous loci,
  coverage did *not* improve over generations — the best tiling was generation 1's
  uniform spread (2.78 bpb) and evolution drifted slightly worse. enwik8 is
  articles in **dump order** (not topically sorted), so a contiguous region is an
  unrelated grab-bag: there is no coherent territory for the GA to discover, and a
  uniform spread is already near-optimal. Same wall the news corpus hit.
- **Document-granularity content loci unstall it (LSH).** With `--locus content
  --chunk-kb 4` (≈document-sized chunks, 22,808 of them, indexed by **LSH** since
  brute-force O(n²) would be 520M comparisons) the GA *does* improve generation
  over generation — 2.80 → 2.78 → **2.76 bpb**, beating the positional best.
  Experts now evolve toward topical clusters gathered by word-MinHash regardless
  of position. The margin over positional is small (~0.4%) because enwik8's
  per-chunk topical signal is genuinely weak (topical-word Jaccard of LSH
  neighbors ≈ 2.3× random) — topic is a far subtler signal than language. But the
  mechanism is proven and scales: content addressing is what gives the
  evolutionary search traction on unsorted data. Its mixture reaches **2.45 bpb**
  (20% under the best single brain, again beating the hindsight oracle 2.70).

The takeaway: the evolutionary search pays off when position correlates with
content (languages, topics, sorted/sharded data); when it doesn't, the *mixture*
of even a uniformly-spread population is still a large, deployable win over any
single brain.

## Usage

```
# evolve a population over any corpus (one document/article per line)
python3 atn-ga.py run --corpus CORPUS.txt --out RUNDIR [options]

# route a query against the evolved population (which expert lights up?)
python3 atn-ga.py lightup --out RUNDIR "some query text"

# soft online mixture of experts vs single brain / hindsight oracle
python3 atn-ga.py mixture --out RUNDIR
```

`run` options (all have sensible defaults):

| flag | default | meaning |
|---|---|---|
| `--pop` | 32 | population size |
| `--gens` | 15 | generations |
| `--span-mb` | 0.5 | target training bytes per brain |
| `--span-chunks` | 8 | initial span (in chunks) of each gene |
| `--locus` | positional | `positional` (contiguous region) or `content` (gather MinHash-similar chunks) |
| `--chunk-kb` | (derived) | chunk size in KB; set small (e.g. 4) for document-granularity content loci |
| `--df-max` | 0.5 | content: drop words in >this fraction of chunks (sharpens the topical signature) |
| `--eval-frac` | 0.05 | fraction of lines held out for scoring |
| `--replace-frac` | 0.3 | worst fraction replaced each generation |
| `--elite` | 4 | (legacy; steady-state keeps survivors) |
| `--jitter` | 3 | locus mutation range (chunks) |
| `--mapbits` | 22 | initial `--map-bits` per brain |
| `--seed` | 1 | RNG seed (runs are fully reproducible) |
| `--jobs` | cores−1 | parallel train/score workers |
| `--atn` | `./atn` | path to the atn binary |

## What `RUNDIR/` contains

```
territory.txt   the trainable text (eval lines removed)
index.tsv       chunk_id <tab> byte_off <tab> byte_len   (addressable slices)
eval.txt        held-out lines used to measure coverage
eval_pos.tsv    each eval line's fractional position (for the tiling map)
brains/         cached brains, named by gene signature (reused across gens)
history.tsv     gen <tab> coverage_bpb <tab> best_marginal <tab> n_owners
genes.json      final population: genes, marginals, coverage
tiling.tsv      which region each surviving expert owns (centroid, range)
graph.tsv       routing graph: owner -> fallback edges with weights
graph.dot       same graph as Graphviz (dot -Tpng graph.dot -o graph.png)
```

## Honest limits & next steps

- atn's n-gram orders `{2,4,7}` are compile-time, so the gene varies the *locus*
  and `--map-bits`, not the model internals. The interesting search — *where*
  each expert sits — is exactly the locus search, so this is not a real
  constraint, but richer genes would need a runtime order flag.
- **Content loci (`--locus content`, implemented).** A positional gene is a
  contiguous byte region — fine when nearby text is related (a sorted/sharded
  corpus), useless when it isn't. A content gene instead names a *seed chunk* and
  gathers its `span` nearest chunks by **word-level MinHash** similarity (shared
  vocabulary), so an expert specializes topically regardless of position. Note
  the signature is over single words, not phrase shingles: shingles catch
  near-duplicates, words catch topic/language. Validated by shuffling the
  5-language corpus at block level so contiguous regions become mixed-language:
  positional coverage degraded to 2.74 bpb, while content **recovered to 2.69** —
  better even than positional on the *unshuffled* corpus (2.72), because it builds
  pure same-language training sets (top-8 neighbors are 90% same-language) instead
  of regions that straddle boundaries. Content mode auto-selects its index:
  exact brute-force for ≤2500 chunks, **banded MinHash LSH** beyond (validated at
  22,808 chunks). The signature uses **document-frequency filtering** (`--df-max`):
  dropping corpus-universal words (stopwords/markup) sharpens topic discrimination
  in mono-lingual data, while keeping enough to preserve language discrimination.
  Granularity matters — coarse chunks are multi-topic grab-bags whose signatures
  blur (enwik8 at 78 KB: content 2.82 ≥ positional 2.78), while document-sized
  chunks (`--chunk-kb 4`) let the GA find topical territory (enwik8: 2.76 <
  positional 2.78). Content addressing is a *document-granularity* tool.
- **Soft mixture (`mixture` command, implemented).** Coverage uses a hard
  per-line argmin. The deployable router can't peek at the answer, so `mixture`
  runs an **online fixed-share** predictor over the eval stream: each byte is
  predicted as a weighted blend of all experts (weights ∝ recent per-byte
  accuracy via atn's new `--score-bytes`), with a small `alpha` leaked back to
  uniform each step so the weights can *switch* experts as the stream crosses
  regions. On the 5-language run it scored **2.62 bpb with no hindsight** —
  beating the best single expert (3.39, by 23%) and coming within 0.02 of the
  hindsight oracle (2.60). Plain Bayesian mixing (alpha=0) gets stuck at 3.82;
  the fixed-share leak is what lets it track. Line-level mixing can't do this —
  line-probabilities are too peaked for a second expert to matter, so the gain
  has to come per byte.
- Scaling up: the corpus is never resident — a gene addresses a slice, we stream
  just that slice to train one brain plus a fixed held-out sample. The same loop
  runs on Wikipedia or larger; only `--span-mb`, `--pop`, and the chunk size grow.
