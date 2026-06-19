#!/usr/bin/env python3
# bench_hexkey.py — REGRESSION TEST + benchmark for rulehub.hex_key (the cached-gather hot loop).
# Proves the live hex_key is BIT-EXACT vs the original roll/where version on the int64 boards every caller
# feeds in, then benchmarks the stepping loop.  (uint8 is intentionally NOT tested: the old code overflows
# on uint8 via `b << 12`, and no caller uses it — all pass b.astype(np.int64).)
import time, numpy as np
import rulehub                                         # the live (fast) hex_key under test

def _em(H): return (np.arange(H) % 2 == 0).reshape(H, 1)
def hex_key_ref(b):                                    # the ORIGINAL roll/where rulehub.hex_key
    H = b.shape[0]; em = _em(H)
    up = np.roll(b, 1, 0); dn = np.roll(b, -1, 0); l = np.roll(b, 1, 1); rg = np.roll(b, -1, 1)
    nw = np.where(em, np.roll(up, 1, 1), up); ne = np.where(em, up, np.roll(up, -1, 1))
    sw = np.where(em, np.roll(dn, 1, 1), dn); se = np.where(em, dn, np.roll(dn, -1, 1))
    return (b << 12) | (nw << 10) | (ne << 8) | (rg << 6) | (se << 4) | (sw << 2) | l

hex_key_fast = rulehub.hex_key

if __name__ == "__main__":
    # 1) bit-exactness across even/odd heights and rectangular boards (int64 = the real usage)
    rng = np.random.default_rng(0); allok = True
    for (H, W) in [(60, 60), (61, 61), (48, 84), (16, 16), (7, 11), (128, 128)]:
        b = rng.integers(0, 4, (H, W)).astype(np.int64)
        ok = np.array_equal(np.asarray(hex_key_ref(b)), np.asarray(hex_key_fast(b)))
        allok &= ok
        if not ok: print(f"  MISMATCH at {H}x{W}")
    print(f"  bit-exact vs original roll/where reference (int64): {allok}")

    # 2) benchmark a realistic stepping loop (a LUT applied each tick), like every sim does
    lut = rng.integers(0, 4, 16384).astype(np.uint8)
    for (H, W, N) in [(60, 60, 400), (128, 128, 200)]:
        b0 = rng.integers(0, 4, (H, W)).astype(np.int64)
        def run(fn, b):
            b = b.copy()
            for _ in range(N): b = lut[fn(b)].astype(np.int64)
            return b
        rr = run(hex_key_ref, b0); rf = run(hex_key_fast, b0)
        assert np.array_equal(rr, rf), "stepping diverged!"
        t0 = time.perf_counter(); run(hex_key_ref, b0);  tref = time.perf_counter() - t0
        t0 = time.perf_counter(); run(hex_key_fast, b0); tfast = time.perf_counter() - t0
        print(f"  {H}x{W} x{N} steps: ref {tref*1e3:6.1f} ms | fast {tfast*1e3:6.1f} ms | speedup {tref/tfast:.2f}x")
