#!/usr/bin/env python3
# spoeqi_demo.py — send the ENTIRE CA-1 computer through a spoeqi pact, four ways.
# Alice and Bob share only a pact (a seed). No machines are connected. Yet Bob ends up
# running the exact computer Alice sent, because the pact gives them a shared, deterministic,
# addressable byte-tape — and the computer is "naturally encrypted by the CAs".
import base64, json, hashlib
import numpy as np
import atn_spoeqi as sp
import calc, ca1sys, caos2

SEED = b"alice<->bob pact 2026"

# ───────── helpers: boot/run CA-1 images ─────────
def boot(prog, mem, regs=None):
    m = ca1sys.CA1Sys()
    for k, v in mem.items(): m.M[k] = v
    if regs:
        for r, v in regs.items(): setattr(m, r, v)
    return m

def calc_compute(prog, a, b, op):
    m = ca1sys.CA1Sys(); m.M[calc.OPA] = a; m.M[calc.OPB] = b; m.M[calc.OP] = op
    m.run((prog, {}), max_i=2_000_000)
    return m.M[calc.RHI] * 256 + m.M[calc.RLO]

def caos_frame(prog, M_bytes, regs, mx, my, mb):
    m = ca1sys.CA1Sys(fb_addr=caos2.FB, fb_w=caos2.W, fb_h=caos2.H)
    m.M[:] = M_bytes
    for r, v in regs.items(): setattr(m, r, v)
    m.M[caos2.MX] = mx; m.M[caos2.MY] = my; m.M[caos2.MB] = mb
    m.run(prog, max_i=4_000_000, frame_on=lambda mm: True)
    return bytes(m.M[caos2.FB:caos2.FB + caos2.W * caos2.H]), m

# ════════════ MODE A: seal & ship a program computer ════════════
def mode_A():
    print("== MODE A: seal & ship (envelope) — the CALCULATOR computer ==")
    cprog, _ = calc.program()
    img = sp.ca1_image(cprog, {})                       # the whole computer = program bytes
    alice = sp.Pact(SEED)
    env = sp.seal(alice, img, generation=10)
    print(f"   Alice sealed a {len(img)}-byte CA-1 image -> {len(env)}-byte envelope (key NOT sent)")
    bob = sp.Pact(SEED)                                  # Bob has ONLY the same seed
    blob, g = sp.unseal(bob, env, g_now=12, window=20)
    prog, mem, regs = sp.boot_image(blob)
    print(f"   Bob unsealed at gen {g}; image byte-identical: {blob == img}")
    r = calc_compute(prog, 13, 11, 2)
    print(f"   Bob boots the recovered computer and runs 13 x 11 = {r}  {'OK' if r == 143 else 'FAIL'}\n")
    return blob == img and r == 143

# ════════════ MODE A': ship a LIVE SNAPSHOT (running CA-OS) ════════════
def snapshot(m):
    return json.dumps({"kind": "snap", "M": base64.b64encode(bytes(m.M)).decode(),
                       "regs": {r: getattr(m, r) for r in ("A","X","P","SP","PC","Z","C","N")}}).encode()
def restore(blob):
    o = json.loads(blob.decode()); return bytearray(base64.b64decode(o["M"])), o["regs"]

def mode_Asnap():
    print("== MODE A': ship a LIVE SNAPSHOT — a running CA-OS desktop mid-session ==")
    osprog = caos2.program()
    m = ca1sys.CA1Sys(fb_addr=caos2.FB, fb_w=caos2.W, fb_h=caos2.H); caos2.load_memory(m); m.SP = caos2.STACK
    m.M[caos2.MX] = 80; m.M[caos2.MY] = 70; m.M[caos2.MB] = 0
    m.run(osprog, max_i=4_000_000, frame_on=lambda mm: True)       # boot one frame
    # click "9" then "x" then "9" then "=" so the live machine has 81 on its display
    def click(x, y):
        m.M[caos2.MX] = x; m.M[caos2.MY] = y; m.M[caos2.MB] = 1; m.run(osprog, frame_on=lambda mm: True)
        m.M[caos2.MB] = 0; m.run(osprog, frame_on=lambda mm: True)
    for col, row in [(2,0),(3,1),(2,0),(2,3)]:
        click(70+8+col*26+12, 30+42+row*20+9)
    snap = snapshot(m)
    alice = sp.Pact(SEED); env = sp.seal(alice, snap, generation=30)
    print(f"   Alice snapshots the running OS ({len(snap)//1024} KB) -> envelope {len(env)//1024} KB")
    bob = sp.Pact(SEED); blob, g = sp.unseal(bob, env, g_now=31, window=20)
    M2, regs = restore(blob)
    # Bob resumes: render the next frame on his side; compare to Alice's next frame
    fbA, _ = caos_frame(osprog, bytes(m.M), {r: getattr(m, r) for r in ("A","X","P","SP","PC","Z","C","N")}, 80, 70, 0)
    fbB, mB = caos_frame(osprog, bytes(M2), regs, 80, 70, 0)
    print(f"   Bob resumes the machine; display digits D3,D4 = {mB.M[caos2.D3]},{mB.M[caos2.D4]} (8,1 -> '81')")
    print(f"   Bob's next frame == Alice's next frame: {fbA == fbB}\n")
    return fbA == fbB and mB.M[caos2.D3] == 8 and mB.M[caos2.D4] == 1

# ════════════ MODE B: place the computer in the shared filesystem by COORDINATE ════════════
def otp_place(pact, data, component, generation):
    ks = sp.tap(pact, component, generation, len(data))
    return bytes(d ^ k for d, k in zip(data, ks))         # one-time-pad against the CA tape
def otp_recover(pact, ct, component, generation):
    ks = sp.tap(pact, component, generation, len(ct))
    return bytes(c ^ k for c, k in zip(ct, ks))

def mode_B():
    print("== MODE B: unify substrate — place the computer at pact coordinate (component,gen,offset) ==")
    cprog, _ = calc.program(); img = sp.ca1_image(cprog, {})
    alice = sp.Pact(SEED); COMP, GEN = 2, 7
    ct = otp_place(alice, img, COMP, GEN)                  # computer XOR shared CA keystream
    print(f"   Alice writes the computer into the shared CA filesystem at component {COMP}, gen {GEN}")
    print(f"   (transmits {len(ct)} masked bytes; the keystream is shared, never sent)")
    bob = sp.Pact(SEED)
    rec = otp_recover(bob, ct, COMP, GEN)
    rprog, rmem, _ = sp.boot_image(rec)
    r = calc_compute(rprog, 13, 11, 2)
    print(f'   Bob reads "relative position component {COMP}, gen {GEN}" -> recovers computer; 13x11={r}')
    print(f"   recovered byte-identical: {rec == img}\n")
    return rec == img and r == 143

# ════════════ MODE C: live shared machine + talk about relative positions ════════════
def mode_C():
    print("== MODE C: live shared computer — communicate plainly about relative positions ==")
    cprog, _ = calc.program()
    # Alice computes a 'secret' on her CA-1 and notes WHERE the answer sits (a relative position)
    secret_a, secret_b, op = 47, 6, 0                     # 47 + 6 = 53
    m = ca1sys.CA1Sys(); m.M[calc.OPA]=secret_a; m.M[calc.OPB]=secret_b; m.M[calc.OP]=op
    m.run((cprog, {}), max_i=2_000_000)
    addr = calc.RLO                                       # the result byte's address
    alice = sp.Pact(SEED)
    # Alice seals just her machine's memory image; tells Bob (publicly): "look at relative position 0x%X"
    env = sp.seal(alice, sp.ca1_image(cprog, {a: m.M[a] for a in range(0x10, 0x40)}), generation=50)
    public_reference = f"relative position 0x{addr:02X} of the computer at the pact"
    print(f"   Alice computes a secret, seals the machine, says publicly: 'read {public_reference}'")
    bob = sp.Pact(SEED); blob, g = sp.unseal(bob, env, g_now=50, window=10)
    _, mem, _ = sp.boot_image(blob)
    print(f"   Bob unseals (CA-decrypted), reads {public_reference}: {mem.get(addr)}  (= 47+6, never spoken aloud)")
    print(f"   only a relative POSITION crossed in the clear; the value rode the pact, CA-encrypted\n")
    return mem.get(addr) == 53

# ════════════ MODE D: computer-quine discovery (bounded, honest) ════════════
def mode_D(trials=4000):
    print("== MODE D: computer-quine search — does a pact NATURALLY contain a runnable program? ==")
    # A 'valid micro-program' here: tapped bytes interpreted as opcodes that HALT within budget
    # and leave a deterministic nonzero accumulator. Search seeds/coords; report hit rate.
    OPS = ["LDI","ADD","ADDI","SUB","SUBI","STA","LDA","JMP","JZ","HLT","NOP"]
    def decode(bs):
        prog=[]
        for i in range(0, len(bs)-1, 2):
            op = OPS[bs[i] % len(OPS)]; arg = bs[i+1] & 0x1F
            prog.append((op, arg))
        prog.append(("HLT", None)); return prog
    hits = 0; rng = np.random.default_rng(0)
    for t in range(trials):
        seed = b"quine-search-%d" % t
        p = sp.Pact(seed, ncomp=2, side=16)               # tiny pact = fast
        bs = sp.tap(p, 0, 0, 16)
        prog = decode(bs)
        m = ca1sys.CA1Sys()
        try:
            m.run((prog, {}), max_i=2000)
        except Exception:
            continue
        # 'runnable & meaningful': halted (didn't run off the end / cap) and A != 0
        if m.icount < 2000 and m.A != 0 and m.PC <= len(prog):
            hits += 1
    print(f"   searched {trials} random pacts; {hits} produced a halting, nonzero micro-program")
    print(f"   -> {'pacts naturally contain trivial programs (expected for a tiny op-space)' if hits else 'none found'};")
    print("      a USEFUL computer-quine (a chosen program appearing for free) is a real search")
    print("      problem — kin to spoeqi's l0_quine_search/keychain_quine. Honest: not free.\n")
    return True

if __name__ == "__main__":
    print("\nSending the CA-1 computer through a spoeqi pact (Alice & Bob share only a seed)\n" + "="*72)
    results = {"A": mode_A(), "A'": mode_Asnap(), "B": mode_B(), "C": mode_C(), "D": mode_D()}
    print("="*72)
    print("results:", {k: ("OK" if v else "FAIL") for k, v in results.items()})
