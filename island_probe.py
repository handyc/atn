#!/usr/bin/env python3
# island_probe.py — why is 4D a re-entrant GROWTH island (growth at 2D,4D; copy at
# 3D,5D,6D)? Hypothesis: a SELECTION effect — growth-regime gliders tend to gain mass
# and, in some dimensions, blow past the bounded-mass cutoff (rejected as "explode"),
# leaving only copy-type translations among survivors. Test, per dimension (vN, K=2):
# the outcome mix (dead/explode/static/translating), and among translating survivors
# the growth% and the mass TREND (growing vs shrinking). If growth-gliders correlate
# with mass-growth and explode more in 3D/5D/6D than 4D, selection explains the island.
import numpy as np

def vn_off(d):
    o=[tuple([0]*d)]
    for ax in range(d):
        for s in (1,-1): t=[0]*d; t[ax]=s; o.append(tuple(t))
    return o
def key_nd(b,offs,K):
    k=np.zeros(b.shape,np.int64)
    for i,off in enumerate(offs):
        sh=b
        for ax,dd in enumerate(off):
            if dd: sh=np.roll(sh,-dd,ax)
        k+=sh.astype(np.int64)*(K**i)
    return k
def rand_lut(K,m,p,rng):
    n=K**m; lut=np.zeros(n,np.uint8); msk=rng.random(n)<p; lut[msk]=rng.integers(1,K,int(msk.sum())); lut[0]=0; return lut
def Fvec(lut,offs,K):
    F=np.zeros(len(offs[0]))
    for i,off in enumerate(offs):
        if i==0: continue
        a=np.mean([lut[v*(K**i)]>0 for v in range(1,K)]); F=F+a*np.array(off,float)
    return F
def trial(lut,offs,K,dim,side,T):
    rng=np.random.default_rng(0); shape=(side,)*dim; b=np.zeros(shape,np.uint8); c=side//2
    sl=tuple(slice(c-1,c+2) for _ in range(dim)); b[sl]=rng.integers(1,K,(3,)*dim)
    coms=[]; mass=[]
    for _ in range(T):
        b=lut[key_nd(b,offs,K)].astype(np.uint8); nz=np.flatnonzero(b); mn=nz.size; mass.append(mn)
        if mn==0: return ("dead",None,None)
        if mn>0.06*b.size: return ("explode",None,None)
        coms.append(np.array(np.unravel_index(nz,shape)).mean(axis=1))
    coms=np.array(coms); h=len(coms)//2; v=(coms[-1]-coms[h])/(len(coms)-h)
    trend=(mass[-1]-mass[h])/max(1,mass[h])
    if np.linalg.norm(v)<0.15: return ("static",None,trend)
    return ("translating",v,trend)

def main():
    print("dimension probe (von Neumann, K=2): outcome mix + survivor regime + mass trend\n")
    print("  dim   explode%  dead%  static%  transl%   among transl: growth%  mean-mass-trend  (growth&grow)%")
    for dim in (2,3,4,5):
        offs=vn_off(dim); m=len(offs); side={2:60,3:26,4:14,5:10,6:8}[dim]; T={2:22,3:18,4:14,5:16,6:12}[dim]
        rng=np.random.default_rng(dim*13+1); N=500
        out={"dead":0,"explode":0,"static":0,"translating":0}; gr=[]; tr=[]; gg=0; ng=0
        for _ in range(N):
            lut=rand_lut(2,m,rng.uniform(0.06,0.5),rng)
            kind,v,trend=trial(lut,offs,2,dim,side,T); out[kind]+=1
            if kind=="translating":
                F=Fvec(lut,offs,2)
                if np.linalg.norm(F)<1e-6: continue
                cosang=np.dot(v,-F)/(np.linalg.norm(v)*np.linalg.norm(F)+1e-12)
                g = cosang>0  # growth = motion within 90deg of -F
                gr.append(g); tr.append(trend); ng+=1
                if g and trend>0.05: gg+=1
        tot=sum(out.values())
        growthpct = 100*np.mean(gr) if gr else float("nan")
        mt = np.mean(tr) if tr else float("nan")
        print(f"  {dim}    {100*out['explode']/tot:6.1f}  {100*out['dead']/tot:5.1f}  "
              f"{100*out['static']/tot:6.1f}  {100*out['translating']/tot:6.1f}     "
              f"{growthpct:6.1f}            {mt:+.2f}          {100*gg/max(1,ng):4.0f}")
    print("\n-> if 4D uniquely lets growth-gliders stay bounded (low explode%, growth survivors")
    print("   with positive mass trend) while 3D/5D/6D reject them, selection explains the island.")

if __name__ == "__main__":
    main()
