#!/usr/bin/env python3
"""Find the stack a PR belongs to, from branch relationships on GitHub.

Usage: stack.py <owner/repo> <pr-number> <rundir>

A PR whose base branch is another PR's head is stacked on it. Walks down to the default branch
(ancestors) and up through every PR based on the focus PR's head, recursively (descendants; a
stack can branch). Writes <rundir>/stack.json, <rundir>/stack/<n>.diff for every other PR, and
prints a summary. A PR with no stack yields a stack.json with empty lists.
"""
import json
import os
import subprocess
import sys

FIELDS = "number,title,url,state,isDraft,author,baseRefName,headRefName,headRefOid,additions,deletions,changedFiles,body,files,commits,mergedAt"
MAX_DEPTH = 10


def gh(*args):
    res = subprocess.run(["gh", *args], capture_output=True, text=True)
    if res.returncode:
        raise RuntimeError(res.stderr.strip())
    return res.stdout


def gh_json(*args):
    return json.loads(gh(*args) or "null")


def slim(pr):
    return {
        "number": pr["number"], "title": pr["title"], "url": pr["url"], "state": pr["state"],
        "isDraft": pr.get("isDraft", False), "author": (pr.get("author") or {}).get("login", ""),
        "base": pr["baseRefName"], "head": pr["headRefName"], "headSha": pr["headRefOid"],
        "additions": pr["additions"], "deletions": pr["deletions"], "changedFiles": pr["changedFiles"],
        "body": (pr.get("body") or "")[:6000],
        "files": [f["path"] for f in pr.get("files") or []],
        "commits": [c["messageHeadline"] for c in pr.get("commits") or []],
    }


def pr_for_head(repo, branch):
    """The PR whose head is `branch`: an open one first, else the most recently merged."""
    prs = gh_json("pr", "list", "--repo", repo, "--head", branch, "--state", "all", "--json", FIELDS, "--limit", "20")
    open_ = [p for p in prs if p["state"] == "OPEN"]
    merged = sorted((p for p in prs if p["state"] == "MERGED"), key=lambda p: p.get("mergedAt") or "", reverse=True)
    return (open_ or merged or [None])[0]


def compare(repo, base, head):
    try:
        c = gh_json("api", f"repos/{repo}/compare/{base}...{head}")
        return {"ahead": c["ahead_by"], "behind": c["behind_by"]}
    except RuntimeError:
        return None


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    repo, num, run = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    default = gh_json("repo", "view", repo, "--json", "defaultBranchRef")["defaultBranchRef"]["name"]
    focus = slim(gh_json("pr", "view", str(num), "--repo", repo, "--json", FIELDS))

    ancestors, base_branch = [], focus["base"]
    while base_branch != default and len(ancestors) < MAX_DEPTH:
        pr = pr_for_head(repo, base_branch)
        if not pr:
            break  # based on a plain branch, not a PR
        ancestors.append(slim(pr))
        base_branch = pr["baseRefName"]
    ancestors.reverse()  # bottom of the stack first
    bottom_base = ancestors[0]["base"] if ancestors else focus["base"]

    descendants, frontier, seen = [], [(focus["head"], focus["number"], 1)], {focus["number"]}
    while frontier:
        head, parent, depth = frontier.pop(0)
        if depth > MAX_DEPTH:
            continue
        for pr in gh_json("pr", "list", "--repo", repo, "--base", head, "--state", "all", "--json", FIELDS, "--limit", "30"):
            if pr["number"] in seen:
                continue
            seen.add(pr["number"])
            d = slim(pr)
            d["parent"], d["depth"] = parent, depth
            descendants.append(d)
            frontier.append((pr["headRefName"], pr["number"], depth + 1))

    stack = ancestors + [focus] + descendants
    focus_files = set(focus["files"])
    for pr in stack:
        pr["sharedFiles"] = sorted(focus_files & set(pr["files"])) if pr is not focus else []

    health = []
    for parent, child in zip([None] + ancestors, ancestors + [focus]):
        if parent and parent["state"] == "MERGED":
            health.append(f"#{child['number']} still targets `{child['base']}`, but #{parent['number']} is merged. Retarget it to `{parent['base']}`.")
        if parent and parent["state"] == "CLOSED":
            health.append(f"#{child['number']} is based on #{parent['number']}, which was closed without merging.")
    gap = compare(repo, focus["base"], focus["headSha"]) if focus["state"] == "OPEN" else None
    if gap and gap["behind"]:
        health.append(f"#{focus['number']} is {gap['behind']} commit(s) behind its base `{focus['base']}`, so its diff may not match what lands after a rebase.")

    os.makedirs(os.path.join(run, "stack"), exist_ok=True)
    for pr in stack:
        if pr is focus or pr["state"] == "CLOSED":
            continue
        try:
            with open(os.path.join(run, "stack", f"{pr['number']}.diff"), "w") as fh:
                fh.write(gh("pr", "diff", str(pr["number"]), "--repo", repo))
        except RuntimeError as e:
            health.append(f"Could not fetch the diff of #{pr['number']}: {e}")

    out = {"default": default, "bottomBase": bottom_base, "focus": focus["number"],
           "ancestors": ancestors, "descendants": descendants, "health": health, "focusBehind": gap}
    json.dump(out, open(os.path.join(run, "stack.json"), "w"), indent=1)

    if not ancestors and not descendants:
        print(f"stack: #{num} is not stacked (base `{focus['base']}`).")
        return
    print(f"stack: {len(stack)} PRs, base `{bottom_base}`. Bottom first:")
    for pr in ancestors:
        print(f"  #{pr['number']:<5} {pr['state']:<7} {pr['title'][:70]}  (+{pr['additions']} -{pr['deletions']})")
    print(f"> #{focus['number']:<5} {focus['state']:<7} {focus['title'][:70]}  (+{focus['additions']} -{focus['deletions']})  <- reviewing")
    for pr in descendants:
        print(f"  {'  ' * pr['depth']}#{pr['number']:<5} {pr['state']:<7} {pr['title'][:60]}  (on #{pr['parent']}, +{pr['additions']} -{pr['deletions']})")
    for h in health:
        print(f"  ! {h}")


if __name__ == "__main__":
    main()
