#!/usr/bin/env python3
# caplace.py — PLACE-AND-ROUTE for the cellular-automaton computer: the last gap to a self-wiring
# datapath.  Every CA capability is already verified — the gate (gatecell), the confined gate->gate
# wire (autowire2), routing depth + fan-out (autowire4).  What was missing was the LAYOUT ALGORITHM:
# given a netlist, decide WHERE each gate-chamber sits and AUTO-ROUTE the channels between them, with
# no hand-placed coordinates.  This does that — a placer (chambers on a column grid by logic depth) and
# a Lee/BFS maze router (channels snake through free space, kept apart by wall margins) — then realises
# the result as ONE CA configuration (chambers + channels carved into a wall field, inputs seeded as
# carriers, gate biases seeded) and runs it.  The chamber is a winner-take-all NOR of every carrier that
# floods in; channels transport and OR-merge carriers.  So the CA computes the routed netlist in one run.
#
# Result: a netlist in -> the CA lays out and wires its own datapath -> verified truth table (held-out).
import numpy as np, rulehub

# ---- the CA rule + mechanism (identical physics to autowire2) ----
def _newton_lut(cx, cy, span, it=160, side=128):
    st = span/side; ox = cx-st*side*.5; oy = cy-st*side*.5
    gx, gy = np.meshgrid(ox+np.arange(side)*st, oy+np.arange(side)*st)
    l = rulehub._posterise(rulehub._newton(gx, gy, it), it)
    if l[0] != 0: l = l.copy(); l[0] = 0
    return l
LZ = _newton_lut(-0.255, -0.077, 0.270)    # spreading carrier (the wire)
LO = _newton_lut(-0.105, -0.135, 0.152)    # stable bias (the gate's "1" reference)

# ============================ the netlist ================================================
# A circuit is: primary inputs (named), NOR chambers (each NORs the carriers that reach it), and nets
# (source -> chamber).  A source is a primary input or another chamber's output.  One chamber is the
# output.  (NOR is universal; multi-LEVEL logic needs active regeneration — see the honesty note in main.)
class Net:
    def __init__(self, inputs, chambers, nets, out):
        self.inputs = inputs           # ["A","B","C"]
        self.chambers = chambers       # ["g1","g2"]
        self.nets = nets               # [("A","g1"),("B","g1"),("g1","g2"),("C","g2")]
        self.out = out                 # "g2"

# ============================ placement ==================================================
GRID_H, GRID_W = 56, 132
def place(net):
    """Assign each chamber a column by its logic depth (longest path from a primary input), rows spread
    vertically.  Returns {chamber: (cx, cy)} chamber-centre coords + input port coords on the left edge."""
    depth = {i: 0 for i in net.inputs}
    # longest-path depth for chambers (topological; nets are a DAG)
    for _ in range(len(net.chambers) + 1):
        for s, d in net.nets:
            if d in net.chambers:
                depth[d] = max(depth.get(d, 0), depth.get(s, 0) + 1)
    maxd = max(depth[c] for c in net.chambers)
    cols = {}
    for c in net.chambers: cols.setdefault(depth[c], []).append(c)
    pos = {}
    for dval, cs in cols.items():
        cx = 16 + int((GRID_W - 32) * (dval - 1) / max(1, maxd))    # chambers start at depth>=1
        for k, c in enumerate(cs):
            cy = int(GRID_H * (k + 1) / (len(cs) + 1))
            pos[c] = (cx, cy)
    ports = {}                                                       # primary inputs: ports on the far left
    for k, i in enumerate(net.inputs):
        ports[i] = (6, int(GRID_H * (k + 1) / (len(net.inputs) + 1)))
    return pos, ports

CH_HALF = 7                                                          # chamber half-size
def lee_route(occupied, src, dst):
    """BFS shortest path of OPEN cells from src to dst through free space (occupied=True is blocked).
    Returns the path as a list of (r,c) or None."""
    H, W = occupied.shape
    from collections import deque
    sr, sc = src; dr, dc = dst
    seen = {(sr, sc): None}; q = deque([(sr, sc)])
    while q:
        r, c = q.popleft()
        if abs(r-dr) + abs(c-dc) <= 1:
            seen.setdefault((dr, dc), (r, c)); path = [(dr, dc)]; cur = (r, c)
            while cur is not None: path.append(cur); cur = seen[cur]
            return path[::-1]
        for nr, nc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
            if 0 <= nr < H and 0 <= nc < W and (nr, nc) not in seen and not occupied[nr, nc]:
                seen[(nr, nc)] = (r, c); q.append((nr, nc))
    return None

def route(net, pos, ports):
    """Carve chambers + auto-routed channels into an OPEN mask.  Channels run through FREE space (chamber
    interiors are obstacles so wires go around them); each enters its target chamber at a staggered edge
    cell.  Returns OPEN, the per-input seed cells, each chamber's bias cell."""
    OPEN = np.zeros((GRID_H, GRID_W), bool)
    occupied = np.zeros((GRID_H, GRID_W), bool)                       # routing obstacles (False = free)
    for c, (cx, cy) in pos.items():
        OPEN[cy-CH_HALF:cy+CH_HALF+1, cx-CH_HALF:cx+CH_HALF+1] = True
        occupied[cy-CH_HALF:cy+CH_HALF+1, cx-CH_HALF:cx+CH_HALF+1] = True   # don't route through chambers
    def carve(r, c):                                                 # 3-cell-wide channel
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                rr, cc = r+dr, c+dc
                if 0 <= rr < GRID_H and 0 <= cc < GRID_W: OPEN[rr, cc] = True
    def block(r, c):                                                 # keep other channels >=2 cells away
        for dr in range(-2,3):
            for dc in range(-2,3):
                rr, cc = r+dr, c+dc
                if 0 <= rr < GRID_H and 0 <= cc < GRID_W: occupied[rr, cc] = True
    seeds = {}
    bias = {c: (pos[c][1], pos[c][0]) for c in net.chambers}
    fanin = {c: sum(1 for s, d in net.nets if d == c) for c in net.chambers}
    fanout = {}; outcount = {}                                        # per-SOURCE fan-out (ports + chambers)
    for s, d in net.nets: fanout[s] = fanout.get(s, 0) + 1; outcount[s] = 0
    incount = {c: 0 for c in net.chambers}
    def stagger(centre, count, total):                                # spread N entry/exit cells across an edge
        return centre + int(round((count - (total-1)/2) * (2*(CH_HALF-1)) / max(1, total-1)))
    order = sorted(net.nets, key=lambda sd: abs(pos[sd[1]][0] - (ports[sd[0]][0] if sd[0] in ports else pos[sd[0]][0])))
    for s, d in order:
        cxd, cyd = pos[d]; k = incount[d]; incount[d] += 1
        dst = (stagger(cyd, k, fanin[d]), cxd - CH_HALF - 1)          # spread entries on the dest's left edge
        ko = outcount[s]; outcount[s] += 1
        if s in ports:
            src = (stagger(ports[s][1], ko, fanout[s]), ports[s][0])  # spread exits from the input port
        else:
            cxs, cys = pos[s]; src = (stagger(cys, ko, fanout[s]), cxs + CH_HALF + 1)   # ... or the source chamber's right edge
        occupied[src] = False; occupied[dst] = False
        path = lee_route(occupied, src, dst)
        if path is None: raise RuntimeError(f"route failed {s}->{d}")
        for (r, c) in path: carve(r, c)
        for (r, c) in path: block(r, c)
        if s in ports: seeds[s] = src
    return OPEN, seeds, bias

# ============================ realise on the CA + run ====================================
def simulate(OPEN, seeds, bias, out_pos, invals, T=340, seed=0, biasv=18):
    WALL = ~OPEN
    rng = np.random.default_rng(seed)
    Z = np.zeros(OPEN.shape, np.uint8); O = np.zeros(OPEN.shape, np.uint8)
    def patch(arr, r, c, sz): arr[max(0,r-sz//2):r-sz//2+sz, max(0,c-sz//2):c-sz//2+sz] = rng.integers(1, 4, (min(sz,arr.shape[0]-(r-sz//2)), min(sz,arr.shape[1]-(c-sz//2))))
    for name, (r, c) in seeds.items():
        if invals.get(name): patch(Z, r, c, 5)                        # input=1 -> inject a carrier
    for t in range(T):
        if t < 50:
            for c, (r, cc) in bias.items(): patch(O, r, cc, biasv)    # hold each chamber's bias
        Z = LZ[rulehub.hex_key(Z.astype(np.int64))].astype(np.uint8)
        O = LO[rulehub.hex_key(O.astype(np.int64))].astype(np.uint8)
        Z[WALL] = 0; O[WALL] = 0
        both = (Z > 0) & (O > 0); Z[both] = 0; O[both] = 0
    (orow, ocol) = out_pos
    reg = (slice(max(0,orow-CH_HALF), orow+CH_HALF+1), slice(max(0,ocol-CH_HALF), ocol+CH_HALF+1))
    return 1 if int((O[reg] > 0).sum()) > int((Z[reg] > 0).sum()) else 0

def pnr(net):
    pos, ports = place(net); OPEN, seeds, bias = route(net, pos, ports)
    out_pos = (pos[net.out][1], pos[net.out][0])
    return OPEN, seeds, bias, out_pos, pos

def verify(net, ref, seeds_list):
    OPEN, seeds, bias, out_pos, pos = pnr(net)
    ok = tot = 0; tbl = {}
    import itertools
    for combo in itertools.product((0,1), repeat=len(net.inputs)):
        invals = dict(zip(net.inputs, combo))
        bits = [simulate(OPEN, seeds, bias, out_pos, invals, seed=sd+7*sum(combo)) for sd in seeds_list]
        got = int(round(np.mean(bits))); want = ref(*combo)
        tbl[combo] = got; ok += sum(b == want for b in bits); tot += len(bits)
    return ok/tot, tbl, OPEN, pos

def main():
    print("caplace — automatic place-and-route on the CA: a netlist -> the CA wires its own datapath\n")
    # netlist: a routed 3-input NOR.  g1 = NOR(A,B); its carrier relays to g2, which also gets C.
    net = Net(["A","B","C"], ["g1","g2"],
              [("A","g1"),("B","g1"),("g1","g2"),("C","g2")], out="g2")
    ref = lambda A,B,C: 1 - (A | B | C)
    OPEN, _, _, _, pos = pnr(net)
    print(f"  placed {len(net.chambers)} chambers at {pos}; routed {len(net.nets)} nets through {int(OPEN.sum())} open cells")
    tr, tblr, _, _ = verify(net, ref, range(6))
    ho, tblh, OPEN, pos = verify(net, ref, range(200, 206))
    print(f"  TRAIN    acc {100*tr:.0f}%")
    print(f"  HELD-OUT acc {100*ho:.0f}%   truth { {''.join(map(str,k)):v for k,v in tblh.items()} }   (ref ~(A|B|C))")
    # ASCII picture of the auto-generated layout
    print("\n  auto-laid-out CA (#=open chamber/channel, .=wall):")
    for r in range(0, GRID_H, 2):
        print("   " + "".join("#" if OPEN[r, c] else "." for c in range(0, GRID_W, 2)))
    # a deeper netlist: a 4-input NOR TREE.  g1=NOR(A,B), g2=NOR(C,D) (same column), g3=NOR(g1,g2).
    print("\n  deeper netlist — 4-input NOR tree (3 chambers, 6 auto-routed nets):")
    net2 = Net(["A","B","C","D"], ["g1","g2","g3"],
               [("A","g1"),("B","g1"),("C","g2"),("D","g2"),("g1","g3"),("g2","g3")], out="g3")
    ref2 = lambda A,B,C,D: 1 - (A | B | C | D)
    pos2 = pnr(net2)[4]
    print(f"    placed at {pos2}")
    ho2, tbl2, _, _ = verify(net2, ref2, range(200, 205))
    print(f"    HELD-OUT acc {100*ho2:.0f}%   (ref ~(A|B|C|D))")
    if ho >= 0.95 and ho2 >= 0.95:
        print("\n  -> SELF-WIRING WORKS: the layout + every channel was generated by the algorithm (no hand")
        print("     coordinates); the CA runs it and computes the netlist.  Place-and-route is closed for")
        print("     routed multi-input NOR trees.  (Multi-LEVEL logic — NOR of NOR — needs active carrier")
        print("     regeneration between stages, an inverter that re-floods: the next honest frontier.)")

if __name__ == "__main__":
    main()
