#!/usr/bin/env python3
# flipflopga_aggregate.py — how many islands evolved a clean, rewritable CA flip-flop?
import glob, json, os, sys
import numpy as np
def clean(st):  # heldout [(a1,b1),(a2,b2),(a3,b3)]: set->A, reset->B, set->A
    if not st: return False
    (a1,b1),(a2,b2),(a3,b3)=st
    return a1>3*max(1,b1) and b2>3*max(1,a2) and a3>3*max(1,b3)
def main():
    d=sys.argv[1] if len(sys.argv)>1 else "alice/flipflopga-v1/outputs"
    R=[json.load(open(f)) for f in glob.glob(os.path.join(d,"result_*.json"))]
    if not R: print("no results yet"); return
    R.sort(key=lambda r:-r["fitness"])
    nclean=sum(1 for r in R if clean(r.get("heldout_states")))
    print(f"{len(R)} islands. best fitness {R[0]['fitness']:.3f}, median {np.median([r['fitness'] for r in R]):.3f}")
    print(f"CLEAN flippable flip-flops on the HELD-OUT seed (set->A, reset->B, set->A, 3x dominance): {nclean}/{len(R)}")
    print("\ntop 6 (held-out [set,reset,set] (mA,mB)):")
    for r in R[:6]:
        g=r["genome"]; print(f"  fit {r['fitness']:.2f}  psize={g['psize']} pt={g['pticks']}  heldout={r.get('heldout_states')}")
    b=R[0]
    print(f"\nBEST genome: layerA={[round(x,3) for x in b['genome']['A']]} layerB={[round(x,3) for x in b['genome']['B']]} "
          f"psize={b['genome']['psize']} pticks={b['genome']['pticks']}")
    if nclean>0:
        print(f"\n  -> {nclean} CA networks store 1 bit of REWRITABLE memory (a working flip-flop),")
        print("     verified on a held-out seed. Designed digital memory works where the evolved")
        print("     analog reservoir did not. Next: chain flip-flops -> a multi-bit register.")
    else:
        print("\n  -> none clean on held-out; best partial latches above (report honestly).")
if __name__=="__main__": main()
