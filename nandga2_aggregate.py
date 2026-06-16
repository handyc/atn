#!/usr/bin/env python3
# nandga2_aggregate.py — did a GENERALISING universal gate emerge? Trust HELD-OUT only.
import glob, json, os, sys
import numpy as np
from collections import Counter
def main():
    d=sys.argv[1] if len(sys.argv)>1 else "alice/nandga-v2/outputs"
    R=[json.load(open(f)) for f in glob.glob(os.path.join(d,"result_*.json"))]
    if not R: print("no results yet"); return
    R.sort(key=lambda r:-r["heldout_acc"])
    ho=[r["heldout_acc"] for r in R]; tr=[r["train_acc"] for r in R]
    print(f"{len(R)} islands. HELD-OUT acc: best {ho[0]*100:.0f}%, median {np.median(ho)*100:.0f}%")
    print(f"            TRAIN acc:    best {max(tr)*100:.0f}%, median {np.median(tr)*100:.0f}%")
    real=[r for r in R if r["heldout_acc"]>=0.95]
    print(f"genomes with >=95% HELD-OUT (a real, generalising universal gate): {len(real)}/{len(R)}")
    print(f"gate types among top-15: {dict(Counter(r['gate'] for r in R[:15]))}")
    print("\ntop 6 (held-out / train):")
    for r in R[:6]: print(f"  {r['gate']:4s}  heldout {r['heldout_acc']*100:3.0f}%  train {r['train_acc']*100:3.0f}%")
    if real:
        b=real[0]
        print(f"\n  -> REAL universal {b['gate']} gate ({b['heldout_acc']*100:.0f}% held-out): the CA substrate")
        print("     is computation-universal by construction (register + this gate = a datapath).")
        print(f"     genome det={b['genome']['det']} fab={b['genome']['fab']}")
    else:
        print("\n  -> NO gate generalises (held-out stays low). HONEST: gate COMPOSITION is the real")
        print("     bottleneck for a CA computer in this substrate — storage (register) works, but a")
        print("     robust composable logic gate does not emerge from the routing fabric. Key open problem.")
if __name__=="__main__": main()
