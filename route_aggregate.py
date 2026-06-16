#!/usr/bin/env python3
# route_aggregate.py — combine ALICE route-v1 results: rank glider-routing recipes
# and characterise what makes routing robust.
import glob, json, os, sys
import numpy as np

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "alice/route-v1/outputs"
    rows = []
    for f in glob.glob(os.path.join(d, "result_*.json")):
        rows += json.load(open(f))
    if not rows:
        print("no results yet"); return
    print(f"{len(rows)} base rules with a routing result\n")
    # "clean routing" = tracks the field well, survives, and actually turns
    clean = [r for r in rows if r["med_err"] < 20 and r["frac"] > 0.6 and r["net_turn"] > 50]
    print(f"CLEAN routers (med_err<20deg, survived>60%, net_turn>50deg): "
          f"{len(clean)}/{len(rows)} ({100*len(clean)/len(rows):.0f}%)")
    me = np.array([r["med_err"] for r in rows])
    print(f"median heading-vs-field error across bases: median {np.median(me):.0f}deg, "
          f"best {me.min():.0f}deg")
    # winning configs among clean routers
    if clean:
        from collections import Counter
        cfg = Counter((r["turn_deg"], r["grad_frac"]) for r in clean)
        print("\nwinning (turn_deg, grad_frac) among clean routers:")
        for (t, g), n in cfg.most_common():
            print(f"  turn {t:3d}deg, gradient over {g} of board: {n}")
        print("\ntop 8 routing recipes (lowest med_err among clean):")
        for r in sorted(clean, key=lambda r: r["med_err"])[:8]:
            print(f"  err {r['med_err']:4.1f}deg  net_turn {r['net_turn']:3.0f}  surv {r['frac']:.2f}  "
                  f"turn{r['turn_deg']}/grad{r['grad_frac']}  cx={r['cx']:+.3f} cy={r['cy']:+.3f} span={r['span']:.3f}")
        # does base zoom (span) or speed proxy correlate with routability?
        sp = np.array([r["span"] for r in clean]); er = np.array([r["med_err"] for r in clean])
        if len(clean) > 10:
            print(f"\n(within clean routers) corr(span, med_err) = {np.corrcoef(sp, er)[0,1]:+.2f}")
    print("\n-> if a sizeable fraction route cleanly, glider routing is robust with the right")
    print("   base+field; the winning configs give the recipe for the waveguide demo.")

if __name__ == "__main__":
    main()
