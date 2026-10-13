#!/usr/bin/env python3
"""Create, find or show a design-doc run.

Usage: new_run.py new <slug> [--repo-dir DIR]   create RUN, print its path
       new_run.py list [--repo-dir DIR]          runs for this repo, newest first
       new_run.py show <RUN>                     where the run stands and what waits on the human

A run lives in ${DESIGN_DOC_HOME:-~/.cache/design-doc}/runs/<repo>-<slug>. It holds meta.json
(repo, src, head, created, artifact url once published), design.json (the doc) and research/
(the agents' scratch notes). The repo itself is untouched until sign-off.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

HOME = os.path.expanduser(os.environ.get("DESIGN_DOC_HOME", "~/.cache/design-doc"))


def git(args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def repo_info(repo_dir):
    src = git(["rev-parse", "--show-toplevel"], repo_dir) or os.path.abspath(repo_dir)
    url = git(["remote", "get-url", "origin"], src)
    m = re.search(r"[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
    repo = m.group(1) if m else os.path.basename(src)
    return {"repo": repo, "src": src, "head": git(["rev-parse", "HEAD"], src), "branch": git(["branch", "--show-current"], src)}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new(slug, repo_dir):
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")[:48] or "design"
    info = repo_info(repo_dir)
    run = os.path.join(HOME, "runs", f"{info['repo'].replace('/', '-')}-{slug}")
    if os.path.exists(os.path.join(run, "design.json")):
        sys.exit(f"{run} already exists; resume it, or pick another slug")
    os.makedirs(os.path.join(run, "research"), exist_ok=True)
    json.dump({**info, "slug": slug, "run": run, "created": now(), "artifact": None},
              open(os.path.join(run, "meta.json"), "w"), indent=1)
    json.dump({"title": "", "slug": slug, "stage": "frame", "seed": "", "status": {"working": "Reading the code"},
               "frame": {"status": "draft"}, "ground": {"status": "pending"}, "decisions": [],
               "decisionsStatus": "pending", "design": {"status": "pending", "sections": []},
               "objections": [], "challengeStatus": "pending", "defense": [], "questions": [], "log": []},
              open(os.path.join(run, "design.json"), "w"), indent=1)
    print(run)


def runs(repo_dir):
    prefix = repo_info(repo_dir)["repo"].replace("/", "-") + "-"
    base = os.path.join(HOME, "runs")
    found = [os.path.join(base, d) for d in os.listdir(base) if d.startswith(prefix)] if os.path.isdir(base) else []
    found = [r for r in found if os.path.exists(os.path.join(r, "design.json"))]
    return sorted(found, key=lambda r: os.path.getmtime(os.path.join(r, "design.json")), reverse=True)


def show(run):
    d = json.load(open(os.path.join(run, "design.json")))
    meta = json.load(open(os.path.join(run, "meta.json")))
    print(f"{d.get('title') or meta['slug']}  stage: {d.get('stage')}  artifact: {meta.get('artifact') or 'not published'}")
    decided = sum(c.get("status") == "decided" for c in d.get("decisions", []))
    print(f"decisions: {decided} of {len(d.get('decisions', []))} decided, {sum(c.get('status') == 'parked' for c in d.get('decisions', []))} parked")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from render import waiting_list
    w = [x["label"] for x in waiting_list(d)]
    print("waiting on the human:" + ("".join(f"\n- {x}" for x in w) if w else " nothing"))
    for e in d.get("log", [])[-5:]:
        print(f"  {e.get('at', '')[:16]}  {e.get('what', '')}")


def main():
    a = sys.argv[1:]
    repo_dir = a[a.index("--repo-dir") + 1] if "--repo-dir" in a else "."
    if a[:1] == ["new"] and len(a) > 1:
        new(a[1], repo_dir)
    elif a[:1] == ["list"]:
        for r in runs(repo_dir):
            d = json.load(open(os.path.join(r, "design.json")))
            when = datetime.fromtimestamp(os.path.getmtime(os.path.join(r, "design.json"))).strftime("%Y-%m-%d %H:%M")
            print(f"{r}\t{when}\t{d.get('stage')}\t{d.get('title') or ''}")
    elif a[:1] == ["show"] and len(a) > 1:
        show(a[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
