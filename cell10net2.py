#!/usr/bin/env python3
# cell10net2.py — RICH-source cell10 graph reservoir. Extends cell10net with a
# much wider menu of things the 3 ports can connect to, per the user's hypothesis
# that the extra inputs help IF wired to the right thing. Ports can route to:
#   node   : another node's CURRENT board state
#   self   : this node's current board
#   input  : the current byte (broadcast)
#   pbyte  : a PREVIOUS byte (lag 1/2/3, broadcast) -- temporal input memory
#   pboard : a node's board ONE BYTE AGO -- temporal state memory
#   clock  : a positional/time signal ((t>>arg)&3, broadcast) -- "external" signal
#   func   : a derived FUNCTION of a node's board (local neighbour sum mod 4)
#
# Ports are FORCED ON (no "off"; port_w>=1) so the GA must find a USE for them;
# fitness stays honest (held-out both_acc), so the verdict is real: does a
# forced, rich wiring beat the ports-off 7->1 ceiling (0.3037 on news)?

import numpy as np
import caca, cell10

SOURCES = ["node", "self", "input", "pbyte", "pboard", "clock", "func"]

class HexNet10R:
    def __init__(self, gene, pool7, seed=0):
        rng = np.random.default_rng(seed)
        self.S = gene["side"]; self.ticks = gene["ticks"]; self.w = max(1, gene.get("port_w", 1))
        ids = gene["lut_ids"]; self.N = len(ids)
        self.rules = pool7[np.array(ids)].copy()
        self.boards = np.zeros((self.N, self.S, self.S), dtype=np.uint8)
        cells = self.S * self.S
        self.routes = gene["routes"]
        decay = gene.get("decay", 0.0)
        self.dmask = [(rng.random(cells) < decay) if decay > 0 else None for _ in range(self.N)]
        reps = gene.get("reps", 12)
        flat = rng.permutation(cells)[:4 * reps]
        self.drive = [flat[k * reps:(k + 1) * reps] for k in range(4)]
        self.rcells = min(gene.get("rcells", 64), cells)
        self.rsel = np.array([rng.permutation(cells)[:self.rcells] for _ in range(self.N)])
        self.dim = self.N * self.rcells * 4
        self.t = 0; self.byte_hist = []; self.prev_boards = self.boards.copy()

    def reset(self):
        self.boards[:] = 0; self.t = 0; self.byte_hist = []
        self.prev_boards = self.boards.copy()

    def _func(self, g):
        return (g + np.roll(g, 1, 0) + np.roll(g, 1, 1)) & 3

    def _port(self, kind, arg, cur, ago, inp, S):
        if kind == "node":   return cur[arg % self.N]
        if kind == "self":   return cur[arg % self.N]
        if kind == "input":  return inp
        if kind == "pbyte":
            lag = (arg % 3) + 1
            v = (self.byte_hist[-lag] & 3) if len(self.byte_hist) >= lag else 0
            return np.full((S, S), v, np.int64)
        if kind == "pboard": return ago[arg % self.N].astype(np.int64)
        if kind == "clock":  return np.full((S, S), (self.t >> (arg % 4)) & 3, np.int64)
        if kind == "func":   return self._func(cur[arg % self.N].astype(np.int64))
        return np.zeros((S, S), np.int64)

    def feed(self, byte):
        S = self.S; cells = S * S
        ago = self.prev_boards            # state one byte ago (fixed during ticks)
        inp = np.full((S, S), byte & 3, np.int64)
        flat = self.boards.reshape(self.N, cells)
        for k in range(4):
            flat[0, self.drive[k]] = (byte >> (2 * k)) & 3
        for _ in range(self.ticks):
            cur = self.boards.copy()
            newb = np.empty_like(self.boards)
            for i in range(self.N):
                key = cell10._hex_neigh(cur[i].astype(np.int64))
                out7 = self.rules[i][key].astype(np.int64)
                psum = np.zeros((S, S), np.int64)
                for (kind, arg) in self.routes[i]:
                    psum = psum + self._port(kind, int(arg), cur, ago, inp, S)
                newb[i] = ((out7 + self.w * psum) & 3).astype(np.uint8)
            self.boards = newb
            for i in range(self.N):
                if self.dmask[i] is not None:
                    self.boards[i].reshape(cells)[self.dmask[i]] = 0
        # history update (AFTER stepping): record this byte and this feed's start state
        self.byte_hist.append(byte)
        if len(self.byte_hist) > 8: self.byte_hist.pop(0)
        self.prev_boards = self.boards.copy()
        self.t += 1
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
