#!/usr/bin/env python3
# alice_figures.py — consolidation figures from the ALICE result sets, into dissemination/.
#   F6  universality: (A) median heading error vs K per 2D lattice; (B) growth% vs dimension (the 4D island)
#   F7  speed law: measured speed vs derived drift speed, four families, R^2
#   F8  collision gates: XOR & AND gate fidelity over (impact dy, timing px) — recomputed for the top bases
import glob, json, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rulehub

OUT = "dissemination"; os.makedirs(OUT, exist_ok=True)
def cdiff(a, b): return abs(np.angle(np.exp(1j * (a - b))))

# ---------- load gen-v1/2/3/4 → per (substrate,K): growth%, median err, dim ----------
def load_gen():
    agg = {}
    for d in ("alice/gen-v1/outputs", "alice/gen-v2/outputs", "alice/gen-v3/outputs", "alice/gen-v4/outputs"):
        for f in glob.glob(os.path.join(d, "result_*.json")):
            r = json.load(open(f)); key = (r["substrate"], r["K"])
            a = agg.setdefault(key, {"dim": r["dim"], "p2": [], "e3": []})
            if r["dim"] == 2: a["p2"] += r["pairs"]
            else: a["e3"] += r["pairs"]
    out = {}
    for (sub, K), a in agg.items():
        if a["dim"] == 2:
            if len(a["p2"]) < 30: continue
            m = np.radians([p[0] for p in a["p2"]]); p = np.radians([p[1] for p in a["p2"]])
            err = np.degrees([cdiff(m[i], p[i]) for i in range(len(m))])
            errc = np.degrees([cdiff(m[i], p[i] + np.pi) for i in range(len(m))])
            out[(sub, K)] = dict(dim=2, n=len(m), mederr=float(np.median(err)),
                                 growth=float(np.mean(err < errc)))
        else:
            if len(a["e3"]) < 30: continue
            e = np.array(a["e3"])
            out[(sub, K)] = dict(dim=a["dim"], n=len(e), mederr=float(np.median(e)),
                                 growth=float(np.mean(e < 90)))
    return out

def fig6(gen):
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(10, 4.2))
    # A: median err vs K, one line per 2D lattice
    lat = {"sq-vn": ("square von Neumann", "#d62728"), "sq-moore": ("square Moore", "#2ca02c"),
           "hex": ("hexagonal", "#1f77b4")}
    for sub, (lab, col) in lat.items():
        ks = sorted(K for (s, K) in gen if s == sub and gen[(s, K)]["dim"] == 2)
        if not ks: continue
        axA.plot(ks, [gen[(sub, K)]["mederr"] for K in ks], "o-", color=col, label=lab)
    axA.set_xlabel("states K"); axA.set_ylabel("median heading error (deg)")
    axA.set_title("A · law is exact at low K, degrades with K (2D lattices)", fontsize=9)
    axA.legend(fontsize=8); axA.set_ylim(-2, 60); axA.grid(alpha=0.2)
    # B: growth% vs dimension (von Neumann K=2)
    dims = [2, 3, 4, 5, 6]; gr = []
    for d in dims:
        key = (f"vn{d}", 2)
        # vn3==cube-vn in gen-v1; accept either label
        if key not in gen and d == 3 and ("cube-vn", 2) in gen: key = ("cube-vn", 2)
        gr.append(gen[key]["growth"] * 100 if key in gen else np.nan)
    axB.plot(dims, gr, "s-", color="#9467bd", ms=8)
    axB.axhline(50, color="#888", ls=":", lw=1)
    for d, g in zip(dims, gr):
        if not np.isnan(g): axB.annotate(f"{g:.0f}%", (d, g), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    axB.set_xlabel("lattice dimension (von Neumann, K=2)"); axB.set_ylabel("% gliders in growth regime")
    axB.set_title("B · growth↔copy is non-monotonic: a 4D growth island", fontsize=9)
    axB.set_ylim(-5, 110); axB.set_xticks(dims); axB.grid(alpha=0.2)
    fig.suptitle("F6. Universality of the direction law across lattice, K, and dimension", fontsize=10)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig6_universality.png", dpi=130); plt.close()
    print("F6 done:", {k: (round(v["mederr"]), round(v["growth"]*100)) for k, v in sorted(gen.items())})

def fig7():
    fam = {}
    for f in glob.glob("alice/speed-v1/outputs/result_*.json"):
        r = json.load(open(f)); fam.setdefault(r["family"], []).extend(r["recs"])
    cols = {"newton": "#d62728", "julia": "#1f77b4", "mandelbrot": "#2ca02c", "burning": "#9467bd"}
    plt.figure(figsize=(5.4, 5))
    alls, alld = [], []
    for f, recs in fam.items():
        sp = np.array([x["speed"] for x in recs]); dr = np.array([x["drift"] for x in recs])
        c = np.corrcoef(dr, sp)[0, 1]
        plt.scatter(dr, sp, s=7, alpha=0.3, color=cols.get(f, "#888"), label=f"{f} (R²={c*c:.2f})")
        alls += list(sp); alld += list(dr)
    alls, alld = np.array(alls), np.array(alld); C = np.corrcoef(alld, alls)[0, 1]
    A = np.polyfit(alld, alls, 1); xs = np.array([alld.min(), alld.max()])
    plt.plot(xs, np.polyval(A, xs), "k--", lw=1.2, label=f"all: R²={C*C:.2f}")
    plt.xlabel("derived drift speed  |F|/(a_self+Σa_p)"); plt.ylabel("measured glider speed (cells/tick)")
    plt.title("F7. Speed law: the kernel drift speed predicts glider speed", fontsize=9)
    plt.legend(fontsize=8); plt.tight_layout(); plt.savefig(f"{OUT}/fig7_speed.png", dpi=130); plt.close()
    print(f"F7 done: {len(alls)} gliders, overall R²={C*C:.2f}")

# ---------- F8: recompute gate fidelity grid for the top XOR and AND bases ----------
SHIFT = {"self": 12, "nw": 10, "ne": 8, "r": 6, "se": 4, "sw": 2, "l": 0}
_DIR = {"nw": (-1, -0.5), "ne": (-1, 0.5), "r": (0, 1.0), "se": (1, 0.5), "sw": (1, -0.5), "l": (0, -1.0)}
DIRV = {k: np.array(v) / np.hypot(*v) for k, v in _DIR.items()}
DANG = {k: np.arctan2(v[0], v[1]) for k, v in DIRV.items()}; DSH = {k: SHIFT[k] for k in DIRV}
def nlut(cx, cy, span):
    side = 128; st = span / side; ox = cx - st * side * .5; oy = cy - st * side * .5
    gx, gy = np.meshgrid(ox + np.arange(side) * st, oy + np.arange(side) * st)
    return rulehub._posterise(rulehub._newton(gx, gy, 160), 160)
def rfor(base, th):
    phi = np.radians(th) - np.pi; o = base.copy()
    for k, s in DSH.items():
        n = int(round(3 * max(0, np.cos(DANG[k] - phi))))
        for i, v in enumerate((1, 2, 3)): o[v << s] = v if i < n else 0
    return o
def runmass(stack, reg, seeds, H, ticks, sv):
    rng = np.random.default_rng(sv); b = np.zeros((H, H), np.uint8)
    for (r, c) in seeds: b[r-2:r+3, c-2:c+3] = rng.integers(1, 4, (5, 5))
    for _ in range(ticks):
        b = stack[reg, rulehub.hex_key(b.astype(np.int64))].astype(np.uint8)
        if (b > 0).sum() > 0.18 * H * H: return None
    return int((b > 0).sum())
def gate_grid(cx, cy, span, kind, H=120, ticks=110):
    base = nlut(cx, cy, span); base = base.copy(); base[0] = 0
    stack = np.stack([rfor(base, 0), rfor(base, 180)])
    cols = np.arange(H)[None, :].repeat(H, 0); reg = (cols >= H // 2).astype(int)
    cy0, D = H // 2, 32; dys = list(range(-8, 9, 2)); pxs = [-4, -2, 0, 2, 4]
    G = np.full((len(dys), len(pxs)), np.nan)
    for i, dy in enumerate(dys):
        for j, px in enumerate(pxs):
            hit = 0; ok = 0
            for sv in (1, 2, 3):
                mL = runmass(stack, reg, [(cy0, H//2-D)], H, ticks, sv)
                mR = runmass(stack, reg, [(cy0+dy, H//2+D+px)], H, ticks, sv+11)
                mB = runmass(stack, reg, [(cy0, H//2-D), (cy0+dy, H//2+D+px)], H, ticks, sv+23)
                if None in (mL, mR, mB) or mL < 5 or mR < 5: continue
                ok += 1
                if kind == "XOR" and mB < 0.2*(mL+mR): hit += 1
                if kind == "AND" and mB > 1.6*(mL+mR): hit += 1
            G[i, j] = hit/ok if ok else np.nan
    return G, dys, pxs
def best_gate_coords():
    rows = []
    for f in glob.glob("alice/collide-v3/outputs/result_*.json"):
        rows += json.load(open(f))
    bx = max(rows, key=lambda r: r["xor_region"])
    ba = max(rows, key=lambda r: r["and_region"])
    return ((bx["cx"], bx["cy"], bx["span"], "XOR", "XOR / annihilation gate"),
            (ba["cx"], ba["cy"], ba["span"], "AND", "AND / product gate"))

def fig8():
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.4))
    for ax, (cx, cy, span, kind, title) in zip(axes, best_gate_coords()):
        G, dys, pxs = gate_grid(cx, cy, span, kind)
        im = ax.imshow(G, cmap="viridis", vmin=0, vmax=1, aspect="auto", origin="lower",
                       extent=[min(pxs)-1, max(pxs)+1, min(dys)-1, max(dys)+1])
        ax.set_xlabel("timing / phase offset px"); ax.set_ylabel("impact parameter dy")
        ax.set_title(f"{title}\ncx={cx:.4f} cy={cy:.4f} span={span:.4f}", fontsize=8.5)
        fig.colorbar(im, ax=ax, shrink=0.85, label="gate fidelity (3 seeds)")
    fig.suptitle("F8. Robust glider-collision gates over impact parameter × timing", fontsize=10)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig8_gates.png", dpi=130); plt.close()
    print("F8 done")

def main():
    gen = load_gen(); fig6(gen); fig7(); fig8()
    print("consolidation figures written to dissemination/: fig6, fig7, fig8")

if __name__ == "__main__":
    main()
