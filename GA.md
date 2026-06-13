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

## Usage

```
# evolve a population over any corpus (one document/article per line)
python3 atn-ga.py run --corpus CORPUS.txt --out RUNDIR [options]

# route a query against the evolved population (which expert lights up?)
python3 atn-ga.py lightup --out RUNDIR "some query text"
```

`run` options (all have sensible defaults):

| flag | default | meaning |
|---|---|---|
| `--pop` | 32 | population size |
| `--gens` | 15 | generations |
| `--span-mb` | 0.5 | target training bytes per brain |
| `--span-chunks` | 8 | initial span (in chunks) of each gene |
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
- Loci are **contiguous** byte regions. That suits data where nearby text is
  related (a sorted/sharded corpus). For unsorted data, a *content* locus (seed
  doc → gather similar chunks via the MinHash in `prep.c`) would let experts
  specialize topically regardless of position — a natural next gene type.
- Coverage uses per-line argmin (a hard MoE). A soft mixture (interpolate the
  top-k experts) would lower bpb further and is a drop-in change to `evaluate`.
- Scaling up: the corpus is never resident — a gene addresses a slice, we stream
  just that slice to train one brain plus a fixed held-out sample. The same loop
  runs on Wikipedia or larger; only `--span-mb`, `--pop`, and the chunk size grow.
