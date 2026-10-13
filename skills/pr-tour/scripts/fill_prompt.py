#!/usr/bin/env python3
"""Fill a reviewer or verifier prompt for a run.

Usage: fill_prompt.py <rundir> reviewer <out.md> --prefix R
       fill_prompt.py <rundir> verifier <out.md> --findings <claims.json> [--run]

Fills {{RUN}}, {{SRC}}, {{MERGE_BASE}}, the stack rules when the PR is stacked, and for a
verifier the claims to check ({{FINDINGS}}: a JSON array, or an object with a "findings" array)
and whether it may run code (--run). Prints the output path.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE, "..", "prompts")
READ_ONLY = "Do not run any code. Verify by reading."
RUN_OK = ("If a short test or script would show the failure, write it inside {{SRC}}, run it with the dependencies "
          "already installed there, record the command and trimmed output in your verifier note, then delete what you "
          "wrote. Never install dependencies or reach the network. If it cannot run, say so.")


def stack_context(run, meta):
    path = os.path.join(run, "stack.json")
    if not os.path.exists(path):
        return ""
    st = json.load(open(path))
    if not st["ancestors"] and not st["descendants"]:
        return ""
    lines = [f"- below: #{p['number']} {p['state']} \"{p['title']}\" (base `{p['base']}`)" for p in st["ancestors"]]
    if not st["ancestors"]:
        lines.append(f"- below: none (based on `{st['default']}`)")
    lines.append(f"- reviewing: #{st['focus']}")
    lines += [f"- above: #{p['number']} {p['state']} \"{p['title']}\" (built on #{p['parent']})" for p in st["descendants"]]
    if not st["descendants"]:
        lines.append("- above: none")
    text = open(os.path.join(PROMPTS, "stack-context.md")).read()
    for k, v in {"FOCUS": str(st["focus"]), "DEFAULT": st["default"], "STACK_LIST": "\n".join(lines),
                 "MERGE_BASE": meta["mergeBase"], "RUN": run}.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def main():
    args = sys.argv[1:]
    if len(args) < 3 or args[1] not in ("reviewer", "verifier"):
        sys.exit(__doc__)
    run, kind, out = os.path.abspath(args[0]), args[1], args[2]
    opt = lambda name: args[args.index(name) + 1] if name in args else None
    meta = json.load(open(os.path.join(run, "meta.json")))
    text = open(os.path.join(PROMPTS, f"{kind}.md")).read()
    stack = stack_context(run, meta)
    values = {"CONTEXT": stack, "STACK": stack, "PREFIX": opt("--prefix") or "R",
              "REPRO": RUN_OK if "--run" in args else READ_ONLY}
    if kind == "verifier":
        if not opt("--findings"):
            sys.exit("verifier needs --findings <claims.json>")
        claims = json.load(open(opt("--findings")))
        values["FINDINGS"] = json.dumps(claims.get("findings", claims) if isinstance(claims, dict) else claims, indent=1)
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    for k, v in {"RUN": run, "SRC": meta["src"], "MERGE_BASE": meta["mergeBase"]}.items():
        text = text.replace("{{" + k + "}}", v)  # last: the inserted blocks use these too
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w").write(text)
    print(out)


if __name__ == "__main__":
    main()
