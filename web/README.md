# atn corpus atlas — a web frontend for a built population

A small Django app that turns a built atn-ga run (e.g. `demo-langs`) into an
explorable website: browse the territories the GA carved out, see each expert's
distinctive vocabulary and sample passages, visualise the routing graph, and
**route your own text live** (it shells out to the `atn` binary, exactly like
the `lightup` command).

It's a *window* onto the population: the n-gram brains stay as files under the
run directory; SQLite stores the structure/metadata; live queries call `atn`.

## Run it

```sh
# 1. build a population first (from the repo root)
./demo-languages.sh                 # or ./demo-news.sh

# 2. set up the site
cd web
pip install -r requirements.txt     # Django (the core tool itself needs no deps)
python manage.py migrate
python manage.py import_run --name demo-langs       # loads ../demo-langs

# 3. serve
python manage.py runserver
# open http://127.0.0.1:8000/
```

`import_run` re-reads the run's artifacts (`genes.json`, `tiling.tsv`,
`graph.tsv`, `neighbors.bin`, `index.tsv`, `territory.txt`) and reuses
`atn-ga.py`'s own helpers so the distinctive terms / passages match `lightup`.
Re-run it any time you rebuild; pass `--dir`/`--atn`/`--name` to point elsewhere.

### Portable export (decoupled from Django)

The tool can also emit the model-shaped data as framework-agnostic files, so a
built population can be shipped and loaded into *any* downstream project later:

```sh
# from the repo root — writes run.csv / experts.csv / passages.csv / edges.csv
# and a self-contained atlas.db (tables: run, expert, passage, edge)
python3 atn-ga.py export --out demo-langs --format both
```

Load that SQLite straight into this app (the structured data comes from the db;
`--dir`/`--atn` just say where the brains + binary live for live scoring):

```sh
cd web
python manage.py import_run --from-db ../demo-langs/atlas.db \
    --dir ../demo-langs --atn ../atn --name demo-langs
```

The CSVs are equally usable from pandas, a DB browser, or a bigger Django
project's own loader — nothing about the export depends on this app.

## Pages

- **Atlas** (`/`) — every surviving expert as a card (guessed language label,
  distinctive vocabulary, a sample line).
- **Territory** (`/expert/<id>/`) — one expert in detail: terms, sample passages,
  related experts from the routing graph.
- **Live query** (`/query/`) — type text; every expert scores its surprisal
  (bits/byte) and the least-surprised one lights up. Real `atn` brains, live.
- **Graph** (`/graph/`) — the routing graph (vis-network); nodes sized by
  ownership, coloured by language; click to open a territory.
- **Admin** (`/admin/`) — raw CRUD over Runs / Experts / Edges.

## Notes / limitations

- The language **label** is a coarse function-word guess for display only — the
  territory's actual terms and passages are the ground truth.
- Closely-related languages (Dutch/English, Spanish/Italian) can route to each
  other: a byte n-gram model keys on surface form, and they share a lot of it.
- Built for local/dev use (`DEBUG=True`, SQLite). Not hardened for deployment.
