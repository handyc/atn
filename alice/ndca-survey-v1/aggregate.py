#!/usr/bin/env python3
# Merge survey shards -> structured class-4 yield by dimension and family.
import glob, os, sys, collections
outdir = sys.argv[1] if len(sys.argv) > 1 else "outputs"
tot = collections.Counter(); c4 = collections.Counter()
totN = collections.Counter(); c4N = collections.Counter(); n = 0
for tsv in sorted(glob.glob(os.path.join(outdir, "shard_*.tsv"))):
    for ln in open(tsv).read().splitlines()[1:]:
        N, fam, cls, act = ln.split("\t"); n += 1
        tot[(N, fam)] += 1; totN[N] += 1
        if cls == "4": c4[(N, fam)] += 1; c4N[N] += 1
print(f"=== structured (fractal) class-4 yield: {n} rules classified ===")
print(f"{'N':>2} {'overall %c4':>11}   per-family %c4")
for N in sorted(totN, key=int):
    fam_str = "  ".join(f"{fam.split('|')[0]}={100*c4[(N,fam)]/tot[(N,fam)]:.0f}%"
                        for (NN, fam) in sorted(tot) if NN == N)
    print(f"{N:>2} {100*c4N[N]/totN[N]:>10.1f}%   {fam_str}")
print("\nreading: structured-search class-4 yield vs lattice dimension N (von Neumann, "
      "m=2N+1). Compare to RANDOM rules (~0% at N>=2) to see the Mandelbrot/Julia walk's value.")
