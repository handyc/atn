#!/usr/bin/env python3
# verify_corpus.py — does the glider-trajectory fingerprint actually separate real
# texts? Encode a small labelled multilingual corpus three ways and compare
# leave-one-out 1-NN classification accuracy by language:
#   (P) glider PATH   — resampled normalised COM trajectory (sequence signature)
#   (D) glider DIR-HIST — histogram of the glider's actual movement directions (dynamical)
#   (B) letter-freq BASELINE — plain character histogram (no CA at all)
# Honest test: if the glider features beat chance and rival/explain the baseline, the
# encoder is a real DH feature; if only the baseline works, say so.
import numpy as np, rulehub, target_gen
from mechanism import SHIFT, DIRV
DSH={k:SHIFT[k] for k in DIRV}; DANG={k:np.arctan2(v[0],v[1]) for k,v in DIRV.items()}
def surgery(base,phi):
    o=base.copy()
    for k,s in DSH.items():
        n=int(round(3*max(0,np.cos(DANG[k]-phi))))
        for i,v in enumerate((1,2,3)): o[v<<s]=v if i<n else 0
    return o
BASE=target_gen.newton_lut(-0.10,-0.02,0.52); W=H=90; KPER=6
def chh(ch): return ((ord(ch.lower())%32)/32)*2*np.pi-np.pi
def com(b):
    nz=np.flatnonzero(b)
    if nz.size==0: return None
    ys,xs=np.divmod(nz,W); return (xs.mean(),ys.mean(),nz.size)
def trace(s):
    b=np.zeros((H,W),np.uint8); b[H//2-2:H//2+3,12:17]=np.random.default_rng(1).integers(1,4,(5,5))
    path=[]
    for ch in s[:60]:
        lut=surgery(BASE,chh(ch))
        for _ in range(KPER):
            b=lut[rulehub.hex_key(b.astype(np.int64))].astype(np.uint8); m=com(b)
            if m is None or m[2]>0.14*W*H:
                last=path[-1] if path else (12,H//2); b=np.zeros((H,W),np.uint8)
                r=int(last[1])%H; c=int(last[0])%W; b[max(0,r-2):r+3,max(0,c-2):c+3]=1; m=(last[0],last[1],9)
            path.append((m[0],m[1]))
    return np.array(path)
def feat_path(s):
    p=trace(s)
    if len(p)<4: return np.zeros(64)
    idx=np.linspace(0,len(p)-1,32).astype(int); q=p[idx]; q=q-q[0]
    sc=max(1e-6,np.hypot(*q.T).max()); return (q/sc).ravel()
def feat_dir(s):
    p=trace(s)
    if len(p)<4: return np.zeros(8)
    d=np.diff(p,axis=0); ang=np.arctan2(d[:,1],d[:,0]); h,_=np.histogram(ang,bins=8,range=(-np.pi,np.pi));
    return h/max(1,h.sum())
def feat_lf(s):
    v=np.zeros(27)
    for ch in s.lower():
        o=ord(ch)
        if 97<=o<=122: v[o-97]+=1
        elif ch==' ': v[26]+=1
    return v/max(1,v.sum())
def loo_acc(X,y):
    X=np.array(X); y=np.array(y); n=len(y); ok=0
    for i in range(n):
        d=np.sqrt(((X-X[i])**2).sum(1)); d[i]=1e9; ok+= y[np.argmin(d)]==y[i]
    return ok/n

CORPUS={
 "en":["the quick brown fox jumps over","she sells sea shells by the shore","a journey of a thousand miles","to be or not to be that is","the rain in spain falls mainly","all that glitters is not gold","better late than never they say","knowledge is power and freedom"],
 "fr":["le petit chat dort sur le lit","je pense donc je suis vraiment","la vie est belle et douce ainsi","les feuilles tombent en automne","un bon vin rouge avec du pain","elle chante une chanson triste","nous allons a la plage demain","le temps passe tres vite ici"],
 "de":["der schnelle braune fuchs springt","ich denke also bin ich wirklich","das leben ist schoen und gut","die blaetter fallen im herbst","ein guter wein mit dem brot","sie singt ein trauriges lied","wir gehen morgen zum strand","die zeit vergeht sehr schnell"],
 "es":["el gato pequeno duerme aqui","pienso luego existo de verdad","la vida es bella y dulce asi","las hojas caen en el otono","un buen vino con algo de pan","ella canta una cancion triste","vamos a la playa manana temprano","el tiempo pasa muy rapido aqui"],
 "it":["il piccolo gatto dorme qui","penso dunque sono davvero io","la vita e bella e dolce cosi","le foglie cadono in autunno","un buon vino rosso con il pane","lei canta una canzone triste","andiamo alla spiaggia domani","il tempo passa molto veloce qui"],
}
def main():
    texts=[]; labs=[]
    for lang,arr in CORPUS.items():
        for t in arr: texts.append(t); labs.append(lang)
    print(f"{len(texts)} texts, {len(CORPUS)} languages (chance = {100/len(CORPUS):.0f}%)\n")
    for name,fn in [("glider PATH (sequence signature)",feat_path),
                    ("glider DIR-HIST (dynamical)",feat_dir),
                    ("letter-freq BASELINE (no CA)",feat_lf)]:
        X=[fn(t) for t in texts]; acc=loo_acc(X,labs)
        print(f"  {name:34s}  LOO 1-NN accuracy: {100*acc:.0f}%")
    print("\n-> honest read printed by comparison above.")
if __name__=="__main__": main()
