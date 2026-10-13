#!/usr/bin/env python3
"""Flag hard-to-read prose in <rundir>/tour.json. Prints warnings; exits 0.

Usage: lint_prose.py <rundir>

Checks the mechanical rules in reference/writing.md: long sentences, too many code names in one
sentence, long paragraphs, code or refs in the leads that must be plain, refs mid-sentence, `->`
arrows, and missing leads (headline, chapter tldr, finding impact). It cannot judge clarity.
"""
import json
import os
import re
import sys

CODE = re.compile(r"`[^`]+`")
REF = re.compile(r"`(?:base:)?[\w@./+-]+\.\w+:\d+(?:-\d+)?`")
MAX_WORDS, MAX_CODE, MAX_SENTENCES = 30, 2, 5


def sentences(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    for para in re.split(r"\n\s*\n", text):
        lines = [l for l in para.splitlines() if l.strip()]
        items = [l for l in lines if re.match(r"\s*[-*] ", l)] or [" ".join(lines)]
        for item in items:
            yield from (s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`*])", item) if s.strip())


def check(where, text, out, plain=False, max_words=MAX_WORDS):
    if not text:
        return
    for para in re.split(r"\n\s*\n", re.sub(r"```.*?```", " ", text, flags=re.S)):
        if not re.match(r"\s*[-*] ", para) and len(list(sentences(para))) > MAX_SENTENCES:
            out.append(f"{where}: a paragraph has more than {MAX_SENTENCES} sentences")
    for s in sentences(text):
        words = len(CODE.sub("x", s).split())
        names = len(CODE.findall(s))
        short = s[:70] + ("…" if len(s) > 70 else "")
        if words > max_words:
            out.append(f"{where}: {words}-word sentence: \"{short}\"")
        if plain and names:
            out.append(f"{where}: should be plain words, no code: \"{short}\"")
        elif names > MAX_CODE:
            out.append(f"{where}: {names} code names in one sentence: \"{short}\"")
        refs = list(REF.finditer(s))
        if refs and refs[0].end() < len(s.rstrip(".)")) - 2:
            out.append(f"{where}: ref in the middle of a sentence, move it to the end or to `see`/`evidence`: \"{short}\"")
        if "->" in s:
            out.append(f"{where}: replace `->` arrows with sentences: \"{short}\"")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    t = json.load(open(os.path.join(sys.argv[1], "tour.json")))
    out = []
    s, c = t.get("summary", {}), t.get("context", {})
    if not s.get("headline"):
        out.append("summary: missing headline")
    check("summary.headline", s.get("headline"), out, plain=True, max_words=40)
    check("summary.why", s.get("why"), out)
    check("summary.riskReason", s.get("riskReason"), out)
    check("context.before", c.get("before"), out)
    check("context.after", c.get("after"), out)
    for p, b in ((t.get("stack") or {}).get("prs") or {}).items():
        check(f"stack #{p}.brief", b.get("brief"), out)
        check(f"stack #{p}.relation", b.get("relation"), out)
    for ch in t.get("chapters", []):
        cid = ch.get("id")
        if not ch.get("tldr"):
            out.append(f"chapter {cid}: missing `tldr` (one plain sentence)")
        check(f"chapter {cid}.tldr", ch.get("tldr"), out, plain=True)
        check(f"chapter {cid}.explain", ch.get("explain"), out)
        for i, x in enumerate(ch.get("check", []), 1):
            check(f"chapter {cid}.check[{i}]", x, out)
        for it in ch.get("items", []):
            check(f"chapter {cid} note on {it.get('ref')}", it.get("note"), out)
    for f in t.get("findings", []):
        fid = f.get("id")
        if f.get("verdict") != "DISMISSED" and not f.get("impact"):
            out.append(f"finding {fid}: missing `impact` (who notices, what they see)")
        check(f"finding {fid}.impact", f.get("impact"), out, plain=True)
        for k in ("summary", "scenario", "fix"):
            check(f"finding {fid}.{k}", f.get(k), out)
        v = f.get("verifier") or ""
        if len(CODE.sub("x", v).split()) > 110:
            out.append(f"finding {fid}.verifier: over 110 words; rewrite to the deciding reason")
        check(f"finding {fid}.verifier", v, out)
    for d in t.get("descriptionCheck", []):
        check("descriptionCheck", d.get("detail"), out)
    print("\n".join(out) if out else "prose: no warnings")
    print(f"prose: {len(out)} warning(s)" if out else "", end="")


if __name__ == "__main__":
    main()
