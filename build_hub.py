#!/usr/bin/env python3
# build_hub.py — dissemination/index.html: a hub linking every glider lab, grouped by the arc from
# a cellular-automaton rule -> gates -> a computer -> an OS -> the encrypted pact -> the 32-bit machine.
# Static page; links to the local lab HTML by relative path (open via file:// in a browser).
import os

GROUPS = [
    ("Foundations — the rule, and reading/writing it", [
        ("glider-lab.html",   "Glider Lab 1", "Interactive companion to “Glider Surgery” — the hex K=4 rule and its gliders."),
        ("glider-lab2.html",  "Glider Lab 2", "Fractal rule explorer — derive CA rule tables from escape-time fractals."),
        ("glider-lab3.html",  "Glider Lab 3", "Rule studio + word→glider: turn text into seeded glider patterns."),
        ("glider-lab4.html",  "Glider Lab 4", "Word-trace atlas — the trajectories words leave in the CA."),
        ("glider-lab6.html",  "Glider Lab 6", "Any image becomes a CA rule (posterised escape-time → LUT)."),
        ("glider-lab7.html",  "Glider Lab 7", "Image as the seed — feed a picture into the automaton."),
    ]),
    ("From gliders to a computer", [
        ("glider-lab5.html",  "Glider Lab 5", "CA memory register — a mutual-annihilation latch holding a bit."),
        ("glider-lab8.html",  "Glider Lab 8", "The sequential circuit — a closed feedback loop (LFSR) on real LUTs."),
        ("glider-lab9.html",  "Glider Lab 9", "CA Photoshop + video reel — CA rulesets as image filters."),
        ("glider-lab10.html", "Glider Lab 10","The whole CA computer, live — NAND, latch, inverter, wire, register, all running."),
    ]),
    ("A computer, and an OS, on the CA", [
        ("glider-lab11.html", "Glider Lab 11","Doom-reduced — a raycaster on the CA-1 computer."),
        ("glider-lab12.html", "CA-1 98",      "A Windows-98-style desktop; the apps’ arithmetic runs on CA-1."),
        ("glider-lab13.html", "CA-OS",        "A whole desktop OS: CA-1 draws every pixel; the browser is a dumb terminal."),
        ("glider-lab14.html", "CA-OS v2",     "The Windows-like CA-OS with the live CA-internals panels below."),
    ]),
    ("Alice & Bob — the cellular-automaton pact (encrypted line)", [
        ("glider-lab15.html", "Pact 1", "Sending a computer through a cellular-automaton pact (shared randomness)."),
        ("glider-lab16.html", "Pact 2", "Sending a whole desktop through the pact."),
        ("glider-lab17.html", "Pact 3", "Steering one desktop over an encrypted classical line."),
        ("glider-lab18.html", "CA-Office", "The office suite (Writer/Sheet/Calc) on a cellular automaton."),
        ("glider-lab19.html", "Dual CA-Office", "One shared office suite over the encrypted line."),
        ("glider-lab20.html", "Cut / restore + mother server", "An encrypted line you can cut, restore, and sync through a zero-trust server."),
        ("glider-lab21.html", "The showcase", "Full CA-Office over the line, with live metrics + a “How it works” tab."),
        ("glider-lab26.html", "The spoeqi envelope", "The SECURE pact: a vetted AEAD (AES-256-GCM) keyed by the CA — seal/unseal, with the generation discovered by the receiver."),
    ]),
    ("CA-2 — the 32-bit machine, with a scientific calculator and a GPU", [
        ("glider-lab22.html", "CA-OS/2", "A 32-bit OS (512×384): draggable windows + a SCIENTIFIC CALCULATOR (sin/cos/tan, ln/log/eˣ/xʸ, √, x², 1/x — all computed on the CA via CORDIC + series), an 8×8 spreadsheet, a multilingual antialiased Writer, Paint, and a 3D app — a spinning cube the CA renders itself."),
        ("glider-lab23.html", "Wide-word CA computer", "Factorials & RSA via BigInt — integers no host register can hold."),
        ("glider-lab24.html", "CA-OS/2 dual-pane", "The full suite shared over a SECURE line — every input delta sealed with AES-256-GCM keyed by the CA; cut/restore, live metrics, live CA panels."),
        ("caos-32-min.html",  "CA-OS/2 (minimal)", "Just the OS and its apps — calculator, sheet, writer, paint, 3D — no prose. Shows how small the bare OS is."),
        ("glider-lab25.html", "CA Unicode Writer", "Type any language — the CA holds the full 16×16 antialiased font (Latin/Greek/Cyrillic/CJK/Hangul/kana) in its own memory and blits every glyph."),
    ]),
]
# The honest chain, told once, as the credibility anchor of the whole project.
ARC = """
 <section class="arc">
  <h2>The arc — a computer, bottom-up, out of one rule</h2>
  <ol class="steps">
   <li><b>The rule.</b> A hexagonal K=4 cellular automaton with a class-4 (glider-bearing) rule grown from an escape-time fractal.</li>
   <li><b>A gate.</b> Two gliders that mutually annihilate make a winner-take-all latch; tuned, it is a real <b>NAND</b> — verified against its truth table on held-out random seeds.</li>
   <li><b>An adder.</b> NANDs compose into a 1-bit full adder, rippled to <b>any width</b> (8, 32, 128, 1024-bit) — verified bit-for-bit against reference addition.</li>
   <li><b>A CPU.</b> The adder + mutual-annihilation registers + a NAND ALU + branch logic make <b>CA-1</b>, an 8-bit accumulator machine that runs real programs (multiply, sum-1..N).</li>
   <li><b>Self-wiring.</b> A place-and-route algorithm lays out gate-chambers and auto-routes the connecting channels — the CA <b>wires its own datapath</b> from a netlist (routed NOR trees, 100% held-out).</li>
   <li><b>An OS.</b> <b>CA-OS/2</b> (the 32-bit CA-2): a desktop where the CA draws every pixel — Writer, Paint, an 8×8 Sheet, a scientific Calculator, and a 3D app.</li>
   <li><b>A coprocessor + a GPU.</b> A CORDIC math unit (sin/cos/ln/exp…) and a triangle rasteriser, both grounded in the same verified adder — so the calculator and the spinning 3D cube are <b>computed by the cellular automaton</b>.</li>
   <li><b>The pact.</b> Two machines share a seed, regenerate the identical CA-OS locally, and exchange only AES-256-GCM-sealed input deltas keyed by the CA state — “send the whole computer through the pact,” in a 64&nbsp;KB binary.</li>
  </ol>
  <div class="honest">
   <h3>Is it real? — what the cellular automaton actually computes</h3>
   <ul>
    <li><b>Genuinely on the gates (verified gate-by-gate):</b> the NAND gate, the any-width ripple adder, NAND→logic composition, the latch→register, and the place-and-route layout. These run as the literal cellular automaton and are checked against truth/reference.</li>
    <li><b>Computed by the CA datapath, run at speed:</b> the OS, the scientific calculator (CORDIC/series), and the GPU. Every arithmetic op is the <i>same</i> verified CA adder — but emulated fast rather than ground out glider-by-glider (one gate-true cosine is ~minutes; sampled adds are re-checked on the real gates to prove equivalence). Capability scales; speed never.</li>
    <li><b>Host-provided (not the CA):</b> the browser blits the framebuffer and forwards your mouse/keys — a dumb terminal. The font is decompressed by the host, then stored in the CA’s own memory and blitted by CA code.</li>
   </ul>
   <p>The honest verdict: a <b>teaching instrument</b> that demonstrates universality and capability from a single CA rule — not a speed competitor to silicon.</p>
  </div>
 </section>"""

def build():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "dissemination", "index.html")
    rows = []
    for title, labs in GROUPS:
        cards = []
        for fn, name, blurb in labs:
            exists = os.path.exists(os.path.join(here, "dissemination", fn))
            cls = "card" + ("" if exists else " missing")
            href = fn if exists else "#"
            tag = "" if exists else "<span class='miss'>not generated</span>"
            cards.append(f"<a class='{cls}' href='{href}'><b>{name}</b>{tag}<span>{blurb}</span></a>")
        rows.append(f"<section><h2>{title}</h2><div class='grid'>{''.join(cards)}</div></section>")
    n = sum(len(l) for _, l in GROUPS)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Glider Labs — a computer out of a cellular automaton</title>
<style>
 :root{{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff}}
 *{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,Segoe UI,Roboto,sans-serif}}
 .wrap{{max-width:1000px;margin:0 auto;padding:22px}}
 h1{{font-size:24px;margin:0 0 4px}} .sub{{color:var(--mut);max-width:760px;margin:0 0 8px}}
 h2{{font-size:15px;color:var(--b);margin:22px 0 8px;border-bottom:1px solid #2a3340;padding-bottom:4px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
 a.card{{display:block;background:#161b22;border:1px solid #2a3340;border-radius:9px;padding:11px 12px;text-decoration:none;color:var(--ink)}}
 a.card:hover{{border-color:var(--a);background:#1b2230}}
 a.card b{{color:var(--a);display:block;font-size:13.5px}} a.card span{{display:block;color:var(--mut);font-size:12px;margin-top:3px}}
 a.card.missing{{opacity:.5}} .miss{{color:var(--mut);font-size:10px;font-weight:400;margin-left:6px}}
 .foot{{color:var(--mut);font-size:12px;margin-top:22px;border-top:1px solid #2a3340;padding-top:10px}}
 code{{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}}
 .steps{{margin:6px 0 4px;padding-left:20px}} .steps li{{margin:3px 0}}
 .honest{{background:#11161d;border:1px solid #2a3340;border-left:3px solid var(--a);border-radius:8px;padding:10px 14px;margin:12px 0}}
 .honest h3{{margin:0 0 6px;font-size:14px;color:var(--a)}} .honest ul{{margin:6px 0;padding-left:18px}}
 .honest li{{margin:4px 0;color:var(--mut)}} .honest b{{color:var(--ink)}} .honest i{{color:var(--b)}} .honest p{{color:var(--mut);margin:6px 0 0}}
</style></head><body><div class="wrap">
 <h1>Glider Labs</h1>
 <p class="sub">A computer built out of a cellular automaton, lab by lab — from the hexagonal K=4 rule and its
 gliders, to logic gates and memory, to the CA-1 computer, an operating system, an encrypted “pact” between two
 machines, and finally the 32-bit CA-2 with a full office suite. {n} interactive labs; all run in the browser.</p>
 {ARC}
 {''.join(rows)}
 <p class="foot">Each lab is self-contained HTML. The cellular automaton does the computing; the browser blits its
 framebuffer and forwards input. Honest scope notes are inside each lab. (Labs are generated locally by the
 <code>build_lab*.py</code> scripts; a “not generated” card just means that file isn’t built on this machine.)
 There is also a <b>pact in a binary</b>: <code>build_pactbundle.py</code> + <code>build_pactelf.py</code> emit
 <code>./notesync</code>, a ~34&nbsp;KB standard Linux ELF that looks like an ordinary note utility but, given the
 key, regenerates the whole CA-OS from its embedded program and serves it to your browser — and in
 <code>host</code>/<code>join</code> mode relays AES-256-GCM-sealed input deltas to a second node (the OS is
 regenerated on both ends; only sealed deltas cross). “Send the entire OS through the pact,” in 64&nbsp;KB.</p>
</div></body></html>"""
    open(out, "w").write(html)
    print("wrote", out, len(html), "bytes;", n, "labs;",
          sum(1 for _, l in GROUPS for fn, _, _ in l if os.path.exists(os.path.join(here, "dissemination", fn))), "present")

if __name__ == "__main__":
    build()
