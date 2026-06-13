"""Load a built atn-ga run (e.g. demo-langs) into the database.

Reuses atn-ga.py's own helpers (_expert_profile, load_index, NeighborTable) so
the distinctive terms / sample passages match exactly what `lightup` prints.

    python manage.py import_run --name demo-langs \
        --dir /abs/path/to/demo-langs --atn /abs/path/to/atn
"""
import importlib.util
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corpus.helpers import guess_label
from corpus.models import Edge, Expert, Passage, Run


def _load_atnga():
    src = os.path.join(settings.REPO_DIR, "atn-ga.py")
    if not os.path.exists(src):
        raise CommandError(f"can't find atn-ga.py at {src}")
    spec = importlib.util.spec_from_file_location("atnga", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Command(BaseCommand):
    help = "Import a built atn-ga run directory into the atlas database."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="demo-langs")
        parser.add_argument("--dir", default=None, help="run output dir (default <repo>/demo-langs)")
        parser.add_argument("--atn", default=None, help="atn binary (default <repo>/atn)")

    def handle(self, *args, **opts):
        run_dir = os.path.abspath(opts["dir"] or os.path.join(settings.REPO_DIR, "demo-langs"))
        atn_path = os.path.abspath(opts["atn"] or os.path.join(settings.REPO_DIR, "atn"))
        genes_path = os.path.join(run_dir, "genes.json")
        if not os.path.exists(genes_path):
            raise CommandError(f"no genes.json in {run_dir} — build a run first")

        mod = _load_atnga()
        meta = json.load(open(genes_path))
        try:
            cfg = json.load(open(os.path.join(run_dir, "config.json")))
        except FileNotFoundError:
            cfg = {}

        # tiling.tsv: expert centroid / lo / hi
        tiling = {}
        tpath = os.path.join(run_dir, "tiling.tsv")
        if os.path.exists(tpath):
            for line in open(tpath).read().splitlines()[1:]:
                f = line.split("\t")
                if len(f) >= 8:
                    tiling[int(f[0])] = (float(f[5]), float(f[6]), float(f[7]))

        # fresh import
        Run.objects.filter(name=opts["name"]).delete()
        run = Run.objects.create(
            name=opts["name"], run_dir=run_dir, atn_path=atn_path,
            corpus_path=cfg.get("corpus", ""), coverage_bpb=meta.get("coverage_bpb", 0.0),
            config_json=json.dumps(cfg, ensure_ascii=False, indent=2),
        )

        chunks = mod.load_index(run_dir)
        nbpath = os.path.join(run_dir, "neighbors.bin")
        nbtable = mod.NeighborTable(nbpath) if (cfg.get("locus") == "content" and os.path.exists(nbpath)) else None
        fd = os.open(os.path.join(run_dir, "territory.txt"), os.O_RDONLY)

        def chunk_ids(gene):
            if nbtable is not None:
                return nbtable.neighbors(gene["start"])[:gene["span"]]
            return list(range(gene["start"], min(gene["start"] + gene["span"], len(chunks))))

        def read_chunk(cid):
            o, l = chunks[cid]
            return os.pread(fd, l, o).decode("utf-8", "ignore").strip()

        survivors = [g for g in meta["genes"] if g.get("n_owned", 0) > 0]
        by_id = {}
        for g in survivors:
            terms, sample = mod._expert_profile(run_dir, g, cfg)
            cen, lo, hi = tiling.get(g["expert"], (g["start"] / max(1, len(chunks)), 0.0, 1.0))
            e = Expert.objects.create(
                run=run, expert_id=g["expert"], brain_path=g["brain"],
                mapbits=g.get("mapbits", 22), orders=",".join(map(str, g.get("orders", [2, 4, 7]))),
                marginal=g.get("marginal", 0.0), n_owned=g.get("n_owned", 0),
                centroid=cen, pos_lo=lo, pos_hi=hi,
                label=guess_label(sample, terms), terms=",".join(terms), sample=sample[:400],
            )
            by_id[g["expert"]] = e
            for cid in chunk_ids(g)[:4]:
                txt = read_chunk(cid)
                if txt:
                    Passage.objects.create(expert=e, text=txt[:320])

        os.close(fd)

        # routing graph edges
        gpath = os.path.join(run_dir, "graph.tsv")
        n_edges = 0
        if os.path.exists(gpath):
            for line in open(gpath).read().splitlines()[1:]:
                f = line.split("\t")
                if len(f) >= 3 and int(f[0]) in by_id and int(f[1]) in by_id:
                    Edge.objects.create(run=run, src=by_id[int(f[0])], dst=by_id[int(f[1])],
                                        weight=int(f[2]))
                    n_edges += 1

        self.stdout.write(self.style.SUCCESS(
            f"imported '{run.name}': {len(survivors)} experts, {n_edges} edges, "
            f"coverage {run.coverage_bpb:.3f} bpb"))
