#!/usr/bin/env python3
"""Flag hard-to-read text in RUN/design.json. Prints warnings; exits 0.

Usage: lint_prose.py <RUN>

Checks the mechanical rules in reference/writing.md and reference/questions.md: long sentences,
too many code names per sentence, long paragraphs, `->` arrows, cards over about 200 words, open
decisions without a recommendation or with fewer than two real options, and questions missing what
Claude found or why it can't decide. It cannot judge clarity.
"""
import json
import os
import re
import sys

CODE = re.compile(r"`[^`]+`")
MAX_WORDS, MAX_CODE, MAX_SENTENCES, MAX_CARD = 30, 2, 5, 220


def sentences(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    for para in re.split(r"\n\s*\n", text):
        lines = [l for l in para.splitlines() if l.strip()]
        items = [l for l in lines if re.match(r"\s*[-*] ", l)] or [" ".join(lines)]
        for item in items:
            yield from (s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`*])", item) if s.strip())


def words(text):
    return len(CODE.sub("x", re.sub(r"```.*?```", " ", text or "", flags=re.S)).split())


def check(where, text, out, plain=False):
    if not text:
        return
    if isinstance(text, list):
        for i, t in enumerate(text, 1):
            check(f"{where}[{i}]", t, out, plain)
        return
    for para in re.split(r"\n\s*\n", re.sub(r"```.*?```", " ", text, flags=re.S)):
        if not re.match(r"\s*[-*] ", para) and len(list(sentences(para))) > MAX_SENTENCES:
            out.append(f"{where}: a paragraph has more than {MAX_SENTENCES} sentences")
    for s in sentences(text):
        n, names = words(s), len(CODE.findall(s))
        short = s[:70] + ("…" if len(s) > 70 else "")
        if n > MAX_WORDS:
            out.append(f"{where}: {n}-word sentence: \"{short}\"")
        if plain and names:
            out.append(f"{where}: should be plain words, no code: \"{short}\"")
        elif names > MAX_CODE:
            out.append(f"{where}: {names} code names in one sentence: \"{short}\"")
        if "->" in s:
            out.append(f"{where}: replace `->` arrows with sentences: \"{short}\"")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = json.load(open(os.path.join(sys.argv[1], "design.json")))
    out = []
    f, g = d.get("frame", {}), d.get("ground", {})
    check("frame.problem", f.get("problem"), out, plain=True)
    for k in ("who", "goals", "nonGoals", "done", "constraints"):
        check(f"frame.{k}", f.get(k), out)
    for a in f.get("assumptions", []):
        check(f"assumption {a.get('id')}", a.get("text"), out)
    for k in ("summary", "flow", "invariants", "surprises"):
        check(f"ground.{k}", g.get(k), out)
    for x in d.get("decisions", []):
        i = x.get("id")
        check(f"{i}.question", x.get("question"), out)
        for k in ("matters", "recommendWhy", "locksIn", "check"):
            check(f"{i}.{k}", x.get(k), out)
        for o in x.get("options", []):
            check(f"{i} option {o.get('id')}", o.get("summary"), out)
        if x.get("status") == "open":
            if len(x.get("options", [])) < 2:
                out.append(f"{i}: an open decision needs at least two real options")
            if not x.get("recommend"):
                out.append(f"{i}: say which option you would pick (`recommend`) and why")
            if not x.get("matters"):
                out.append(f"{i}: missing `matters` (what goes wrong if this is decided badly)")
            card = sum(words(t) for t in [x.get("question"), x.get("matters"), x.get("recommendWhy"), x.get("locksIn")]
                       + [o.get("summary") for o in x.get("options", [])] + sum((o.get("pros", []) + o.get("cons", []) for o in x.get("options", [])), []))
            if card > MAX_CARD:
                out.append(f"{i}: the card is {card} words; keep it under about {MAX_CARD} so it fits on one screen")
        if x.get("status") == "decided" and x.get("key") and not x.get("check"):
            out.append(f"{i}: decided key decision without your `check` of the human's rationale")
    for s in d.get("design", {}).get("sections", []):
        check(f"section {s.get('id')}", s.get("body"), out)
        if s.get("status") == "open" and words(s.get("body")) > 400:
            out.append(f"section {s.get('id')}: over 400 words; split it")
    for q in d.get("questions", []):
        i = q.get("id")
        check(f"{i}.q", q.get("q"), out)
        if q.get("status", "open") == "open":
            for k, why in (("found", "what you already found"), ("why", "why you can't decide alone"), ("changes", "what changes with the answer")):
                if not q.get(k):
                    out.append(f"{i}: missing `{k}` ({why})")
    for o in d.get("objections", []):
        check(f"objection {o.get('id')}", o.get("body"), out)
    print("\n".join(out) if out else "prose: no warnings")
    if out:
        print(f"prose: {len(out)} warning(s)")


if __name__ == "__main__":
    main()
