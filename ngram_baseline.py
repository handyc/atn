#!/usr/bin/env python3
# ngram_baseline.py — atn's REAL n-gram bpb on the same fresh-region test bytes
# the CA reservoir was scored on, so the reservoir's 3.78 bpb has honest context.
# Trains atn on the first 85% of the region, scores the last 15% (matching the
# reservoir eval's train+val / test boundary). --score-bytes prints per-byte
# surprisals; we average them all = aggregate bpb over the test bytes.
import subprocess, tempfile, os

path = "demo-run/eval.txt"; offset = 400000; nbytes = 16000; warmup = 150
data = open(path, "rb").read(offset + nbytes)[offset:]
n = len(data); s, e = warmup, n - 1
m = e - s; i2 = int(m * 0.85)
cut = s + i2 + 1
train, test = data[:cut], data[cut:]
print(f"region {n} bytes; train {len(train)} / test {len(test)} bytes")

def agg_bpb(out_text):
    vals = []
    for tok in out_text.replace("\t", " ").split():
        try: vals.append(float(tok))
        except ValueError: pass
    return sum(vals) / len(vals) if vals else float("nan")

for orders in ["2,4", "2,4,7", "1,2,3,4,5,6,7"]:
    with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as tf:
        tf.write(train); trp = tf.name
    bp = trp + ".brain"
    subprocess.run(["./atn", "--train", trp, "--brain", bp, "-q",
                    "--map-bits", "22", "--orders", orders],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    r = subprocess.run(["./atn", "--score-bytes", "--brain", bp,
                        "--map-bits", "22", "--orders", orders],
                       input=test, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    print(f"  atn n-gram orders={orders:<16} test bpb = {agg_bpb(r.stdout.decode('utf-8','ignore')):.3f}")
    for p in (trp, bp):
        try: os.unlink(p)
        except OSError: pass
