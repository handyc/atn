# c4lib-v1 — ALICE class-4 rule-library scan

Mass-scan escape-time fractals into **7→1 hex CA class-4 rule LUTs** (4⁷=16384),
across generators (Julia / Newton / Burning Ship / Mandelbrot) and tag each hit
with its **3D von-Neumann survival** and **C6 / D6 symmetric-variant class**. The
throughput-bound job ALICE is good for; the product is a big, diverse, tagged
class-4 rule library reusable by `caca.HexNet` (2D) and `ndca` (3D).

## What it produces
Per array task → `outputs/shard_<id>.u8` (concatenated 16384-byte LUTs) +
`outputs/shard_<id>.tsv` (manifest: family, class2d, activity, c4, class3d,
classC6, classD6, fractal coords). `aggregate.py` merges to `outputs/c4lib.npy`.

## Job size
120 array tasks × 400 candidates ≈ **48,000 rules scanned**; expected ~12–18k
class-4 LUTs kept. Each task ≈ 1–2 min single-core → trivial on `cpu-short`.

## Operator workflow (you run these; this session can't SSH to ALICE)
    cd alice/c4lib-v1
    bash push.sh                 # rsync bundle -> alice:~/atn-alice/c4lib-v1
    ssh alice
      cd ~/atn-alice/c4lib-v1 && sbatch submit.sh && squeue -u $USER
    # when done:
    bash pull.sh                 # rsync outputs back
    python3 aggregate.py outputs # -> outputs/c4lib.npy + stats

If running inside an ALICE Open OnDemand Jupyter session instead, skip push/pull
and just `sbatch submit.sh` in place.

## Invariants honoured (per conduit/alice protocol)
deterministic per task seed · each task writes only its own shard files ·
no network in `run_task.py` (stdlib + numpy only) · pure-data outputs ·
`cd "$SLURM_SUBMIT_DIR"` in submit.sh. Adjust the `module load` lines in
submit.sh if `module avail Python` on ALICE shows different versions.
