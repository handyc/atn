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
    ]),
    ("CA-2 — the 32-bit machine", [
        ("glider-lab22.html", "CA-OS/2", "A 32-bit OS (512×384) on the CA-2 machine — launcher + apps."),
        ("glider-lab23.html", "Wide-word CA computer", "Factorials & RSA via BigInt — integers no host register can hold."),
        ("glider-lab24.html", "CA-OS/2 dual-pane", "The full 32-bit suite over the encrypted line: metrics, How-it-works, live CA."),
    ]),
]

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
</style></head><body><div class="wrap">
 <h1>Glider Labs</h1>
 <p class="sub">A computer built out of a cellular automaton, lab by lab — from the hexagonal K=4 rule and its
 gliders, to logic gates and memory, to the CA-1 computer, an operating system, an encrypted “pact” between two
 machines, and finally the 32-bit CA-2 with a full office suite. {n} interactive labs; all run in the browser.</p>
 {''.join(rows)}
 <p class="foot">Each lab is self-contained HTML. The cellular automaton does the computing; the browser blits its
 framebuffer and forwards input. Honest scope notes are inside each lab. (Labs are generated locally by the
 <code>build_lab*.py</code> scripts; a “not generated” card just means that file isn’t built on this machine.)</p>
</div></body></html>"""
    open(out, "w").write(html)
    print("wrote", out, len(html), "bytes;", n, "labs;",
          sum(1 for _, l in GROUPS for fn, _, _ in l if os.path.exists(os.path.join(here, "dissemination", fn))), "present")

if __name__ == "__main__":
    build()
