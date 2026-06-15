#!/usr/bin/env python3
# Merge GA-sweep-v2 results -> class-4 vs LINEAR(class-3) vs random, mean+-std/seed.
import glob, os, sys, json, math, collections
outdir = sys.argv[1] if len(sys.argv) > 1 else "outputs"
by = collections.defaultdict(list)
for f in glob.glob(os.path.join(outdir, "result_*.json")):
    d = json.load(open(f)); by[(d["corpus"], d["mode"])].append(d["fresh_res_acc"])
def ms(xs):
    n=len(xs); m=sum(xs)/n if n else 0
    sd=math.sqrt(sum((x-m)**2 for x in xs)/n) if n>1 else 0
    return m, sd, n
print("=== GA-sweep-v2: reservoir res_acc on FRESH region (mean+-std over seeds) ===")
print(f"{'corpus':<8}{'class4':>16}{'linear(c3)':>16}{'random':>16}   verdict")
for corpus in ["news","code","langs"]:
    c4=by.get((corpus,"class4"),[]); li=by.get((corpus,"linear"),[]); rd=by.get((corpus,"random"),[])
    if not (c4 and li and rd): continue
    m4,s4,_=ms(c4); ml,sl,_=ms(li); mr,sr,_=ms(rd)
    sp=math.sqrt((s4**2+sl**2)/2) or 1e-9; d=(m4-ml)/sp     # class4 vs linear effect size
    v = ("class4 > linear" if m4 > ml + 0.01 else
         "linear >= class4" if ml > m4 + 0.01 else "class4 ~ linear")
    print(f"{corpus:<8}{m4:.3f}+-{s4:.3f}{ml:>9.3f}+-{sl:.3f}{mr:>9.3f}+-{sr:.3f}   {v} (d={d:+.1f})")
print("\nreading: the literature says structured class-3 (linear) rules often win in ReCA.")
print("If class4 ~ linear >> random -> it's 'structured>>random', not 'class-4 is special'.")
print("If class4 > linear -> the class-4 hunch is confirmed head-to-head (novel result).")
