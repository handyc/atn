#!/usr/bin/env python3
# atn_spoeqi.py — a spoeqi-style PACT bridge that speaks CA-1. Lets us "send the entire
# computer through a pact": two parties holding the same pact derive identical, deterministic
# CA state forever (no key transmitted), giving a shared addressable byte-tape (tap) and a
# rolling-key authenticated envelope (seal/unseal). A CA-1 computer is just a byte image
# (program + memory + registers), so it rides through the pact like any payload.
#
# Faithful to velour-caml/spoeqi's architecture:
#   * tap(c,g,n)   = SHA-256 chain over (domain||c||g||counter||grid[c])  [keystream.py]
#   * derive_key(g)= SHA-256(DOMAIN_ENVELOPE||g||full_state)               [envelope.py]
#   * seal/unseal  = ChaCha20-Poly1305, brute-force a +/-window of generations
# Difference (by design): the pact CA here IS the atn hex-K4 CA (rulehub.hex_key), the same
# family spoeqi uses — so CA-1 and the pact share one substrate. (Byte-level interop with a
# specific velour pact would just need spoeqi's exact neighbour-order constants.)
from __future__ import annotations
import hashlib, struct, json, secrets
import numpy as np
import rulehub
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.exceptions import InvalidTag

DOMAIN_DEFAULT  = b'spoeqi/tap/v1'
DOMAIN_ENVELOPE = b'spoeqi/envelope/v1'
MAGIC = b'ATNPACT'; VERSION = 1
HEADER = len(MAGIC) + 1 + 12

class Pact:
    """Shared seed + per-component hex-CA rules + initial grids. Two parties with the same
    seed see identical CA state at every generation — the shared, addressable byte-tape."""
    def __init__(self, seed: bytes, ncomp: int = 8, side: int = 64):
        self.seed = seed; self.ncomp = ncomp; self.side = side; self.area = side * side
        sd = int.from_bytes(hashlib.sha256(seed + b'rules').digest()[:8], 'little')
        rng = np.random.default_rng(sd)
        self.luts = [rng.integers(0, 4, rulehub.RULE_TABLE_SIZE if hasattr(rulehub, 'RULE_TABLE_SIZE') else 16384).astype(np.uint8) for _ in range(ncomp)]
        ig = np.random.default_rng(int.from_bytes(hashlib.sha256(seed + b'grid').digest()[:8], 'little'))
        self.init = [ig.integers(0, 4, (side, side)).astype(np.uint8) for _ in range(ncomp)]
        self._cache = {0: [g.copy() for g in self.init]}     # generation -> list of grids

    def grids_at(self, gen: int):
        if gen in self._cache: return self._cache[gen]
        base = max(g for g in self._cache if g <= gen)
        grids = [g.copy() for g in self._cache[base]]
        for _ in range(gen - base):
            grids = [self.luts[c][rulehub.hex_key(grids[c].astype(np.int64))].astype(np.uint8) for c in range(self.ncomp)]
        self._cache[gen] = [g.copy() for g in grids]
        return grids

    def state_bytes(self, gen: int) -> bytes:
        return np.concatenate([g.ravel() for g in self.grids_at(gen)]).astype(np.uint8).tobytes()

def tap(pact: Pact, component: int, generation: int, n_bytes: int, domain: bytes = DOMAIN_DEFAULT) -> bytes:
    """n_bytes of deterministic keystream from component c at generation g (the shared filesystem)."""
    grid = pact.grids_at(generation)[component].ravel().astype(np.uint8).tobytes()
    out = bytearray(); counter = 0
    while len(out) < n_bytes:
        h = hashlib.sha256(); h.update(domain)
        h.update(struct.pack('<IQI', component, generation, counter)); h.update(grid)
        out.extend(h.digest()); counter += 1
    return bytes(out[:n_bytes])

def derive_key(pact: Pact, generation: int) -> bytes:
    h = hashlib.sha256(); h.update(DOMAIN_ENVELOPE)
    h.update(struct.pack('<Q', generation)); h.update(pact.state_bytes(generation))
    return h.digest()

def seal(pact: Pact, plaintext: bytes, generation: int) -> bytes:
    key = derive_key(pact, generation); nonce = secrets.token_bytes(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)
    return MAGIC + bytes([VERSION]) + nonce + ct

def unseal(pact: Pact, sealed: bytes, g_now: int, window: int = 20):
    if sealed[:len(MAGIC)] != MAGIC: raise ValueError('not an atn pact envelope')
    nonce = sealed[len(MAGIC)+1:HEADER]; ct = sealed[HEADER:]
    cands = sorted(range(max(0, g_now-window), g_now+window+1), key=lambda g: abs(g-g_now))
    for g in cands:
        try:
            pt = ChaCha20Poly1305(derive_key(pact, g)).decrypt(nonce, ct, None)
            return pt, g
        except InvalidTag:
            continue
    raise ValueError(f'could not unseal within +/-{window} of generation {g_now}')

# ───────────────────── CA-1 computer image (the payload) ────────────────────
def ca1_image(prog, mem: dict, regs: dict | None = None) -> bytes:
    """Serialize a CA-1 computer to bytes. mem: {addr:int}. regs optional (live snapshot)."""
    obj = {"prog": [[op, (arg if arg is not None else 0)] for op, arg in prog],
           "mem": {str(k): int(v) for k, v in mem.items()},
           "regs": regs or {}}
    return json.dumps(obj, separators=(",", ":")).encode()

def boot_image(blob: bytes):
    obj = json.loads(blob.decode())
    prog = [(op, arg) for op, arg in obj["prog"]]
    mem = {int(k): v for k, v in obj["mem"].items()}
    return prog, mem, obj.get("regs", {})

if __name__ == "__main__":
    # smoke: identical pacts on two machines see identical state + tap
    seed = b"the-pact-of-alice-and-bob"
    alice = Pact(seed); bob = Pact(seed)
    assert alice.state_bytes(7) == bob.state_bytes(7), "pacts diverged!"
    assert tap(alice, 3, 5, 64) == tap(bob, 3, 5, 64), "tap diverged!"
    msg = b"hello through the cellular automaton"
    env = seal(alice, msg, generation=10)
    pt, g = unseal(bob, env, g_now=12, window=20)
    print("pact bridge smoke:")
    print(f"  shared state @gen7 identical: True   tap @c3g5 identical: True")
    print(f"  sealed {len(msg)}B -> envelope {len(env)}B (key/CA-state NOT transmitted)")
    print(f"  Bob unsealed at generation {g}: {pt.decode()!r}  -> {'OK' if pt==msg else 'FAIL'}")
