#!/usr/bin/env python3
# cell10net.py — a graph reservoir of cell10 boards: the original 7->1 class-4
# rule (from the mandelhunt pool) with THREE routable extra-input ports per cell,
# wired across the network. This is the user's cell10 idea applied to the
# reservoir: each node's 3 ports route to another node's board, itself, the input
# signal, or off — information flows between boards AT THE CELL LEVEL (vs caca's
# coarse masked-XOR board coupling).
#
# Rule family (efficient, faithful to "7->1 rule + 3 inputs"): the cell10 output
# is the base 7->1 class-4 lookup ADDITIVELY MODULATED by the routed ports:
#     out = (rule7[hexkey] + w * (p1 + p2 + p3)) mod 4
# w=0 recovers pure 7->1; w>=1 lets the ports steer the class-4 substrate. (A
# full arbitrary 4^10 LUT is a superset; this restricted family keeps it fast and
# is enough to test whether cell-level inter-board routing helps at all.)

import argparse, numpy as np
import caca, cell10

SRC = ["off", "self", "input", "node"]   # port source kinds

class HexNet10:
    def __init__(self, gene, pool7, seed=0):
        rng = np.random.default_rng(seed)
        self.S = gene["side"]; self.ticks = gene["ticks"]; self.w = gene.get("port_w", 1)
        ids = gene["lut_ids"]; self.N = len(ids)
        self.rules = pool7[np.array(ids)].copy()           # (N,16384) 7->1 LUTs
        self.boards = np.zeros((self.N, self.S, self.S), dtype=np.uint8)
        cells = self.S * self.S
        # routes[i] = list of up to 3 (kind, arg) for node i's ports
        self.routes = gene["routes"]
        decay = gene.get("decay", 0.0)
        self.dmask = [(rng.random(cells) < decay) if decay > 0 else None for _ in range(self.N)]
        reps = gene.get("reps", 12)
        flat = rng.permutation(cells)[:4 * reps]
        self.drive = [flat[k * reps:(k + 1) * reps] for k in range(4)]
        self.rcells = min(gene.get("rcells", 64), cells)
        self.rsel = np.array([rng.permutation(cells)[:self.rcells] for _ in range(self.N)])
        self.dim = self.N * self.rcells * 4

    def reset(self):
        self.boards[:] = 0

    def _port(self, prev, kind, arg, inp_grid):
        if kind == "self":  return prev[arg]          # arg = own index
        if kind == "input": return inp_grid
        if kind == "node":  return prev[arg]
        return None                                    # off

    def feed(self, byte):
        cells = self.S * self.S
        inp_val = (byte & 3)
        inp_grid = np.full((self.S, self.S), inp_val, dtype=np.int64)
        # drive node 0 with the byte's 4 base-4 digits
        flat = self.boards.reshape(self.N, cells)
        for k in range(4):
            flat[0, self.drive[k]] = (byte >> (2 * k)) & 3
        for _ in range(self.ticks):
            prev = self.boards.copy()
            newb = np.empty_like(self.boards)
            for i in range(self.N):
                key = cell10._hex_neigh(prev[i].astype(np.int64))   # 7->1 base key
                out7 = self.rules[i][key].astype(np.int64)
                psum = np.zeros((self.S, self.S), dtype=np.int64)
                for (kind, arg) in self.routes[i]:
                    g = self._port(prev, kind, arg, inp_grid)
                    if g is not None: psum = psum + g
                newb[i] = ((out7 + self.w * psum) & 3).astype(np.uint8)
            self.boards = newb
            for i in range(self.N):
                if self.dmask[i] is not None:
                    self.boards[i].reshape(cells)[self.dmask[i]] = 0
        # readout: one-hot sampled cells
        flat = self.boards.reshape(self.N, cells)
        feats = np.zeros((self.N, self.rcells, 4), dtype=np.float32)
        for i in range(self.N):
            feats[i, np.arange(self.rcells), flat[i, self.rsel[i]]] = 1.0
        return feats.reshape(-1)

    def run(self, data, warmup=0):
        self.reset()
        F = np.zeros((len(data), self.dim), dtype=np.float32)
        for t in range(len(data)):
            F[t] = self.feed(data[t])
        return F


def default_routes(N, rng):
    """Each node's 3 ports route to: another node's board / self / the input
    signal / off — the cell-level graph wiring."""
    routes = []
    for i in range(N):
        ports = []
        for _ in range(3):
            r = rng.random()
            if r < 0.2: ports.append(("off", 0))
            elif r < 0.4: ports.append(("self", i))
            elif r < 0.6: ports.append(("input", 0))
            else: ports.append(("node", int(rng.integers(0, N))))
        routes.append(ports)
    return routes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="demo-run/eval.txt")
    ap.add_argument("--bytes", type=int, default=14000)
    ap.add_argument("--fresh-offset", type=int, default=400000)
    ap.add_argument("--nodes", type=int, default=3)
    ap.add_argument("--side", type=int, default=16)
    ap.add_argument("--ticks", type=int, default=2)
    ap.add_argument("--rcells", type=int, default=96)
    ap.add_argument("--port-w", type=int, default=1)
    ap.add_argument("--poolk", type=int, default=160)
    ap.add_argument("--warmup", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    pool7, names = caca.load_pool(a.poolk, seed=a.seed)
    rng = np.random.default_rng(a.seed)
    ids = rng.choice(len(pool7), size=a.nodes, replace=False).tolist()
    routes = default_routes(a.nodes, rng)
    base = dict(side=a.side, ticks=a.ticks, rcells=a.rcells, decay=0.1,
                lut_ids=ids, routes=routes, port_w=a.port_w, reps=18)

    def evalnet(net, path, off, nb, label, full=False):
        data = open(path, "rb").read(off + nb)[off:]
        s, e = a.warmup, len(data) - 1
        F = net.run(data)[s:e]
        r = caca.evaluate(F, data, s, e, ctx=4, full=full)
        bpb = f"  both_bpb {r['both_bpb']:.3f}" if full else ""
        print(f"  {label:<26}res_acc {r['res_acc']:.3f}  both_acc {r['both_acc']:.3f}  "
              f"ctx_acc {r['ctx_acc']:.3f}{bpb}")
        return r

    print(f"network: {a.nodes} nodes {a.side}x{a.side}, ticks {a.ticks}, port_w {a.port_w}")
    print(f"routes: {routes}")
    print(f"rules: {[names[i] for i in ids]}\n")

    # 7->1 reservoir (ports OFF) vs cell10-routed (same rules, same structure)
    g7 = dict(base); g7["routes"] = [[("off", 0)] * 3 for _ in range(a.nodes)]
    for region, off, nb in [("IN-SAMPLE", 0, a.bytes), ("FRESH", a.fresh_offset, a.bytes)]:
        print(f"== {region} ==")
        evalnet(HexNet10(g7, pool7, seed=1234), a.file, off, nb, "7->1 (ports off)")
        evalnet(HexNet10(base, pool7, seed=1234), a.file, off, nb, "cell10 (routed ports)")

if __name__ == "__main__":
    main()
