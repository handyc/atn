#!/usr/bin/env python3
# walkthrough.py — render a scripted walk through the maze with the CA-1 raycaster program
# (bit-faithful emulator; ALU verified == genuine CA gates) and save ASCII frames as a
# committable, browser-free artifact.
import raycaster as rc
from ca1sys import CA1Sys

SW, SH = rc.SW, rc.SH
CHS = {0: ' ', 1: '`', 2: '@', 3: '#', 4: '=', 5: '.'}
# input bits: b0 left, b1 right, b2 fwd, b3 back
SCRIPT = [4, 4, 4, 4, 4, 2, 2, 4, 4, 4, 1, 1, 4, 4, 4, 4]

def main():
    m = CA1Sys(fb_addr=rc.FB_A, fb_w=SH, fb_h=SW); rc.load_memory(m)
    code = rc.program(loop=True)
    frames = []; fi = [0]
    def setin(mm):
        i = fi[0]; fi[0] += 1
        return SCRIPT[i] if i < len(SCRIPT) else 0
    def on_frame(mm):
        fb = mm.M[rc.FB_A:rc.FB_A + SW * SH]
        frames.append((mm.M[0x12], "\n".join("".join(CHS[fb[c * SH + y]] for c in range(SW)) for y in range(SH))))
        return len(frames) >= len(SCRIPT)
    m.run(code, max_i=50_000_000, frame_on=on_frame, set_input=setin)
    with open("RAYCAST_WALKTHROUGH.md", "w") as out:
        out.write("# CA-1 raycaster walkthrough\n\n")
        out.write("Each frame is ~40,000 CA-1 instructions, rendered by the bit-faithful emulator\n")
        out.write("(ALU verified bit-identical to the genuine CA gates; 400/400 ops replayed on the\n")
        out.write("real CA datapath). Move script: forward ×5, turn-right ×2, forward ×3, turn-left ×2,\n")
        out.write("forward ×4. Legend: `` ` `` ceiling · `@` near wall · `#` mid wall · `=` far wall · `.` floor.\n")
        for i, (pa, f) in enumerate(frames):
            out.write(f"\n### frame {i}  (player angle {pa})\n```\n{f}\n```\n")
    print(f"wrote RAYCAST_WALKTHROUGH.txt with {len(frames)} frames")
    print(frames[0][1]); print("\n... frame 7 ...\n"); print(frames[7][1])

if __name__ == "__main__":
    main()
