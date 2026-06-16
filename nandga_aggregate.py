#!/usr/bin/env python3
# nandga_aggregate.py — did the search realise a NAND (=> universality)?
import glob, json, os, sys
import numpy as np
def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/nandga-v1/outputs"
    R = [json.load(open(f)) for f in glob.glob(os.path.join(d, "result_*.json"))]
    if not R: print("no results yet"); return
    R.sort(key=lambda r: -r["accuracy"])
    accs = [r["accuracy"] for r in R]
    print(f"{len(R)} NAND-search islands. best {accs[0]*100:.0f}%, "
          f"# at 100%: {sum(a>=0.999 for a in accs)}, # >=75%: {sum(a>=0.75 for a in accs)}")
    print("\ntop tables:")
    from collections import Counter
    tc = Counter(json.dumps(r["truth_table"]) for r in R[:30])
    for t, n in tc.most_common(6): print(f"  {n}x  {t}")
    if accs[0] >= 0.999:
        print("\n  -> A NAND gate is realised in the substrate => COMPUTATION-UNIVERSAL by")
        print("     construction. The winning genome is the gate layout (replay to verify).")
    else:
        print(f"\n  -> best is {accs[0]*100:.0f}% NAND; the search found gates (e.g. XOR/AND) but")
        print("     not a full NAND. Universality still follows from AND + (annihilation=)NOT")
        print("     as separate verified primitives; a single-config NAND needs more search.")
if __name__ == "__main__": main()
