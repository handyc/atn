#!/usr/bin/env python3
# aggregate.py — merge ALICE shard outputs into one class-4 rule library + stats.
# Run locally after pull.sh:  python3 aggregate.py outputs/
import glob, os, sys
import numpy as np

LUT7 = 1 << 14

def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "outputs"
    tsvs = sorted(glob.glob(os.path.join(outdir, "shard_*.tsv")))
    luts = []; rows = []; header = None
    for tsv in tsvs:
        sid = os.path.basename(tsv).split("_")[1].split(".")[0]
        lines = open(tsv).read().splitlines()
        if not lines:
            continue
        if header is None: header = lines[0]
        body = lines[1:]
        u8 = os.path.join(outdir, f"shard_{sid}.u8")
        if not body or not os.path.exists(u8):
            continue
        arr = np.fromfile(u8, dtype=np.uint8).reshape(-1, LUT7)
        for i, ln in enumerate(body):
            if i < len(arr):
                luts.append(arr[i]); rows.append(ln.split("\t"))
    if not luts:
        print("no class-4 LUTs found in", outdir); return
    pool = np.stack(luts)
    np.save(os.path.join(outdir, "c4lib.npy"), pool)
    cols = header.split("\t")
    fam = [r[cols.index("family")] for r in rows]
    c3d = np.array([int(r[cols.index("class3d")]) for r in rows])
    cC6 = np.array([int(r[cols.index("classC6")]) for r in rows])
    cD6 = np.array([int(r[cols.index("classD6")]) for r in rows])
    import collections
    print(f"=== class-4 rule library: {len(pool)} LUTs from {len(tsvs)} shards ===")
    print("saved:", os.path.join(outdir, "c4lib.npy"), f"({pool.nbytes/1e6:.1f} MB)")
    print("by family:", dict(collections.Counter(fam)))
    print(f"survive as 3D class-4: {(c3d==4).mean()*100:.1f}%   "
          f"stay class-4 under C6: {(cC6==4).mean()*100:.1f}%   D6: {(cD6==4).mean()*100:.1f}%")
    print("hint: load with np.load('c4lib.npy'); each row is a 16384-byte 7->1 LUT, "
          "usable directly by caca.HexNet (and as a 3D rule via ndca).")

if __name__ == "__main__":
    main()
