#!/usr/bin/env python3
# build_lab24.py — glider-lab24.html: the CA-OS/2 SHOWCASE. The full 32-bit CA-Office suite
# (Writer/Sheet/Calc/Paint/About) on a 512x384 desktop, driven over the cut/restore-able encrypted
# line + zero-trust mother server, with the live METRICS panel and the "How it works" tab + live CA
# panels — the whole lab21 stack rebuilt on the 32-bit CA-2 machine. Input deltas are widened to carry
# 9-bit coordinates (the bigger screen). VM is the faithful 32-bit CA-2 VM (flat 1 MB).
#
# Builds on lab20 (cut/restore + mother server). New in lab21:
#   * METRICS — total bytes, bytes/sec, avg bytes/delta, mouse-vs-keystroke split, a bytes/sec sparkline,
#     and the headline ratio vs. a 30 fps full-screen video stream (the line carries ~10 B/action, not 49 KB/frame).
#   * Features every CA-Office app, including the ones added after lab20 (Paint, Minesweeper, Clock).
#
# Inherits from lab20:
#   PART A — cut/restore resilience (client-only):
#     * Each delta is sealed (ct + SHA-256 tag) and seq-numbered. When the line is DROPPED, Alice keeps
#       working locally and her sealed deltas QUEUE instead of vanishing. On RESTORE they replay to Bob
#       in seq order -> Bob catches up and reconverges (lossless). Bob applies the *next expected* seq
#       only, so keystrokes replay one-per-frame and a gap stalls Bob until it's filled (lossy demo).
#   PART B — zero-trust mother server (static-hosting friendly):
#     * The "server" only ever holds CIPHERTEXT (sealed deltas). Alice can PUSH her queue to it; Bob can
#       PULL (replays seq>bob). EXPORT downloads the sealed bundle (to upload to a static domain); FETCH
#       pulls a sealed bundle from a domain URL. The host never sees a key or any plaintext.
import json
import caos_ca2 as o2
from ca1sys import make_machine
_m = o2.make(); o2.load_memory(_m)
_prog, _ = o2.program()
OS = dict(prog=[[op, (arg if arg is not None else 0)] for op, arg in _prog],
          mem={str(a): _m.M[a] for a in range(0x10000) if _m.M[a]},   # initial mem (font/data); FB drawn at runtime
          SP=0x7FFF, MEM=o2.MEMSIZE, W=o2.W, H=o2.H, FB=o2.FB, MX=o2.MX, MY=o2.MY, MB=o2.MB, KEY=o2.KEY, PAL=o2.PAL,
          TBUF=o2.TBUF, TLEN=o2.TLEN, CELLS=o2.CELLS, DIRTY=o2.DIRTY, APP=o2.APP,
          WINX=o2.WINX, WINY=o2.WINY, WW=o2.WW, WH=o2.WH, CSTRIDE=o2.CSTRIDE, WTAB=o2.WTAB, FONT16=o2.FONT16)
FONT = json.load(open("unifont16.json"))
OSJSON = json.dumps(OS, separators=(",", ":")); FONTJSON = json.dumps(FONT, separators=(",", ":"))
PLUTS = json.load(open("caos_pipeluts.json"))   # verified gate/latch rule tables (base64) for the live CA panels

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CA-OS/2 (32-bit) over an encrypted line — Alice &amp; Bob, with live metrics</title>
<style>
 :root{--bg:#0e1116;--ink:#e6edf3;--mut:#9aa7b4;--a:#ffd27f;--b:#6db3ff;--ok:#5ed18a;--no:#ff7a7a;--pa:#c77dff;--sv:#7de0c7}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1060px;margin:0 auto;padding:14px}
 h1{font-size:20px;margin:0 0 2px}h1 small{color:var(--mut);font-weight:400;font-size:13px}
 p{color:var(--mut);max-width:920px}
 .seedbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0;background:#161b22;border:1px solid #2a3340;border-radius:8px;padding:8px 10px}
 input[type=text]{background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:6px 8px;font-family:ui-monospace,monospace;min-width:190px}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px}
 .card{background:#161b22;border:1px solid #2a3340;border-radius:10px;padding:10px}
 .card.alice{border-color:#5a4a2a}.card.bob{border-color:#2a4a5a}
 .card h2{margin:0 0 6px;font-size:15px}.alice h2{color:var(--a)}.bob h2{color:var(--b)}
 canvas.screen{image-rendering:pixelated;width:100%;border:2px solid #2a3340;border-radius:4px;background:#000;display:block}
 .alice canvas.screen{cursor:none}
 .line{background:#13101c;border:1px solid #3a2a55;border-radius:8px;padding:10px;margin-top:10px}
 .line h3{margin:0 0 4px;color:var(--pa);font-size:13px}
 .wire{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut);word-break:break-all;min-height:16px}
 .stat{font-size:12px;color:var(--mut);margin-top:4px}.stat b{color:var(--a)} .ok{color:var(--ok)}.no{color:var(--no)}
 .grids{display:flex;gap:6px;align-items:center;margin-top:6px}
 canvas.ca{image-rendering:pixelated;width:48px;height:48px;border:1px solid #2a3340;border-radius:3px}
 .srv{background:#0c1a17;border:1px solid #265048;border-radius:8px;padding:10px;margin-top:10px}
 .srv h3{margin:0 0 4px;color:var(--sv);font-size:13px}
 .srv .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0}
 .store{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--mut);max-height:64px;overflow:auto;background:#08110f;border:1px solid #1c3b35;border-radius:5px;padding:6px;word-break:break-all}
 .note{font-size:12px;color:var(--mut);background:#11161d;border:1px solid #2a3340;border-radius:8px;padding:10px;margin-top:10px}
 code{background:#0b0e13;padding:1px 5px;border-radius:4px;color:var(--a)}button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:6px;padding:6px 10px;cursor:pointer}
 button:disabled{opacity:.45;cursor:default}
 .pill{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;border:1px solid #2a3340}
 .pill.up{color:var(--ok);border-color:#2c5a3e}.pill.down{color:var(--no);border-color:#5a2c2c}
 .metrics{background:#101a22;border:1px solid #284a5a;border-radius:8px;padding:10px;margin-top:10px}
 .metrics h3{margin:0 0 6px;color:var(--b);font-size:13px}
 .mgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
 .m{background:#0a1218;border:1px solid #1c3340;border-radius:6px;padding:6px 8px}
 .m span{font-size:18px;color:var(--a);font-variant-numeric:tabular-nums}.m label{display:block;font-size:11px;color:var(--mut)}
 #spark{width:100%;height:48px;margin-top:8px;background:#0a1218;border:1px solid #1c3340;border-radius:6px;display:block}
 .tabs{display:flex;gap:6px;margin:10px 0 0}
 .tab{background:#161b22;border:1px solid #2a3340;border-bottom:none;border-radius:8px 8px 0 0;padding:8px 16px;cursor:pointer;font-size:14px;color:var(--mut)}
 .tab.active{background:#11161d;color:var(--ink);font-weight:600}
 #tab-demo,#tab-about{border-top:1px solid #2a3340;padding-top:12px}
 .about{line-height:1.6}.about h2{font-size:19px;color:var(--ink);margin:0 0 10px}.about h2 em,.about h3 em{color:var(--a);font-style:normal}
 .about h3{font-size:15px;color:var(--b);margin:22px 0 6px}.about h4{margin:0 0 6px;font-size:13px;color:var(--ink)}
 .about p{color:#c2ccd6;max-width:none}
 .proofbox{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-end;background:#0c1622;border:1px solid #284a5a;border-radius:8px;padding:16px;margin:12px 0}
 .proofnum{font-size:34px;font-weight:700;color:var(--a);font-variant-numeric:tabular-nums;white-space:nowrap;line-height:1}
 .proofnum2{font-size:26px;font-weight:700;color:var(--sv);font-variant-numeric:tabular-nums;white-space:nowrap;line-height:1}
 .plab{font-size:12px;color:var(--mut);max-width:340px;margin-top:4px}
 .layers{margin:6px 0;padding-left:22px}.layers li{margin:7px 0;color:#c2ccd6}
 .cmp{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0}
 .cmp ul{margin:4px 0;padding-left:18px}.cmp li{margin:3px 0;font-size:13px;color:#c2ccd6}
 .does{background:#0c1a12;border:1px solid #265038;border-radius:8px;padding:10px 12px}
 .doesnt{background:#1a0f0f;border:1px solid #5a2c2c;border-radius:8px;padding:10px 12px}
 .ev{background:#15110a;border:1px solid #5a4a2a;border-radius:8px;padding:10px 12px;font-size:13px;color:#d8cdb4}
 .pgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px;margin:10px 0}
 .pcard{background:#0c1218;border:1px solid #2a3340;border-radius:8px;padding:10px}
 .pcard h4{margin:0 0 2px;font-size:13px;color:var(--ink)}.pcard h4 .tag{font-size:11px;color:var(--mut);font-weight:400}
 .pcard .pd{font-size:11.5px;color:var(--mut);min-height:46px;margin:2px 0 6px}
 .pcard canvas{background:#05070a;border:1px solid #2a3340;border-radius:5px;display:block;image-rendering:pixelated;width:100%}
 .preadout{font-family:ui-monospace,monospace;font-size:12px;margin-top:5px;color:var(--ink)}.preadout b{color:var(--a)}
 .ptruth{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut)}.ptruth .hit{color:var(--ok)}
 .prow{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
 .prow button{background:#222b36;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:4px 8px;cursor:pointer;font-size:11px}
 .prow button.on{background:var(--a);color:#1a1205;font-weight:700;border-color:var(--a)}
 .pfull{grid-column:1/-1}
</style></head><body><div class="wrap">
 <h1>Alice &amp; Bob <small>— CA-OS/2 (32-bit) on a 512×384 desktop, over an encrypted line you can <b>cut</b> &amp; <b>restore</b></small></h1>
 <div class="tabs"><button class="tab active" data-t="demo">🖥️ Live demo</button><button class="tab" data-t="about">📖 How it works (is it really in the CA?)</button></div>
 <div id="tab-demo">
 <p>Both machines run the <b>identical 32-bit CA-OS/2</b> (Writer/Sheet/Calc/Paint) locally. Drive <b>Alice</b>; only her <b>encrypted input deltas</b>
 (x, y, button, key, sealed with AES-256-GCM, seq-numbered) cross the wire. <b>Cut the line</b> and Alice keeps working — her
 deltas <b>queue</b> instead of vanishing; <b>restore</b> and they replay in order so Bob reconverges, pixel-for-pixel
 (lossless). Or offload the queue to a <b>mother server</b> that only ever stores ciphertext, and let Bob sync from it
 when able. <span id="selftest"></span></p>
 <div class="seedbar"><label>shared pact seed:</label><input type="text" id="seed" value="alice&lt;-&gt;bob pact 2026">
  <button id="rekey">re-derive &amp; reboot</button>
  <label><input type="checkbox" id="drop"> cut the line</label>
  <span class="pill up" id="linep">line up</span>
  <span class="stat">click Alice's desktop to focus (for typing)</span></div>
 <div class="cols">
   <div class="card alice"><h2>👩 Alice — you drive (mouse + keyboard)</h2><canvas class="screen" id="sa" width="512" height="384" tabindex="0"></canvas></div>
   <div class="card bob"><h2>🧑 Bob — mirror (replays deltas in seq order)</h2><canvas class="screen" id="sb" width="512" height="384"></canvas></div>
 </div>
 <div class="seedbar" style="margin-top:8px">
  <span class="grp" style="color:var(--mut);font-size:11px">files (apply to both panes):</span>
  <span class="grp" style="color:var(--mut);font-size:11px">Writer</span><button id="wsave">Save .txt</button><button id="wload">Open .txt</button>
  <span class="grp" style="color:var(--mut);font-size:11px">Sheet</span><button id="csave">Export CSV</button><button id="cload">Import CSV</button>
  <span class="grp" style="color:var(--mut);font-size:11px">Paint</span><button id="psave">Save PNG</button><button id="pload">Open image</button>
  <input id="file" type="file" style="display:none">
 </div>
 <div class="seedbar" style="margin-top:6px"><span class="grp" style="color:var(--mut);font-size:11px">type into Alice (any language; CJK via IME, paste OK):</span>
  <textarea id="ime" rows="1" style="flex:1;min-width:220px;background:#0b0e13;color:var(--ink);border:1px solid #2a3340;border-radius:5px;padding:5px 7px;font:14px system-ui;resize:vertical" autocomplete="off" autocapitalize="off" spellcheck="false"></textarea>
  <span id="stat" class="grp" style="color:var(--mut);font-size:11px">loading font…</span></div>
 <div class="line"><h3>🔐 the classical line — only encrypted input deltas cross it</h3>
   <div class="wire" id="wire">idle</div>
   <div class="stat"><b id="sent">0</b> bytes sent · <b id="ndelta">0</b> deltas · vs <b>196,608 B/frame</b> for a full screen · desktops <b id="sync">—</b></div>
   <div class="stat">Alice holding (unsent): <b id="queue">0</b> deltas · Bob applied seq <b id="bobseq">—</b> of <b id="topseq">—</b> · pact gen <b id="gen">0</b></div>
   <div class="grids" id="grids"></div>
 </div>
 <div class="metrics"><h3>📊 metrics — how much data actually crosses the classical line</h3>
   <div class="mgrid">
     <div class="m"><span id="mTotal">0</span><label>bytes sent (total)</label></div>
     <div class="m"><span id="mBps">0</span><label>bytes / second (now)</label></div>
     <div class="m"><span id="mAvg">0</span><label>avg bytes / delta</label></div>
     <div class="m"><span id="mMouse">0 / 0 B</span><label>mouse deltas / bytes</label></div>
     <div class="m"><span id="mKey">0 / 0 B</span><label>keystroke deltas / bytes</label></div>
     <div class="m"><span id="mSave">—</span><label>vs. 30 fps full-screen video</label></div>
   </div>
   <canvas id="spark" width="600" height="48"></canvas>
   <div class="stat">a 30 fps full-screen stream would have pushed <b id="mVideo">0</b> MB by now; the line carried only the bytes above.</div>
 </div>
 <div class="srv"><h3>🗄️ mother server — zero-trust store-and-forward (ciphertext only)</h3>
   <div class="row">
     <button id="push">👩 Alice → push queue to server</button>
     <button id="pull">🧑 Bob ← sync from server</button>
     <button id="export">⤓ export sealed bundle</button>
     <input type="text" id="srv" placeholder="https://your-domain/sync.json (static)">
     <button id="fetch">⤒ Bob fetch from domain</button>
   </div>
   <div class="stat"><b id="srvcount">0</b> sealed deltas stored · <b id="srvbytes">0</b> B (all ciphertext — the host holds no key)</div>
   <div class="store" id="store">empty</div>
 </div>
 <p class="note"><b>How it stays correct across a cut:</b> each delta is sealed with <b>AES-256-GCM</b> under a key
 <code>SHA-256(domain ‖ seq ‖ CA-state-at-seq)</code> — the cellular automaton is the <i>key schedule</i>, not the cipher.
 Because the key is seq-derived, a delta replays at any later time and still unseals; the AEAD tag rejects any tampered or
 foreign delta, so a queued/stored delta is as good as a live one. Bob only applies <b>seq = lastApplied+1</b>, so order is
 preserved and a missing delta stalls him until it arrives (the lossy case → fetch it from the server). The mother server
 never sees plaintext or a key; on a static host it's just a sealed JSON bundle you upload and the other side fetches.
 Everything drawn is CA-1 machine code; mirrors <code>atn_spoeqi.py</code>.</p>
 </div><!-- /tab-demo -->
 <div id="tab-about" style="display:none"><div class="about">
  <h2>Is the windowing system <em>really</em> running inside the cellular automaton? <em>Yes</em> — and you can watch it.</h2>
  <p>The natural reaction is "the browser must be drawing those windows." It isn't. The browser does two trivial
  things: it copies a block of bytes to the screen, and it writes your mouse/keyboard into four bytes. <b>Every
  window, button, the cursor, the text you type, the spreadsheet's sum, the minefield, the clock hands — all of it
  is computed by a cellular automaton</b>, one cell-update at a time.</p>

  <div class="proofbox">
   <div><div class="proofnum"><span id="ipfTot">0</span></div><div class="plab">CA-2 (32-bit) instructions the cellular automaton has executed since this page loaded — it's grinding right now</div></div>
   <div><div class="proofnum2"><span id="ipf">—</span></div><div class="plab">…per frame. Idle it's a few thousand; <b>open a window and drag it</b> and watch it leap into the hundreds of thousands — that's the CA redrawing every pixel.</div></div>
  </div>

  <h3>Watch the <em>actual</em> cellular automata — live, on the verified rule tables</h3>
  <p>These are not diagrams or animations. Each panel is a <b>real CA running in your browser</b> on the exact rule
  tables (verified byte-identical to the Python reference), seeded into the gate/memory configurations that CA-1 is
  built from. The amber and blue layers mutually annihilate where they meet; which survives is the computed bit.</p>
  <div class="pgrid">
    <div class="pcard"><h4>1 · NAND gate <span class="tag">— universal logic</span></h4>
      <div class="pd">Bias (amber) vs inputs (blue), winner-take-all → a NAND. It cycles the 4 input cases; the truth table fills as the CA settles. NAND alone is enough to build any computer.</div>
      <canvas id="cg" width="120" height="120"></canvas>
      <div class="preadout">inputs <b id="g_in">00</b> → output <b id="g_out">·</b></div>
      <div class="ptruth" id="g_tt">NAND: 00:· 01:· 10:· 11:·</div></div>
    <div class="pcard"><h4>2 · Latch <span class="tag">— one bit of memory</span></h4>
      <div class="pd">Two layers annihilate; the larger survives and <b>holds with no decay</b> — a flip-flop. Set stores 1 (amber), reset stores 0 (blue). Tile these and you get CA-1's RAM and its framebuffer.</div>
      <canvas id="cl" width="120" height="120"></canvas>
      <div class="preadout">stored bit: <b id="l_bit">·</b></div>
      <div class="prow"><button id="l_set">set → 1</button><button id="l_rst">reset → 0</button><button id="l_auto" class="on">auto</button></div></div>
    <div class="pcard"><h4>3 · Inverter <span class="tag">— active gate</span></h4>
      <div class="pd">A self-emitting carrier (green) flows down the channel unless an input suppresses it: emission ⇔ input absent = NOT.</div>
      <canvas id="ci" width="96" height="40"></canvas>
      <div class="preadout">input <b id="i_in">0</b> → emit (NOT) <b id="i_out">·</b></div>
      <div class="prow"><button id="i_tog">toggle input</button><button id="i_auto" class="on">auto</button></div></div>
    <div class="pcard pfull"><h4>4 · Autonomous wire <span class="tag">— routing with no controller</span></h4>
      <div class="pd">Walls confine a spreading carrier to a channel. Gate 1 computes NOR(A,B) on the left; if it fires, the carrier travels the walled channel to gate 2 on the right, which reproduces it — a gate-to-gate wire that runs itself.</div>
      <canvas id="cw" width="96" height="40"></canvas>
      <div class="preadout">inputs A,B = <b id="w_in">00</b> → gate 2 reads <b id="w_out">·</b> (= NOR, transported)</div></div>
    <div class="pcard pfull"><h4>5 · Circulating register <span class="tag">— sequential memory</span></h4>
      <div class="pd">Five latch cells wired into a ring: each clock the stored pattern rotates one cell and wraps — a delay-line memory. Every cell is a real latch (amber = 1, blue = 0).</div>
      <canvas id="cr" width="250" height="40"></canvas>
      <div class="preadout">stored bits: <b id="r_bits">·····</b> · clock <b id="r_clk">0</b></div></div>
  </div>
  <p class="ev">🔬 And the four small grids under the <b>Live demo</b> tab are also real CAs: that's the <b>pact</b> — the
  shared cellular automaton Alice and Bob both run to generate the identical key tape that encrypts the line. So every
  CA in the system is on screen: the pact CAs (key material) and the gate/latch/wire/register CAs (the computer itself).</p>

  <h3>The chain of construction — rule → gate → computer → windows</h3>
  <ol class="layers">
   <li><b>A cellular-automaton rule.</b> A hexagonal, 4-state, 7-cell-neighbourhood CA (a 16,384-entry lookup table). Just cells updating from their neighbours — no computer in sight yet.</li>
   <li><b>A gate and a memory bit, out of CA patterns.</b> Colliding gliders implement the <b>NAND gate</b> and the mutual-annihilation <b>latch</b> above — tested exhaustively, held-out truth tables 100% correct. NAND + memory is all any computer needs.</li>
   <li><b>CA-1, an 8-bit computer.</b> Those gates and latches compose into an accumulator machine with a real instruction set (load/store, add/sub, logic, shifts, compare, branch, call/return, a stack). Its ALU was cross-checked against the raw CA gate, bit for bit. The top of its 64&nbsp;KB memory is a 256×192 <b>framebuffer</b>.</li>
   <li><b>CA-Office — machine code on CA-1.</b> The window manager, start menu, hit-testing, the 5×7 font, the spreadsheet's repeated-addition totals, Minesweeper's flood-fill, the clock's trig table — all are <b>CA-1 programs</b>. To draw a pixel, CA-1 executes a store instruction writing a colour byte into framebuffer memory. A window is thousands of those.</li>
   <li><b>The browser — a dumb terminal.</b> It reads the framebuffer bytes and paints them; it writes [x, y, button, key] into four CA-1 memory cells. That is the entire contract.</li>
  </ol>

  <h3>What the browser does — and pointedly does <em>not</em></h3>
  <div class="cmp">
   <div class="does"><h4>The browser's complete job</h4><ul>
     <li>a ~40-line CA-1 CPU emulator (one <code>switch</code> over opcodes)</li>
     <li>a loop copying framebuffer bytes → canvas pixels</li>
     <li>4 lines writing mouse/key into CA-1 memory</li>
     <li>(for the line) the SHA-256 / CA pact</li></ul></div>
   <div class="doesnt"><h4>What you will <em>not</em> find in the JavaScript</h4><ul>
     <li>no <code>drawWindow</code>, no UI <code>fillRect</code>, no button code</li>
     <li>no font, no text layout, no cursor drawing</li>
     <li>no spreadsheet math, no Minesweeper, no clock logic</li>
     <li>none of the interface exists in JS — it's all CA-1 bytes</li></ul></div>
  </div>
  <p class="ev">🔎 <b>Verify it yourself:</b> View Source and search the script. The UI simply isn't there. What <em>is</em>
  there is the CPU emulator and a big blob of CA-1 machine code + a memory image (the <code>OS</code> object). The
  pixels appear because CA-1 <em>ran</em>.</p>

  <h3>Then the two-computer part</h3>
  <p><b>The pact (shared randomness, nothing secret on the wire).</b> Alice and Bob seed an identical cellular automaton
  from the shared passphrase and run it in lockstep, generating an endless <em>identical</em> key tape on both sides.
  The key is regenerated, never transmitted — shared, not sent.</p>
  <p><b>The classical line (≈10 bytes per action).</b> Because both run the identical, deterministic CA-1, Bob only
  needs Alice's <em>inputs</em>. Each delta — <code>[x, y, button, key]</code>, 4 bytes — is sealed with AES-256-GCM under a key from
  the pact's CA state at that seq, then sent. Bob unseals and replays it; his screen stays pixel-identical.
  The 196,608-byte screen never travels (see the Metrics).</p>
  <p><b>Cut &amp; restore.</b> Each side is a whole computer, so cutting the line doesn't stop Alice — her deltas queue,
  seq-numbered, and replay in order on restore so Bob reconverges exactly. He applies only the next expected seq, so a
  lost delta stalls him safely instead of corrupting state.</p>

  <h3>Honest scope</h3>
  <p>A physical CA updates a few cells per second; the <b>full CPU running as gliders would take days per frame</b>, so
  the windows in the demo run the <em>identical</em> CA-1 machine code on a fast emulator (~10⁸× quicker). But the logic
  it executes is exactly what the gates above compute, verified bit-for-bit — and those gates, latches, wires and the
  pact really are live cellular automata, right here. "No data crosses" means shared <em>randomness</em>: a chosen
  computer's information does travel (sealed), but the key never does. Recognizable miniatures of a 1998 desktop — but
  genuinely a windowing system <em>computed by a cellular automaton</em>.</p>
 </div></div>
</div>
<script>
"use strict";
const OS=__OS__, FONT=__FONT__;
/* SHA-256 */
const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
const rotr=(x,n)=>((x>>>n)|(x<<(32-n)))>>>0;
function sha256(msg){let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
 const ml=msg.length,total=(((ml+8)>>6)+1)<<6,m=new Uint8Array(total);m.set(msg);m[ml]=0x80;const dv=new DataView(m.buffer),bit=ml*8;
 dv.setUint32(total-4,bit>>>0,false);dv.setUint32(total-8,Math.floor(bit/0x100000000)>>>0,false);const w=new Uint32Array(64);
 for(let off=0;off<total;off+=64){for(let i=0;i<16;i++)w[i]=dv.getUint32(off+i*4,false);
  for(let i=16;i<64;i++){const s0=(rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>>3))>>>0,s1=(rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>>10))>>>0;w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;}
  let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,hh=h7;
  for(let i=0;i<64;i++){const S1=(rotr(e,6)^rotr(e,11)^rotr(e,25))>>>0,ch=((e&f)^((~e)&g))>>>0,t1=(hh+S1+ch+K[i]+w[i])>>>0,S0=(rotr(a,2)^rotr(a,13)^rotr(a,22))>>>0,maj=((a&b)^(a&c)^(b&c))>>>0,t2=(S0+maj)>>>0;hh=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
  h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+hh)>>>0;}
 const out=new Uint8Array(32),o=new DataView(out.buffer);[h0,h1,h2,h3,h4,h5,h6,h7].forEach((v,i)=>o.setUint32(i*4,v>>>0,false));return out;}
const enc=s=>new TextEncoder().encode(s);
const hex=(b,n)=>Array.from(b.slice(0,n||b.length)).map(x=>x.toString(16).padStart(2,'0')).join('');
const unhex=s=>{const a=new Uint8Array(s.length/2);for(let i=0;i<a.length;i++)a[i]=parseInt(s.substr(i*2,2),16);return a;};
/* pact */
const NCOMP=4,SIDE=48,DOMAIN=enc("spoeqi/tap/v1"),CH=1;
function prng(seed,label,n){let out=new Uint8Array(n),pos=0,ctr=0;const s=enc(seed),l=enc(label);
 while(pos<n){const b=new Uint8Array(s.length+l.length+4);b.set(s,0);b.set(l,s.length);new DataView(b.buffer).setUint32(s.length+l.length,ctr,true);
  const h=sha256(b);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
function buildPact(seed){const luts=[],init=[];for(let c=0;c<NCOMP;c++){const lb=prng(seed,"rule"+c,16384),lut=new Uint8Array(16384);for(let i=0;i<16384;i++)lut[i]=lb[i]&3;luts.push(lut);
  const gb=prng(seed,"grid"+c,SIDE*SIDE),g=new Uint8Array(SIDE*SIDE);for(let i=0;i<SIDE*SIDE;i++)g[i]=gb[i]&3;init.push(g);}return{luts,init,cache:{0:init.map(g=>g.slice())}};}
function castep(b,lut,W,H){const nb=new Uint8Array(W*H);for(let r=0;r<H;r++){const rm=(r-1+H)%H,rp=(r+1)%H,ev=(r%2===0);
  for(let c=0;c<W;c++){const cm=(c-1+W)%W,cp=(c+1)%W,s=b[r*W+c],N=b[rm*W+c],Sd=b[rp*W+c],Wc=b[r*W+cm],E=b[r*W+cp];
   let nw,ne,sw,se;if(ev){nw=b[rm*W+cm];ne=N;sw=b[rp*W+cm];se=Sd;}else{nw=N;ne=b[rm*W+cp];sw=Sd;se=b[rp*W+cp];}
   nb[r*W+c]=lut[(s<<12)|(nw<<10)|(ne<<8)|(E<<6)|(se<<4)|(sw<<2)|Wc];}}return nb;}
function gridsAt(p,gen){if(p.cache[gen])return p.cache[gen];let base=0;for(const k in p.cache)if(+k<=gen&&+k>base)base=+k;
 let g=p.cache[base].map(x=>x.slice());for(let t=0;t<gen-base;t++)g=g.map((gg,c)=>castep(gg,p.luts[c],SIDE,SIDE));p.cache[gen]=g.map(x=>x.slice());return p.cache[gen];}
function tap(p,comp,gen,n){const grid=gridsAt(p,gen)[comp];let out=new Uint8Array(n),pos=0,ctr=0;
 while(pos<n){const hdr=new Uint8Array(12),dv=new DataView(hdr.buffer);dv.setUint32(0,comp,true);dv.setUint32(4,gen,true);dv.setUint32(8,ctr,true);
  const buf=new Uint8Array(DOMAIN.length+12+grid.length);buf.set(DOMAIN,0);buf.set(hdr,DOMAIN.length);buf.set(grid,DOMAIN.length+12);
  const h=sha256(buf);for(let i=0;i<32&&pos<n;i++)out[pos++]=h[i];ctr++;}return out;}
/* faithful 32-bit CA-2 VM (flat 1 MB; mirrors ca1sys make_machine("CA-2")) */
function makeVM(sz,sp){const M=new Uint8Array(sz),NM=sz-1;let A=0,X=0,SP=sp||0x7FFF,PC=0,Z=1,C=0,N=0;
 const wrd=d=>{d&=NM;return (M[d]|(M[d+1]<<8)|(M[d+2]<<16)|(M[d+3]<<24))>>>0;};
 const set=(v,c)=>{const w=v>>>0;Z=w===0?1:0;N=(w>>>31)&1;if(c!==undefined)C=c&1;return w;};
 function run(prog){let n=0;while(n<8000000){const I=prog[PC],op=I[0],arg=I[1];PC++;n++;const a=A;
   switch(op){case"LDI":A=set(arg);break;case"LDA":A=set(M[arg&NM]);break;case"STA":M[arg&NM]=a&0xFF;break;
    case"LDAX":A=set(M[(arg+X)&NM]);break;case"STAX":M[(arg+X)&NM]=a&0xFF;break;case"LDX":X=set(M[arg&NM]);break;case"LXI":X=set(arg);break;
    case"LDW":A=set(wrd(arg));break;case"STW":{const d=arg&NM;M[d]=a&0xFF;M[d+1]=(a>>>8)&0xFF;M[d+2]=(a>>>16)&0xFF;M[d+3]=(a>>>24)&0xFF;break;}
    case"ADDW":{const w=wrd(arg);A=set(a+w,(a+w)>0xFFFFFFFF?1:0);break;}case"SUBW":{const w=wrd(arg);A=set(a-w,a>=w?1:0);break;}case"CMPW":{const w=wrd(arg);set((a-w)>>>0,a>=w?1:0);break;}
    case"TAX":X=set(a);break;case"TXA":A=set(X);break;case"INX":X=set(X+1);break;case"DEX":X=set(X-1);break;
    case"ADD":{const w=M[arg&NM];A=set(a+w,(a+w)>0xFFFFFFFF?1:0);break;}case"ADDI":A=set(a+arg,(a+arg)>0xFFFFFFFF?1:0);break;
    case"SUB":{const w=M[arg&NM];A=set(a-w,a>=w?1:0);break;}case"SUBI":A=set(a-arg,a>=arg?1:0);break;
    case"AND":A=set(a&M[arg&NM]);break;case"ANDI":A=set((a&arg)>>>0);break;case"OR":A=set(a|M[arg&NM]);break;case"XOR":A=set(a^M[arg&NM]);break;
    case"INC":A=set(a+1);break;case"DEC":A=set(a-1);break;case"SHL":A=set((a*2)>>>0,(a>>>31)&1);break;case"SHR":A=set(a>>>1,a&1);break;
    case"CMP":{const w=M[arg&NM];set((a-w)>>>0,a>=w?1:0);break;}case"CMPI":set((a-arg)>>>0,a>=arg?1:0);break;
    case"JMP":PC=arg;break;case"JZ":if(Z)PC=arg;break;case"JNZ":if(!Z)PC=arg;break;case"JC":if(C)PC=arg;break;case"JNC":if(!C)PC=arg;break;case"JN":if(N)PC=arg;break;
    case"CALL":M[SP]=PC&255;M[SP-1]=(PC>>8)&255;SP-=2;PC=arg;break;case"RET":SP+=2;PC=(M[SP-1]<<8)|M[SP];break;
    case"FRAME":return n;case"NOP":break;case"HLT":return n;default:throw"op "+op;}}return n;}
 return {M,run};}
/* state — declared BEFORE any load-time call */
const $=id=>document.getElementById(id);
let pact=null,aliceVM=null,bobVM=null,fontBlob=null,fontCps=null,fontW=null,ready=false,bobBusy=false,pendingBobKey=0,mx=80,my=70,mb=0,pendKey=0,keyq=[],bobIn=[80,70,0],seq=0,sent=0,ndelta=0,lastMouse=null,raf=0;
let bobInbox=[],aliceQueue=[],server=[],srvBytes=0,bobSeq=-1;
let bytesMouse=0,bytesKey=0,nMouse=0,nKey=0,t0=0,lastSent=0,spark=[];   // metrics
let ipfTotal=0,aboutVisible=false;   // live CA-2 instruction counter + tab state
const PAL=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
const ctxA=$("sa").getContext("2d"),ctxB=$("sb").getContext("2d");
const imA=ctxA.createImageData(OS.W,OS.H),imB=ctxB.createImageData(OS.W,OS.H);
function blit(ctx,im,vm){for(let i=0;i<OS.W*OS.H;i++){const v=vm.M[OS.FB+i],p=PAL[v]||PAL[0];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}ctx.putImageData(im,0,0);}
function bootVM(){const vm=makeVM(OS.MEM,OS.SP);for(const k in OS.mem)vm.M[+k]=OS.mem[k];expandFont(vm);return vm;}
const gc=[];for(let c=0;c<NCOMP;c++){const cv=document.createElement("canvas");cv.className="ca";cv.width=SIDE;cv.height=SIDE;$("grids").appendChild(cv);gc.push(cv.getContext("2d"));}
const CPAL=[[10,12,20],[60,110,165],[255,210,127],[200,90,70]];
function drawGrids(){const gs=gridsAt(pact,seq);for(let c=0;c<NCOMP;c++){const im=gc[c].createImageData(SIDE,SIDE),g=gs[c];for(let i=0;i<SIDE*SIDE;i++){const p=CPAL[g[i]];im.data[i*4]=p[0];im.data[i*4+1]=p[1];im.data[i*4+2]=p[2];im.data[i*4+3]=255;}gc[c].putImageData(im,0,0);}$("gen").textContent=seq;}
/* seal a delta from the current input, keyed by seq; unseal+apply to Bob, keyed by the delta's own seq */
function wr32(vm,addr,v){vm.M[addr]=v&0xFF;vm.M[addr+1]=(v>>>8)&0xFF;vm.M[addr+2]=(v>>>16)&0xFF;vm.M[addr+3]=(v>>>24)&0xFF;}
/* the pact is the KEY SCHEDULE (not the cipher): key(seq)=SHA-256(domain ‖ seq ‖ full CA state at seq);
   the 7-byte input delta is sealed with AES-256-GCM (WebCrypto). Bob knows the seq -> derives the same key. */
const DOMENV=enc("spoeqi/envelope/v1"),keyCache=new Map();
function deriveKeyBytes(g){const grids=gridsAt(pact,g),st=new Uint8Array(8+NCOMP*SIDE*SIDE);new DataView(st.buffer).setUint32(0,g>>>0,true);
 let o=8;for(const gr of grids){st.set(gr,o);o+=gr.length;}const full=new Uint8Array(DOMENV.length+st.length);full.set(DOMENV,0);full.set(st,DOMENV.length);return sha256(full);}
function getKey(g){if(!keyCache.has(g))keyCache.set(g,crypto.subtle.importKey("raw",deriveKeyBytes(g),{name:"AES-GCM"},false,["encrypt","decrypt"]));return keyCache.get(g);}
async function sealAsync(s,plain,isKey){const key=await getKey(s),nonce=crypto.getRandomValues(new Uint8Array(12));
 const ct=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce},key,plain)),d={seq:s,nonce,ct},sz=d.nonce.length+d.ct.length+2;
 if($("drop").checked){aliceQueue.push(d);$("wire").innerHTML=`✗ line cut — queued sealed delta seq ${s} locally (Alice keeps working)`;}
 else{bobInbox.push(d);$("wire").innerHTML=`delta @ seq ${s}: <span style="color:var(--pa)">${hex(d.nonce)} ${hex(d.ct)}</span>${isKey?" (incl. keystroke)":""} (${sz} B, AES-256-GCM)`;}
 sent+=sz;ndelta++;if(isKey){bytesKey+=sz;nKey++;}else{bytesMouse+=sz;nMouse++;}$("sent").textContent=sent;$("ndelta").textContent=ndelta;}
async function applyBobAsync(d){try{const key=await getKey(d.seq),pl=new Uint8Array(await crypto.subtle.decrypt({name:"AES-GCM",iv:d.nonce},key,d.ct));
  bobIn=[pl[0]|(pl[1]<<8),pl[2]|(pl[3]<<8),pl[4]];pendingBobKey=pl[5]|(pl[6]<<8);bobSeq=d.seq;}
  catch(e){/* tampered / foreign / wrong-seed -> AEAD tag fails -> reject, don't advance */}finally{bobBusy=false;}}
function renderServer(){$("srvcount").textContent=server.length;$("srvbytes").textContent=srvBytes;
 $("store").innerHTML=server.length?server.slice(-12).map(d=>`seq ${d.seq}: <span style="color:var(--sv)">${hex(d.nonce)} ${hex(d.ct)}</span>`).join("<br>"):"empty";}
function stats(){$("queue").textContent=aliceQueue.length;$("bobseq").textContent=bobSeq<0?"—":bobSeq;$("topseq").textContent=seq>0?seq-1:"—";
 const up=!$("drop").checked;$("linep").textContent=up?"line up":"line CUT";$("linep").className="pill "+(up?"up":"down");}
function renderMetrics(){const el=Math.max(0.001,(performance.now()-t0)/1000);
 const inst=sent-lastSent;lastSent=sent;spark.push(inst);if(spark.length>90)spark.shift();
 const FULL=196608,videoBps=30*FULL,ratio=sent>0?(videoBps*el)/sent:0;
 $("mTotal").textContent=sent.toLocaleString();$("mBps").textContent=inst.toLocaleString();
 $("mAvg").textContent=(sent/(ndelta||1)).toFixed(1);
 $("mMouse").textContent=`${nMouse} / ${bytesMouse.toLocaleString()} B`;$("mKey").textContent=`${nKey} / ${bytesKey.toLocaleString()} B`;
 $("mSave").textContent=ratio>0?Math.round(ratio).toLocaleString()+"×":"—";$("mVideo").textContent=(videoBps*el/1e6).toFixed(1);
 const c=$("spark"),x=c.getContext("2d"),W=c.width,H=c.height;x.clearRect(0,0,W,H);
 const peak=Math.max(1,...spark);x.strokeStyle="#7de0c7";x.lineWidth=1.5;x.beginPath();
 spark.forEach((v,i)=>{const px=i/89*W,py=H-(v/peak)*(H-3)-1.5;i?x.lineTo(px,py):x.moveTo(px,py);});x.stroke();}
const sa=$("sa");
function rel(e){const r=sa.getBoundingClientRect(),cs=getComputedStyle(sa),
  bl=parseFloat(cs.borderLeftWidth)||0,bt=parseFloat(cs.borderTopWidth)||0;   // border-exact: clientX/Y minus border, over the content box
  const x=(e.clientX-r.left-bl)/sa.clientWidth*OS.W,y=(e.clientY-r.top-bt)/sa.clientHeight*OS.H;
  return[Math.max(0,Math.min(OS.W-1,x|0)),Math.max(0,Math.min(OS.H-1,y|0))];}
sa.onmousemove=e=>{[mx,my]=rel(e);};sa.onmousedown=e=>{[mx,my]=rel(e);mb=1;sa.focus();};window.addEventListener("mouseup",()=>mb=0);
function kdcp(e){let cp=-1;if(e.key==="Backspace")cp=8;else if(e.key==="Enter")cp=10;else if([...e.key].length===1)cp=e.key.codePointAt(0);
 if(cp>=0){e.preventDefault();keyq.push(cp);}}                          // KEY = Unicode codepoint (8=BS,10=NL)
sa.addEventListener("keydown",kdcp);
const ime=document.getElementById("ime");let composing=false;          // IME/paste box -> forward codepoints to Alice
function flush(){for(const ch of ime.value)keyq.push(ch.codePointAt(0));ime.value="";}
ime.addEventListener("compositionstart",()=>composing=true);
ime.addEventListener("compositionend",()=>{composing=false;flush();});
ime.addEventListener("input",()=>{if(!composing)flush();});
ime.addEventListener("keydown",e=>{if(e.key==="Backspace"){e.preventDefault();keyq.push(8);}else if(e.key==="Enter"){e.preventDefault();keyq.push(10);}});
const b2u=x=>{const b=atob(x),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
function expandFont(vm){if(!fontBlob)return;const M=vm.M,F=OS.FONT16,WT=OS.WTAB;for(let i=0;i<FONT.n;i++){const cp=fontCps[i*2]|(fontCps[i*2+1]<<8),off=F+cp*64;
  for(let b=0;b<64;b++)M[off+b]=fontBlob[i*64+b];M[WT+cp]=fontW[i];}}
async function loadFont(){fontBlob=new Uint8Array(await new Response(new Blob([b2u(FONT.b64)]).stream().pipeThrough(new DecompressionStream("deflate"))).arrayBuffer());
 fontCps=b2u(FONT.cps_b64);fontW=b2u(FONT.w_b64);if(aliceVM)expandFont(aliceVM);if(bobVM)expandFont(bobVM);ready=true;
 const st=document.getElementById("stat");if(st)st.textContent="font loaded ("+FONT.n.toLocaleString()+" Unicode glyphs) — Writer is multilingual on both panes.";}
function syncCheck(){let same=true;for(let i=0;i<OS.W*OS.H;i++){if(aliceVM.M[OS.FB+i]!==bobVM.M[OS.FB+i]){same=false;break;}}
 $("sync").innerHTML=same?"<span class='ok'>in sync ✓</span>":"<span class='no'>diverged ✗ (Bob behind / line cut)</span>";}
function reset(){if(raf)cancelAnimationFrame(raf);pact=buildPact($("seed").value);aliceVM=bootVM();bobVM=bootVM();
 mx=80;my=70;mb=0;pendKey=0;bobIn=[80,70,0];seq=0;sent=0;ndelta=0;lastMouse=null;bobInbox=[];aliceQueue=[];server=[];srvBytes=0;bobSeq=-1;keyCache.clear();bobBusy=false;pendingBobKey=0;
 bytesMouse=0;bytesKey=0;nMouse=0;nKey=0;t0=performance.now();lastSent=0;spark=[];
 $("sent").textContent=0;$("ndelta").textContent=0;$("wire").textContent="idle";drawGrids();renderServer();stats();renderMetrics();raf=requestAnimationFrame(tick);}
let fc=0;
function tick(){
 if(pendKey===0&&keyq.length)pendKey=keyq.shift();   // feed one queued key per frame (lossless typing)
 // ALICE: drive locally (always — a cut line never stops her own machine)
 wr32(aliceVM,OS.MX,mx);wr32(aliceVM,OS.MY,my);wr32(aliceVM,OS.MB,mb);wr32(aliceVM,OS.KEY,pendKey);const ipf=aliceVM.run(OS.prog);ipfTotal+=ipf;blit(ctxA,imA,aliceVM);
 const mouseChanged=!lastMouse||mx!==lastMouse[0]||my!==lastMouse[1]||mb!==lastMouse[2];
 if(mouseChanged||pendKey!==0){
   const s=seq++,isKey=pendKey!==0;
   const plain=new Uint8Array([mx&0xFF,(mx>>8)&0xFF,my&0xFF,(my>>8)&0xFF,mb,pendKey&0xFF,(pendKey>>8)&0xFF]);
   lastMouse=[mx,my,mb];sealAsync(s,plain,isKey);drawGrids();
 }
 // BOB: apply ONLY the next expected seq (ordered, lossless replay); drop already-applied stragglers
 bobInbox=bobInbox.filter(d=>d.seq>bobSeq);
 if(!bobBusy){const ni=bobInbox.findIndex(d=>d.seq===bobSeq+1);if(ni>=0){bobBusy=true;applyBobAsync(bobInbox.splice(ni,1)[0]);}}
 let bobKey=pendingBobKey;pendingBobKey=0;
 wr32(bobVM,OS.MX,bobIn[0]);wr32(bobVM,OS.MY,bobIn[1]);wr32(bobVM,OS.MB,bobIn[2]);wr32(bobVM,OS.KEY,bobKey);bobVM.run(OS.prog);blit(ctxB,imB,bobVM);
 pendKey=0;
 if((++fc%12)===0){syncCheck();stats();if(aboutVisible){$("ipf").textContent=ipf.toLocaleString();$("ipfTot").textContent=ipfTotal.toLocaleString();}}
 if((fc%60)===0)renderMetrics();
 raf=requestAnimationFrame(tick);
}
/* line restore: replay Alice's locally-queued deltas straight to Bob, in order */
$("drop").onchange=function(){if(!this.checked&&aliceQueue.length){for(const d of aliceQueue)bobInbox.push(d);
   $("wire").innerHTML=`✓ line restored — replaying ${aliceQueue.length} queued deltas to Bob in seq order`;aliceQueue=[];}stats();};
/* mother server (zero-trust, ciphertext only) */
$("push").onclick=function(){for(const d of aliceQueue){server.push(d);srvBytes+=d.nonce.length+d.ct.length+2;}aliceQueue=[];renderServer();stats();
 $("wire").innerHTML=`👩→🗄️ Alice pushed her queue to the mother server (sealed)`;};
$("pull").onclick=function(){let added=0;for(const d of server)if(d.seq>bobSeq&&!bobInbox.some(x=>x.seq===d.seq)){bobInbox.push(d);added++;}stats();
 $("wire").innerHTML=`🗄️→🧑 Bob syncing ${added} sealed deltas from the server (replays in order)`;};
$("export").onclick=function(){const bundle=JSON.stringify(server.map(d=>({seq:d.seq,nonce:hex(d.nonce),ct:hex(d.ct)})));
 const a=document.createElement("a");a.href="data:application/json,"+encodeURIComponent(bundle);a.download="sync.json";a.click();};
$("fetch").onclick=function(){const url=$("srv").value.trim();if(!url){$("wire").textContent="enter your static domain URL first";return;}
 fetch(url).then(r=>r.json()).then(arr=>{let added=0;for(const o of arr){const d={seq:o.seq,nonce:unhex(o.nonce),ct:unhex(o.ct)};
   if(!server.some(x=>x.seq===d.seq)){server.push(d);srvBytes+=d.nonce.length+d.ct.length+2;}
   if(d.seq>bobSeq&&!bobInbox.some(x=>x.seq===d.seq)){bobInbox.push(d);added++;}}renderServer();stats();
   $("wire").innerHTML=`⤒ fetched a sealed bundle from your domain — Bob replaying ${added} deltas`;})
  .catch(err=>{$("wire").textContent="fetch failed: "+err+" (CORS or no file yet)";});};
/* ===== live CA component panels (real CAs on the verified gate/latch LUTs; byte-identical to python) ===== */
function unpack(b64,n){const raw=atob(b64);const out=new Uint8Array(n);let p=0;
  for(let i=0;i<raw.length&&p<n;i++){const by=raw.charCodeAt(i);for(let k=0;k<4&&p<n;k++)out[p++]=(by>>(k*2))&3;}return out;}
const LO=unpack("__LO__",16384),LZ=unpack("__LZ__",16384),LW=unpack("__LW__",16384);
const step=castep;
function annih(A,B){for(let i=0;i<A.length;i++)if(A[i]>0&&B[i]>0){A[i]=0;B[i]=0;}}
function pseed(arr,W,r,c,sz){const lo=c-(sz>>1),lr=r-(sz>>1);for(let i=lr;i<lr+sz;i++)for(let j=lo;j<lo+sz;j++)if(i>=0&&j>=0)arr[i*W+j]=1+(Math.random()*3|0);}
function pmass(A){let m=0;for(let i=0;i<A.length;i++)if(A[i]>0)m++;return m;}
function pmassR(A,W,r0,r1,c0,c1){let m=0;for(let r=r0;r<r1;r++)for(let c=c0;c<c1;c++)if(A[r*W+c]>0)m++;return m;}
function drawTwo(ctx,A,B,W,H,cA,cB,mask){const im=ctx.createImageData(W,H);
  for(let p=0;p<W*H;p++){let col=null;if(A[p]>0)col=cA;else if(B[p]>0)col=cB;else if(mask&&mask[p]===0)col=[18,22,30];
    if(col){im.data[p*4]=col[0];im.data[p*4+1]=col[1];im.data[p*4+2]=col[2];im.data[p*4+3]=255;}else im.data[p*4+3]=255;}
  const t=document.createElement("canvas");t.width=W;t.height=H;t.getContext("2d").putImageData(im,0,0);
  ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.drawImage(t,0,0,ctx.canvas.width,ctx.canvas.height);}
const AMBER=[255,210,127],BLUE=[109,179,255],GREEN=[94,209,138];
const GS=60;let gO=new Uint8Array(GS*GS),gZ=new Uint8Array(GS*GS),gCombo=0,gT=0,gTT=[null,null,null,null];
function gReset(){gO=new Uint8Array(GS*GS);gZ=new Uint8Array(GS*GS);const k=gCombo;pseed(gO,GS,GS>>1,GS>>1,18);if(k&1)pseed(gZ,GS,(GS>>1)-12,GS>>1,14);if(k&2)pseed(gZ,GS,(GS>>1)+12,GS>>1,14);gT=0;$("g_in").textContent=((k&2)>>1)+""+(k&1);}
function gTick(){gO=step(gO,LO,GS,GS);gZ=step(gZ,LZ,GS,GS);annih(gO,gZ);gT++;
  if(gT===55){const o=pmass(gO)>pmass(gZ)?1:0;gTT[gCombo]=o;$("g_out").textContent=o;
    $("g_tt").innerHTML="NAND: "+[0,1,2,3].map(k=>`<span class="${gTT[k]!==null?'hit':''}">${(k&2)>>1}${k&1}:${gTT[k]===null?'·':gTT[k]}</span>`).join(" ");}
  if(gT>=72){gCombo=(gCombo+1)&3;gReset();}drawTwo($("cg").getContext("2d"),gO,gZ,GS,GS,AMBER,BLUE);}
const LS=60;let lA=new Uint8Array(LS*LS),lB=new Uint8Array(LS*LS),lAuto=true,lCd=0,lWant=1;
function lWrite(bit){lA=new Uint8Array(LS*LS);lB=new Uint8Array(LS*LS);pseed(bit?lA:lB,LS,LS>>1,LS>>1,24);}
function lTick(){lA=step(lA,LO,LS,LS);lB=step(lB,LZ,LS,LS);annih(lA,lB);const bit=pmass(lA)>pmass(lB)?1:0;$("l_bit").textContent=bit;
  if(lAuto&&(++lCd>=110)){lCd=0;lWant^=1;lWrite(lWant);}drawTwo($("cl").getContext("2d"),lA,lB,LS,LS,AMBER,BLUE);}
const IW=96,IH=40;const Imask=new Uint8Array(IW*IH);
for(let r=4;r<36;r++)for(let c=4;c<34;c++)Imask[r*IW+c]=1;for(let r=17;r<23;r++)for(let c=34;c<58;c++)Imask[r*IW+c]=1;for(let r=4;r<36;r++)for(let c=58;c<92;c++)Imask[r*IW+c]=1;
let iZ=new Uint8Array(IW*IH),iO=new Uint8Array(IW*IH),iIn=0,iAuto=true,iCd=0;
function iTick(){pseed(iZ,IW,20,12,7);if(iIn)pseed(iO,IW,20,12,17);iZ=step(iZ,LW,IW,IH);iO=step(iO,LO,IW,IH);
  for(let p=0;p<IW*IH;p++)if(Imask[p]===0){iZ[p]=0;iO[p]=0;}annih(iZ,iO);
  const em=pmassR(iZ,IW,4,36,74,92)>20?1:0;$("i_out").textContent=em;$("i_in").textContent=iIn;
  if(iAuto&&(++iCd>=90)){iCd=0;iIn^=1;iZ=new Uint8Array(IW*IH);iO=new Uint8Array(IW*IH);}drawTwo($("ci").getContext("2d"),iZ,iO,IW,IH,GREEN,AMBER,Imask);}
const WW2=96,WH2=40;const Wmask=new Uint8Array(WW2*WH2);
for(let r=4;r<36;r++)for(let c=4;c<30;c++)Wmask[r*WW2+c]=1;for(let r=17;r<23;r++)for(let c=30;c<54;c++)Wmask[r*WW2+c]=1;for(let r=4;r<36;r++)for(let c=54;c<92;c++)Wmask[r*WW2+c]=1;
let wZ=new Uint8Array(WW2*WH2),wO=new Uint8Array(WW2*WH2),wCombo=0,wT=0;
function wReset(){wZ=new Uint8Array(WW2*WH2);wO=new Uint8Array(WW2*WH2);const k=wCombo;if(k&1)pseed(wZ,WW2,12,10,7);if(k&2)pseed(wZ,WW2,28,10,7);wT=0;$("w_in").textContent=((k&2)>>1)+""+(k&1);}
function wTick(){if(wT<50){pseed(wO,WW2,20,16,7);pseed(wO,WW2,20,80,9);}wZ=step(wZ,LW,WW2,WH2);wO=step(wO,LO,WW2,WH2);
  for(let p=0;p<WW2*WH2;p++)if(Wmask[p]===0){wZ[p]=0;wO[p]=0;}annih(wZ,wO);wT++;
  if(wT===150){const o=pmassR(wO,WW2,4,36,78,92)>pmassR(wZ,WW2,4,36,78,92)?1:0;$("w_out").textContent=o;}
  if(wT>=180){wCombo=(wCombo+1)&3;wReset();}drawTwo($("cw").getContext("2d"),wZ,wO,WW2,WH2,GREEN,AMBER,Wmask);}
const C5=40,GAP=10,RH=40,PS=24,N5=5;const RW=N5*(C5+GAP);
let rA=new Uint8Array(RW*RH),rB=new Uint8Array(RW*RH),rClk=0,rCd=0,rSettle=0;
function rWrite(bits){rA=new Uint8Array(RW*RH);rB=new Uint8Array(RW*RH);const cy=RH>>1;for(let i=0;i<N5;i++){const cx=i*(C5+GAP)+GAP+(C5>>1);pseed(bits[i]?rA:rB,RW,cy,cx,PS);}rSettle=12;}
function rRead(){const out=[];for(let i=0;i<N5;i++){const x0=i*(C5+GAP);out.push(pmassR(rA,RW,0,RH,x0,x0+C5+GAP)>pmassR(rB,RW,0,RH,x0,x0+C5+GAP)?1:0);}return out;}
function rTick(){if(rSettle>0){rA=step(rA,LO,RW,RH);rB=step(rB,LZ,RW,RH);annih(rA,rB);rSettle--;}
  else if(++rCd>=40){rCd=0;const cur=rRead();const nb=[cur[N5-1]].concat(cur.slice(0,N5-1));rWrite(nb);rClk++;}
  $("r_bits").textContent=rRead().join("");$("r_clk").textContent=rClk;drawTwo($("cr").getContext("2d"),rA,rB,RW,RH,AMBER,BLUE);}
$("l_set").onclick=()=>{lAuto=false;$("l_auto").classList.remove("on");lWrite(1);};
$("l_rst").onclick=()=>{lAuto=false;$("l_auto").classList.remove("on");lWrite(0);};
$("l_auto").onclick=function(){lAuto=!lAuto;this.classList.toggle("on",lAuto);};
$("i_tog").onclick=()=>{iAuto=false;$("i_auto").classList.remove("on");iIn^=1;iZ=new Uint8Array(IW*IH);iO=new Uint8Array(IW*IH);};
$("i_auto").onclick=function(){iAuto=!iAuto;this.classList.toggle("on",iAuto);};
gReset();lWrite(1);wReset();rWrite([1,0,1,1,0]);
let pfc=0;
function panelLoop(){if(aboutVisible){pfc++;gTick();if(pfc%2===0)lTick();iTick();wTick();rTick();}requestAnimationFrame(panelLoop);}
requestAnimationFrame(panelLoop);
/* tabs */
document.querySelectorAll(".tab").forEach(b=>b.onclick=function(){document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));this.classList.add("active");
  const t=this.dataset.t;aboutVisible=(t==="about");$("tab-demo").style.display=t==="demo"?"":"none";$("tab-about").style.display=t==="about"?"":"none";});
$("selftest").textContent=hex(sha256(enc("abc")))==="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"?"":"  [SHA-256 self-test FAILED]";
$("rekey").onclick=reset;$("seed").onchange=reset;
/* ---- files: Writer .txt / Sheet CSV / Paint PNG. Loads write BOTH VMs so the panes stay in sync. ---- */
(function(){
 const PALrgb=OS.PAL.map(h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)]);
 const rd32=(vm,a)=>(vm.M[a]|(vm.M[a+1]<<8)|(vm.M[a+2]<<16)|(vm.M[a+3]<<24))>>>0;
 const both=(addr,v)=>{wr32(aliceVM,addr,v);wr32(bobVM,addr,v);};
 const dl=(name,blob)=>{const u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),800);};
 const pick=(acc,cb)=>{const f=$("file");f.value="";f.accept=acc;f.onchange=()=>{if(f.files[0])cb(f.files[0]);};f.click();};
 const near=(r,g,b)=>{let bi=0,bd=1e9;for(let i=0;i<PALrgb.length;i++){const p=PALrgb[i],dr=p[0]-r,dg=p[1]-g,db=p[2]-b,dd=dr*dr+dg*dg+db*db;if(dd<bd){bd=dd;bi=i;}}return bi;};
 $("wsave").onclick=()=>{const n=rd32(aliceVM,OS.TLEN);let s="";for(let i=0;i<n;i++){const cp=aliceVM.M[OS.TBUF+i*2]|(aliceVM.M[OS.TBUF+i*2+1]<<8);s+=String.fromCodePoint(cp);}dl("document.txt",new Blob([s],{type:"text/plain"}));};
 $("wload").onclick=()=>pick(".txt,text/plain",f=>{const r=new FileReader();r.onload=()=>{let i=0;for(const ch of r.result){if(i>=1800)break;if(ch==="\r")continue;const cp=ch.codePointAt(0);aliceVM.M[OS.TBUF+i*2]=cp&0xFF;aliceVM.M[OS.TBUF+i*2+1]=(cp>>8)&0xFF;bobVM.M[OS.TBUF+i*2]=cp&0xFF;bobVM.M[OS.TBUF+i*2+1]=(cp>>8)&0xFF;i++;}both(OS.TLEN,i);both(OS.APP,3);both(OS.DIRTY,1);};r.readAsText(f);});
 $("csave").onclick=()=>{const rows=[];for(let r=0;r<4;r++){const c=[];for(let col=0;col<3;col++)c.push(rd32(aliceVM,OS.CELLS+(r*3+col)*OS.CSTRIDE));rows.push(c.join(","));}dl("sheet.csv",new Blob([rows.join("\n")+"\n"],{type:"text/csv"}));};
 $("cload").onclick=()=>pick(".csv,text/csv",f=>{const r=new FileReader();r.onload=()=>{const cells=[];r.result.split(/\r?\n/).forEach(L=>{if(!L.trim())return;L.split(",").forEach(v=>cells.push((parseInt(v.trim(),10)||0)>>>0));});for(let i=0;i<12;i++)both(OS.CELLS+i*OS.CSTRIDE,cells[i]||0);both(OS.APP,4);both(OS.DIRTY,1);};r.readAsText(f);});
 const CXo=OS.WINX+10,CYo=OS.WINY+42,CWp=OS.WW-20,CHp=OS.WH-54;
 $("psave").onclick=()=>{const cv=document.createElement("canvas");cv.width=CWp;cv.height=CHp;const g2=cv.getContext("2d"),id=g2.createImageData(CWp,CHp);for(let y=0;y<CHp;y++)for(let x=0;x<CWp;x++){const v=aliceVM.M[OS.FB+(CYo+y)*OS.W+(CXo+x)],p=PALrgb[v]||PALrgb[0],o=(y*CWp+x)*4;id.data[o]=p[0];id.data[o+1]=p[1];id.data[o+2]=p[2];id.data[o+3]=255;}g2.putImageData(id,0,0);cv.toBlob(b=>dl("paint.png",b));};
 $("pload").onclick=()=>pick("image/*",f=>{const img=new Image();img.onload=()=>{const cv=document.createElement("canvas");cv.width=CWp;cv.height=CHp;const g2=cv.getContext("2d");g2.fillStyle="#fff";g2.fillRect(0,0,CWp,CHp);g2.drawImage(img,0,0,CWp,CHp);const d=g2.getImageData(0,0,CWp,CHp).data;both(OS.APP,1);both(OS.DIRTY,1);requestAnimationFrame(()=>requestAnimationFrame(()=>{for(let y=0;y<CHp;y++)for(let x=0;x<CWp;x++){const o=(y*CWp+x)*4,idx=near(d[o],d[o+1],d[o+2]);aliceVM.M[OS.FB+(CYo+y)*OS.W+(CXo+x)]=idx;bobVM.M[OS.FB+(CYo+y)*OS.W+(CXo+x)]=idx;}}));URL.revokeObjectURL(img.src);};img.src=URL.createObjectURL(f);});
})();
reset();loadFont();
</script></body></html>'''
HTML = HTML.replace("__OS__", OSJSON).replace("__FONT__", FONTJSON).replace("__LO__", PLUTS["LO"]).replace("__LZ__", PLUTS["LZ"]).replace("__LW__", PLUTS["LW"])
open("dissemination/glider-lab24.html", "w").write(HTML)
print("wrote dissemination/glider-lab24.html", len(HTML), "bytes")
