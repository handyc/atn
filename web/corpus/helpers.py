"""Live scoring and a small language-label heuristic.

score_query is the "live" part of the site: it routes a piece of text by asking
every surviving expert how surprised it is (atn --score), exactly like the CLI
`lightup`. guess_label is a tiny function-word language identifier used only to
give each territory a human-readable name in the atlas (clearly a guess).
"""
import re
import subprocess

# Function words per language — enough to label a sample passage. CJK is detected
# directly. This is a coarse guess for display, not a serious language identifier.
_LANG_WORDS = {
    "English":  set("the and of to in a is was for with that this from as it".split()),
    "Dutch":    set("de het een en van is op met voor werd door zijn die naar".split()),
    "German":   set("der die das und ist von den im wurde eine auch mit sich nach".split()),
    "French":   set("le la les de et des un une est dans pour avec sur au".split()),
    "Spanish":  set("el la los las de y en un una es por para con del".split()),
    "Italian":  set("il la di e che un una in per con della nel sono".split()),
}
_CJK = re.compile(r"[㐀-鿿]")
_WORDS = re.compile(r"[a-zà-ÿ]+")


def guess_label(sample_text, terms):
    """Best-effort language label from a sample passage + distinctive terms."""
    blob = (sample_text or "") + " " + " ".join(terms or [])
    if _CJK.search(blob):
        return "Chinese (zh)"
    toks = _WORDS.findall((sample_text or "").lower())
    if not toks:
        return ""
    best, best_n = "", 0
    for lang, words in _LANG_WORDS.items():
        n = sum(t in words for t in toks)
        if n > best_n:
            best, best_n = lang, n
    return best if best_n >= 2 else ""


def score_query(run, text, timeout=30):
    """Route `text`: return [(bpb, Expert), ...] sorted best-fit first.
    Shells out to the atn binary once per expert (brain loaded per call)."""
    text = (text or "").strip()
    if not text:
        return []
    blob = (text + "\n").encode("utf-8", "ignore")
    results = []
    for e in run.experts.all():
        try:
            r = subprocess.run(
                [run.atn_path, "--score", "--brain", e.brain_abspath,
                 "--map-bits", str(e.mapbits), "--orders", e.orders],
                input=blob, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            tok = r.stdout.decode("utf-8", "ignore").split("\t")[0].strip().split()
            bpb = float(tok[0]) if tok else 99.0
        except Exception:
            bpb = 99.0
        results.append((bpb, e))
    results.sort(key=lambda x: x[0])
    return results


def bpb_color(bpb, lo=0.5, hi=6.0):
    """Map a surprisal (bits/byte) to a colour: low = green (predictable),
    high = red (surprising). Fixed absolute scale so colours mean the same thing
    across texts."""
    t = max(0.0, min(1.0, (bpb - lo) / (hi - lo)))
    return f"hsl({(1 - t) * 120:.0f}, 75%, 78%)"


def score_chars(run, expert, text, timeout=30):
    """Per-CHARACTER surprisal of `text` under one expert's brain (atn
    --score-bytes), as [{ch, bpb, color}, ...]. Multibyte chars get the mean of
    their bytes' bits. This is the 'watch the model read' heatmap."""
    text = (text or "").rstrip("\n")
    if not text:
        return []
    try:
        r = subprocess.run(
            [run.atn_path, "--score-bytes", "--brain", expert.brain_abspath,
             "--map-bits", str(expert.mapbits), "--orders", expert.orders],
            input=(text + "\n").encode("utf-8", "ignore"),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout,
        )
        lines = r.stdout.decode("utf-8", "ignore").splitlines()
        vals = [float(x) for x in lines[0].split()] if lines else []
    except Exception:
        vals = []
    out, bi = [], 0
    for ch in text:
        n = len(ch.encode("utf-8", "ignore"))
        chunk = vals[bi:bi + n]; bi += n
        bpb = sum(chunk) / len(chunk) if chunk else 0.0
        out.append({"ch": ch, "bpb": round(bpb, 2), "color": bpb_color(bpb)})
    return out


def _byte_label(b):
    if b == 32:
        return "␣"          # space
    if b in (10, 13):
        return "⏎"          # newline
    if 32 < b < 127:
        return chr(b)
    return f"·{b:02x}"       # other / multibyte fragment


def predict_next(run, expert, context, topk=20, timeout=30):
    """The model's next-byte distribution after `context` under one expert
    (atn --predict): [{byte, char, prob}, ...], highest first. The distribution
    the model would sample from — 'what comes next', made visible."""
    try:
        r = subprocess.run(
            [run.atn_path, "--predict", "--topk", str(topk), "--brain", expert.brain_abspath,
             "--map-bits", str(expert.mapbits), "--orders", expert.orders],
            input=(context + "\n").encode("utf-8", "ignore"),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout,
        )
    except Exception:
        return []
    out = []
    for ln in r.stdout.decode("utf-8", "ignore").splitlines():
        if not ln.strip():
            break
        try:
            prob, b = ln.split("\t"); b = int(b)
            out.append({"byte": b, "char": _byte_label(b), "prob": round(float(prob), 4)})
        except ValueError:
            continue
    return out
