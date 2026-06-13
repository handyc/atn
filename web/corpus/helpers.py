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
