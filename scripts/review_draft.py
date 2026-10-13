#!/usr/bin/env python3
"""Turn the reviewer's calls and notes into a GitHub review.

Usage: review_draft.py <rundir> <notes.json> [--post | --json]

notes.json: {"read": {chapterId: bool}, "findings": {id: {"verdict": "agree|ask|reject", "note": str}},
             "notes": {chapterId: str}}  (what the tour page stores / "Copy my notes" exports)

Without --post: writes <rundir>/review.json and prints the review as it will appear.
With --post: submits <rundir>/review.json as a COMMENT review (never approve / request changes).
With --json: also prints the draft as one JSON object for the page's `review/draft` doc:
  {body, comments: [{path, line, body}], undecided: [ids], unread: [chapter ids], at}
"""
import json
import os
import subprocess
import sys


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    run, notes_path, post, as_json = args[0], args[1], "--post" in args, "--json" in args
    load = lambda p: json.load(open(p, encoding="utf-8"))
    meta, tour, files = load(os.path.join(run, "meta.json")), load(os.path.join(run, "tour.json")), load(os.path.join(run, "hunks.json"))["files"]
    notes = load(notes_path)

    # GitHub accepts line comments only on lines inside a hunk (RIGHT side = new file lines).
    commentable = {}
    for f in files:
        s = commentable.setdefault(f["path"], set())
        for h in f["hunks"]:
            s.update(n for kind, _, n, _ in h["lines"] if n is not None and kind in "+ ")

    calls = notes.get("findings", {})
    inline, body_findings, questions = [], [], []
    for f in tour.get("findings", []):
        call = calls.get(f["id"]) or {}
        v, note = call.get("verdict"), (call.get("note") or "").strip()
        if f["verdict"] == "DISMISSED" or v not in ("agree", "ask"):
            continue
        if v == "ask":
            q = note or f"{f['title']}: {f['summary']}"
            questions.append((f, q))
            continue
        text = f"**{f['title']}** ({f['severity']})\n\n" + (f"{f['impact']}\n\n" if f.get("impact") else "") + f"{f['summary']}\n\n**How it breaks:** {f['scenario']}"
        if f.get("fix"):
            text += f"\n\n**Suggestion:** {f['fix']}"
        if f.get("stack"):
            label = {"fixed-above": "Fixed later in", "changed-above": "Changed later in", "from-below": "Comes from", "breaks-above": "Breaks"}[f["stack"]["kind"]]
            text += f"\n\n_{label} #{f['stack']['pr']}._ {f['stack'].get('note', '')}".rstrip()
        if note:
            text += f"\n\n{note}"
        line = f.get("line")
        if f.get("file") and line and line in commentable.get(f["file"], ()):
            inline.append({"path": f["file"], "line": line, "side": "RIGHT", "body": text})
        else:
            where = f" (`{f['file']}:{line}`)" if f.get("file") and line else (f" (`{f['file']}`)" if f.get("file") else "")
            body_findings.append(text + where)

    titles = {c["id"]: c["title"] for c in tour["chapters"]}
    chapter_notes = [(titles.get(k, k), v.strip()) for k, v in notes.get("notes", {}).items() if v and v.strip()]

    parts = []
    if chapter_notes:
        parts.append("\n\n".join(f"**{t}**\n{n}" for t, n in chapter_notes))
    if body_findings:
        parts.append("### Not on a changed line\n\n" + "\n\n---\n\n".join(body_findings))
    if questions:
        parts.append("### Questions\n\n" + "\n".join(f"- {q}" + (f" (`{f['file']}:{f['line']}`)" if f.get("file") and f.get("line") else "") for f, q in questions))
    body = "\n\n".join(parts)

    review = {"commit_id": meta["headSha"], "event": "COMMENT", "body": body, "comments": inline}
    out = os.path.join(run, "review.json")
    if as_json:
        live = [f["id"] for f in tour.get("findings", []) if f["verdict"] != "DISMISSED"]
        from datetime import datetime, timezone
        json.dump(review, open(out, "w", encoding="utf-8"), indent=1)
        print(json.dumps({"body": body, "comments": [{k: c[k] for k in ("path", "line", "body")} for c in inline],
                          "undecided": [i for i in live if not (calls.get(i) or {}).get("verdict")],
                          "unread": [c["id"] for c in tour["chapters"] if not notes.get("read", {}).get(c["id"])],
                          "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}))
        return
    if not post:
        if not inline and not body:
            print("Nothing to post: no findings marked 'Agree' or 'Ask', and no chapter notes.")
            return
        json.dump(review, open(out, "w", encoding="utf-8"), indent=1)
        print(f"Review for {meta['repo']}#{meta['number']} at {meta['headSha'][:7]} (COMMENT, {len(inline)} line comment(s))\n")
        print("=== Review body ===\n" + (body or "(empty)"))
        for c in inline:
            print(f"\n=== {c['path']}:{c['line']} ===\n{c['body']}")
        print(f"\nSaved to {out}. Post with: review_draft.py {run} {notes_path} --post")
        return
    if not os.path.exists(out):
        sys.exit("Run without --post first, and show the draft to the reviewer.")
    res = subprocess.run(["gh", "api", "-X", "POST", f"repos/{meta['repo']}/pulls/{meta['number']}/reviews", "--input", out],
                         capture_output=True, text=True)
    if res.returncode:
        sys.exit("gh api failed:\n" + res.stderr)
    print(json.loads(res.stdout).get("html_url", "posted"))


if __name__ == "__main__":
    main()
