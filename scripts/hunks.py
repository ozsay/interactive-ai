#!/usr/bin/env python3
"""Split a unified diff into addressable hunks.

Usage: hunks.py <diff.patch> <hunks.json>   (prints a compact index to stdout)

Ids: `f<N>` is a file, `f<N>h<M>` one hunk of it. The tour assigns every id to a chapter
or to the skim list; render.py checks nothing was dropped.
"""
import json
import re
import sys

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")
GIT = re.compile(r"^diff --git a/(.*) b/(.*)$")


def parse(text):
    files, cur, h = [], None, None
    old_no = new_no = 0
    for line in text.splitlines():
        m = GIT.match(line)
        if m:
            cur = {"id": f"f{len(files) + 1}", "old": m.group(1), "path": m.group(2),
                   "status": "modified", "binary": False, "additions": 0, "deletions": 0, "hunks": []}
            files.append(cur)
            h = None
            continue
        if cur is None:
            continue
        m = HUNK.match(line)
        if m:
            old_no, new_no = int(m.group(1)), int(m.group(3))
            h = {"id": f"{cur['id']}h{len(cur['hunks']) + 1}", "oldStart": old_no,
                 "oldLines": int(m.group(2) or 1), "newStart": new_no,
                 "newLines": int(m.group(4) or 1), "section": m.group(5).strip(), "lines": []}
            cur["hunks"].append(h)
            continue
        if h is None:  # file header lines
            if line.startswith("new file"):
                cur["status"] = "added"
            elif line.startswith("deleted file"):
                cur["status"] = "deleted"
            elif line.startswith("rename from"):
                cur["status"] = "renamed"
            elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
                cur["binary"] = True
            continue
        tag = line[:1]
        if tag == "+":
            h["lines"].append(["+", None, new_no, line[1:]])
            new_no += 1
            cur["additions"] += 1
        elif tag == "-":
            h["lines"].append(["-", old_no, None, line[1:]])
            old_no += 1
            cur["deletions"] += 1
        elif tag == " " or line == "":
            h["lines"].append([" ", old_no, new_no, line[1:]])
            old_no += 1
            new_no += 1
        elif tag == "\\":
            h["lines"].append(["\\", None, None, line])
    return files


def index(files):
    out = []
    for f in files:
        st = {"added": "A", "deleted": "D", "renamed": "R"}.get(f["status"], "M")
        name = f["path"] if f["status"] != "renamed" else f"{f['old']} -> {f['path']}"
        extra = " [binary]" if f["binary"] else ""
        out.append(f"{f['id']:<6} {st} {name}  (+{f['additions']} -{f['deletions']}){extra}")
        for h in f["hunks"]:
            adds = sum(1 for l in h["lines"] if l[0] == "+")
            dels = sum(1 for l in h["lines"] if l[0] == "-")
            first = next((l[3].strip() for l in h["lines"] if l[0] in "+-" and l[3].strip()), "")
            out.append(f"  {h['id']:<8} @@ -{h['oldStart']} +{h['newStart']} {h['section'][:50]}"
                       f"  (+{adds} -{dels})  {first[:70]}")
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
        files = parse(fh.read())
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump({"files": files}, fh)
    print(index(files))
