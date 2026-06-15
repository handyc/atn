#!/usr/bin/env python3
# saturation.py — does the rule swarm keep discovering NEW behaviour as it grows,
# or just more syntactically-unique copies of the same dynamics? Builds a
# species-accumulation (rarefaction) curve over BEHAVIOURAL signatures and reports
# the marginal rate of new signatures — early vs late. A plateau = behavioural
# saturation (bigger swarm learns nothing new).
import argparse, json, os, glob
import numpy as np

def load(outdir):
    lib = os.path.join(outdir, "library.json")
    if os.path.exists(lib):
        return json.load(open(lib))
    recs = {}
    for f in glob.glob(os.path.join(outdir, "manifest_*.jsonl")):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                r = json.loads(ln); recs[r["hash"]] = r
    return list(recs.values())

def sig(r):
    # behavioural signature: discrete dynamics tags + binned activity/quality
    return (r["family"], r["class3d"], r["glider"], r["symC6"], r["symD6"],
            round(r["c4"], 2), round(r["act"], 2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    recs = load(a.outdir)
    n = len(recs)
    rng = np.random.default_rng(a.seed)
    order = rng.permutation(n)
    sigs = [sig(recs[i]) for i in order]
    print(f"library: {n} syntactically-unique rules (0% exact LUT dup by content-address)")
    # accumulation curve
    seen = set(); curve = []
    checkpoints = sorted(set(int(x) for x in np.unique(
        np.r_[np.linspace(1, n, 30), np.geomspace(1, n, 30)].astype(int)) if 1 <= x <= n))
    ci = 0; distinct = 0
    new_at = []  # (N, distinct)
    for k, s in enumerate(sigs, 1):
        if s not in seen:
            seen.add(s); distinct += 1
        if ci < len(checkpoints) and k == checkpoints[ci]:
            new_at.append((k, distinct)); ci += 1
    total_sig = len(seen)
    print(f"distinct BEHAVIOURAL signatures: {total_sig}  "
          f"({100*total_sig/n:.2f}% of rules are behaviourally distinct; "
          f"{100*(1-total_sig/n):.1f}% are behavioural duplicates of an earlier rule)")
    print(f"\n{'rules sampled':>14}{'distinct behaviours':>22}{'new per 1k rules':>18}")
    prev_k, prev_d = 0, 0
    for k, d in new_at:
        rate = (d - prev_d) / max(1, (k - prev_k)) * 1000
        print(f"{k:>14}{d:>22}{rate:>18.1f}")
        prev_k, prev_d = k, d
    # coverage milestones
    for frac in (0.90, 0.95, 0.99):
        thr = frac * total_sig
        kk = next((k for k, d in new_at if d >= thr), n)
        print(f"  {int(frac*100)}% of all behaviours first seen by ~{kk} rules "
              f"({100*kk/n:.1f}% of the library)")
    # tail rate: new behaviours in the last 10% of the library
    last_k, last_d = new_at[-1]
    mid = next((d for k, d in new_at if k >= n * 0.9), last_d)
    tail_new = last_d - mid
    print(f"\nnew behaviours discovered in the LAST 10% of the library "
          f"({int(n*0.1)} rules): {tail_new}  -> {tail_new/max(1,int(n*0.1))*1000:.2f} per 1k")
    print("\nreading: if the marginal 'new per 1k' rate has collapsed toward ~0, the swarm")
    print("has BEHAVIOURALLY saturated — 100,000x more rules would add syntactic copies,")
    print("not new dynamics.")

if __name__ == "__main__":
    main()
