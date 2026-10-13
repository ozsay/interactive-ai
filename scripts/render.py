#!/usr/bin/env python3
"""Validate <rundir>/tour.json and render it into a single HTML page.

Usage: render.py <rundir> [--out <file.html>]

Fails (exit 1) with a list of problems when the tour drops or repeats a hunk, references an
unknown id, or misses a required field, so the page never silently hides part of the PR.
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "template.html")
MAX_HUNK_LINES = 400
COLLAPSE_DELETED = 30
SEVERITIES = ["high", "medium", "low", "nit"]
VERDICTS = ["CONFIRMED", "PLAUSIBLE", "DISPUTED", "UNVERIFIED", "DISMISSED"]
LEVELS = ["fast", "regular", "deep"]
AGENTS = {"claude": "Claude", "codex": "Codex"}
DESC_KINDS = {"matches": "Matches", "missing": "Claimed, not found",
              "unmentioned": "Not in description", "contradicts": "Contradicts"}
REF = re.compile(r"^(base:)?([\w@./+-]+\.[\w]+|[\w@./+-]+/[\w@.+-]+)(?::(\d+)(?:-(\d+))?)?$")


def esc(s):
    return html.escape(str(s), quote=True)


class Ctx:
    def __init__(self, meta):
        self.repo, self.head, self.base = meta["repo"], meta["headSha"], meta["mergeBase"]
        self.src = meta.get("src", "")

    def ref_url(self, ref):
        m = REF.match(ref.strip())
        if not m:
            return None
        # Only real repo files become links, so `user.profile.name` or `/api/x` stay code.
        exists = os.path.isfile(os.path.join(self.src, m.group(2)))
        if not exists and not (m.group(1) and m.group(3)):
            return None
        sha = self.base if m.group(1) else self.head
        lines = "" if not m.group(3) else f"#L{m.group(3)}" + (f"-L{m.group(4)}" if m.group(4) else "")
        return f"https://github.com/{self.repo}/blob/{sha}/{m.group(2)}{lines}"

    def inline(self, text):
        parts = re.split(r"(`[^`]+`)", text)
        out = []
        for p in parts:
            if p.startswith("`") and p.endswith("`") and len(p) > 1:
                code = p[1:-1]
                url = self.ref_url(code)
                tag = f"<code>{esc(code)}</code>"
                out.append(f'<a class="ref" href="{esc(url)}" target="_blank" rel="noopener">{tag}</a>' if url else tag)
                continue
            s = esc(p)
            s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            s = re.sub(r"(?<![\w/&;])#(\d+)\b", lambda m: f'<a href="https://github.com/{self.repo}/pull/{m.group(1)}" target="_blank" rel="noopener">#{m.group(1)}</a>', s)
            s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                       r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
            out.append(s)
        return "".join(out)

    def md(self, text):
        """Paragraphs, `- ` lists, ``` fences, **bold**, `code`, [links](url)."""
        if not text:
            return ""
        out, para, items, fence = [], [], [], None

        def flush():
            if para:
                out.append(f"<p>{self.inline(' '.join(para))}</p>")
                para.clear()
            if items:
                out.append("<ul>" + "".join(f"<li>{self.inline(i)}</li>" for i in items) + "</ul>")
                items.clear()

        for line in str(text).splitlines():
            if fence is not None:
                if line.strip().startswith("```"):
                    out.append(f'<pre class="code"><code>{esc(chr(10).join(fence))}</code></pre>')
                    fence = None
                else:
                    fence.append(line)
                continue
            if line.strip().startswith("```"):
                flush()
                fence = []
            elif re.match(r"^\s*[-*] ", line):
                if para:
                    flush()
                items.append(re.sub(r"^\s*[-*] ", "", line))
            elif not line.strip():
                flush()
            elif items and line.startswith("  "):
                items[-1] += " " + line.strip()
            else:
                if items:
                    flush()
                para.append(line.strip())
        if fence is not None:
            out.append(f'<pre class="code"><code>{esc(chr(10).join(fence))}</code></pre>')
        flush()
        return "".join(out)


STACK_KINDS = {"fixed-above": "Fixed in", "changed-above": "Changed in", "from-below": "From", "breaks-above": "Breaks"}


def stack_prs(stack):
    return (stack or {}).get("ancestors", []) + (stack or {}).get("descendants", [])


def validate(tour, files, stack=None):
    errs = []
    others = {str(p["number"]): p for p in stack_prs(stack)}
    if others:
        briefs = (tour.get("stack") or {}).get("prs", {})
        if not (tour.get("stack") or {}).get("overview"):
            errs.append("this PR is stacked: add `stack.overview`")
        for n, p in others.items():
            if p["state"] != "CLOSED" and not (briefs.get(n) or {}).get("brief"):
                errs.append(f"stack: missing `stack.prs[\"{n}\"].brief` for #{n}")
        for n in briefs:
            if n not in others:
                errs.append(f"stack: #{n} is not in this PR's stack")
    for f in tour.get("findings", []):
        st = f.get("stack")
        if st and (st.get("kind") not in STACK_KINDS or str(st.get("pr")) not in others):
            errs.append(f"finding {f.get('id')}: `stack` needs kind in {list(STACK_KINDS)} and a pr from the stack")
    for key in ("summary", "context", "chapters"):
        if key not in tour:
            errs.append(f"missing top-level `{key}`")
    if errs:
        return errs
    file_ids = {f["id"]: f for f in files}
    hunk_ids = {h["id"]: f for f in files for h in f["hunks"]}
    seen = {}

    def claim(ref, where):
        if ref in file_ids:
            f = file_ids[ref]
            targets = [h["id"] for h in f["hunks"]] or [ref]
        elif ref in hunk_ids:
            targets = [ref]
        else:
            errs.append(f"{where}: unknown ref `{ref}`")
            return
        for t in targets:
            if t in seen:
                errs.append(f"{where}: `{t}` is already shown in {seen[t]}")
            seen[t] = where

    ids = set()
    for i, c in enumerate(tour["chapters"]):
        cid = c.get("id") or f"#{i + 1}"
        if cid in ids:
            errs.append(f"duplicate chapter id `{cid}`")
        ids.add(cid)
        for k in ("title", "explain"):
            if not c.get(k):
                errs.append(f"chapter {cid}: missing `{k}`")
        for it in c.get("items", []):
            claim(it.get("ref", ""), f"chapter {cid}")
    for s in tour.get("skim", []):
        claim(s.get("ref", ""), "skim")
    status = tour.get("status") or {}
    if status.get("level") and status["level"] not in LEVELS:
        errs.append(f"status.level must be one of {LEVELS}")
    expected = {h["id"] for f in files for h in f["hunks"]} | {f["id"] for f in files if not f["hunks"]}
    missing = sorted(expected - set(seen), key=lambda x: [int(n) for n in re.findall(r"\d+", x)])
    if missing and status.get("chapters") != "pending":
        errs.append("not shown anywhere (add to a chapter or `skim`): " + ", ".join(missing))
    fids = set()
    for f in tour.get("findings", []):
        fid = f.get("id", "?")
        if fid in fids:
            errs.append(f"duplicate finding id `{fid}`")
        fids.add(fid)
        if f.get("severity") not in SEVERITIES:
            errs.append(f"finding {fid}: severity must be one of {SEVERITIES}")
        if f.get("verdict") not in VERDICTS:
            errs.append(f"finding {fid}: verdict must be one of {VERDICTS}")
        for k in ("title", "summary", "scenario"):
            if not f.get(k):
                errs.append(f"finding {fid}: missing `{k}`")
        vb = f.get("verifiedBy") or []
        for a in f.get("foundBy", []) + ([vb] if isinstance(vb, str) else vb):
            if a not in AGENTS:
                errs.append(f"finding {fid}: foundBy/verifiedBy must be in {list(AGENTS)}")
        if f.get("chapter") and f["chapter"] not in ids:
            errs.append(f"finding {fid}: unknown chapter `{f['chapter']}`")
    for d in tour.get("descriptionCheck", []):
        if d.get("kind") not in DESC_KINDS:
            errs.append(f"descriptionCheck: kind must be one of {list(DESC_KINDS)}")
    return errs


def chapter_for(finding, tour, files):
    """Place a finding in the chapter that shows its file/line, when the tour didn't say."""
    if finding.get("chapter"):
        return finding["chapter"]
    path, line = finding.get("file"), finding.get("line")
    by_hunk = {}
    for c in tour["chapters"]:
        for it in c.get("items", []):
            by_hunk[it["ref"]] = c["id"]
    for f in files:
        if f["path"] != path:
            continue
        if f["id"] in by_hunk:
            return by_hunk[f["id"]]
        for h in f["hunks"]:
            if h["id"] in by_hunk and (line is None or h["newStart"] <= line < h["newStart"] + h["newLines"]):
                return by_hunk[h["id"]]
        for h in f["hunks"]:
            if h["id"] in by_hunk:
                return by_hunk[h["id"]]
    return None


def render_hunk(ctx, f, h):
    rows, run = [], []
    lines = h["lines"]

    def flush_run():
        # A long block of removed lines (a rewrite) is collapsed so the new code stays readable.
        if len(run) > COLLAPSE_DELETED:
            rows.append(f'<details class="delrun"><summary>{len(run)} removed lines</summary>{"".join(run)}</details>')
        else:
            rows.extend(run)
        run.clear()

    for kind, o, n, text in lines[:MAX_HUNK_LINES]:
        cls = {"+": "add", "-": "del", "\\": "meta"}.get(kind, "ctx")
        row = (f'<div class="dl {cls}"><span class="ln">{o or ""}</span><span class="ln">{n or ""}</span>'
               f'<span class="mk">{esc(kind if kind != " " else "")}</span><span class="tx">{esc(text)}</span></div>')
        if kind == "-":
            run.append(row)
            continue
        flush_run()
        rows.append(row)
    flush_run()
    if len(lines) > MAX_HUNK_LINES:
        url = f"https://github.com/{ctx.repo}/blob/{ctx.head}/{f['path']}#L{h['newStart'] + MAX_HUNK_LINES}"
        rows.append(f'<div class="dl meta"><span class="tx">… {len(lines) - MAX_HUNK_LINES} more lines. '
                    f'<a href="{esc(url)}" target="_blank" rel="noopener">Read the rest on GitHub</a></span></div>')
    head = f'@@ -{h["oldStart"]},{h["oldLines"]} +{h["newStart"]},{h["newLines"]} @@ {h["section"]}'
    return f'<div class="hunkhead">{esc(head)}</div><div class="diff" role="region" aria-label="diff" tabindex="0">{"".join(rows)}</div>'


def file_head(ctx, f):
    status = {"added": "Added", "deleted": "Deleted", "renamed": "Renamed"}.get(f["status"], "Modified")
    name = esc(f["path"]) if f["status"] != "renamed" else f'{esc(f["old"])} → {esc(f["path"])}'
    url = f"https://github.com/{ctx.repo}/blob/{ctx.head}/{f['path']}"
    return (f'<div class="filehead"><span class="fstat s-{f["status"]}">{status}</span>'
            f'<a href="{esc(url)}" target="_blank" rel="noopener" class="fpath">{name}</a>'
            f'<span class="fnum"><span class="plus">+{f["additions"]}</span> <span class="minus">−{f["deletions"]}</span></span></div>')


def render_item(ctx, it, files):
    ref = it["ref"]
    for f in files:
        if f["id"] == ref:
            body = "".join(render_hunk(ctx, f, h) for h in f["hunks"]) or '<p class="muted">No textual diff (binary or rename only).</p>'
            break
        h = next((h for h in f["hunks"] if h["id"] == ref), None)
        if h:
            body = render_hunk(ctx, f, h)
            break
    note = f'<div class="itemnote">{ctx.md(it["note"])}</div>' if it.get("note") else ""
    status = {"added": "Added", "deleted": "Deleted", "renamed": "Renamed"}.get(f["status"], "Modified")
    name = esc(f["path"]) if f["status"] != "renamed" else f'{esc(f["old"])} → {esc(f["path"])}'
    url = f"https://github.com/{ctx.repo}/blob/{ctx.head}/{f['path']}"
    lines = sum(len(h["lines"]) for h in f["hunks"] if ref in (f["id"], h["id"]))
    # Collapsed by default: the notes carry the tour; code is one click away.
    return (f'<div class="item">{note}<details class="code"><summary class="filehead">'
            f'<span class="fstat s-{f["status"]}">{status}</span><span class="fpath">{name}</span>'
            f'<span class="fnum"><span class="plus">+{f["additions"]}</span> <span class="minus">−{f["deletions"]}</span></span>'
            f'<span class="showcode">{lines} lines</span></summary>'
            f'<div class="codelinks"><a href="{esc(url)}" target="_blank" rel="noopener">Open the file on GitHub</a></div>{body}</details></div>')


def see_list(ctx, see):
    if not see:
        return ""
    items = []
    for s in see:
        ref, note = (s, "") if isinstance(s, str) else (s.get("ref", ""), s.get("note", ""))
        items.append(f'<li>{ctx.inline("`" + ref + "`")}{" " + ctx.inline(note) if note else ""}</li>')
    return f'<div class="see"><h5>Where to look</h5><ul>{"".join(items)}</ul></div>'


def chip(cls, text):
    return f'<span class="chip {cls}">{esc(text)}</span>'


def render_finding(ctx, f, chapter_title):
    loc = ""
    if f.get("file"):
        ref = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
        url = ctx.ref_url(ref) or f"https://github.com/{ctx.repo}/blob/{ctx.head}/{f['file']}"
        loc = f'<a class="ref" href="{esc(url)}" target="_blank" rel="noopener"><code>{esc(ref)}</code></a>'
    evidence = ""
    if f.get("evidence"):
        lis = "".join(f'<li>{ctx.inline("`" + e["ref"] + "`") if e.get("ref") else ""} {ctx.inline(e.get("note", ""))}</li>'
                      for e in f["evidence"])
        evidence = f"<h5>Evidence</h5><ul class='evidence'>{lis}</ul>"
    repro = ""
    if f.get("repro"):
        r = f["repro"]
        label = {"failed-as-predicted": "Reproduced", "passed": "Did not reproduce", "not-run": "Not run"}.get(r.get("status"), r.get("status", ""))
        cmd = f'<pre class="code"><code>{esc(r["command"])}</code></pre>' if r.get("command") else ""
        outp = f'<pre class="code out"><code>{esc(r["output"])}</code></pre>' if r.get("output") else ""
        repro = f'<h5>Reproduction · {esc(label)}</h5>{cmd}{outp}'
    fix = f"<h5>Suggested fix</h5>{ctx.md(f['fix'])}" if f.get("fix") else ""
    vlabel = "The two verifiers disagree" if f["verdict"] == "DISPUTED" else "Verifier"
    verifier = f"<h5>{vlabel}</h5>{ctx.md(f['verifier'])}" if f.get("verifier") else ""
    dismissed = f["verdict"] == "DISMISSED"
    triage = "" if dismissed else f'''
      <div class="triage" data-finding="{esc(f['id'])}">
        <div class="tbtns" role="group" aria-label="Your call on {esc(f['id'])}">
          <button type="button" data-v="agree" aria-pressed="false">Agree, post it</button>
          <button type="button" data-v="ask" aria-pressed="false">Ask the author</button>
          <button type="button" data-v="reject" aria-pressed="false">Not an issue</button>
        </div>
        <label class="sr" for="fn-{esc(f['id'])}">Your note on {esc(f['id'])}</label>
        <textarea id="fn-{esc(f['id'])}" data-fnote="{esc(f['id'])}" rows="2" placeholder="Your note (optional). Posted with the comment."></textarea>
      </div>'''
    fid = esc(f["id"])
    fask = "" if dismissed else (
        f'<div class="ask fask" data-ask="{fid}" data-kind="act"><label class="sr" for="ask-{fid}">Ask Claude about {fid}</label>'
        f'<div class="askrow"><input id="ask-{fid}" type="text" autocomplete="off" '
        f'placeholder="Ask Claude about this finding, e.g. Does a later PR fix this? Reword it for the author.">'
        f'<button type="button" class="askgo">Ask Claude</button></div><div class="answers" aria-live="polite"></div></div>')
    where = f'<span class="muted">in {esc(chapter_title)}</span>' if chapter_title else ""
    st = f.get("stack")
    stack_label = f"{STACK_KINDS[st['kind']]} #{st['pr']}" if st else ""
    stack_chip = chip("stk " + st["kind"], stack_label) if st else ""
    who = " and ".join(AGENTS[a] for a in f.get("foundBy", []))
    vb = f.get("verifiedBy") or []
    vb = [vb] if isinstance(vb, str) else vb
    checked = f', checked by {" and ".join(AGENTS[a] for a in vb)}' if vb else ""
    by = f'<span class="muted">found by {who}{checked}</span>' if who else ""
    stack_note = f'<div class="stacknote">{ctx.inline("**" + stack_label + ":** " + st.get("note", ""))}</div>' if st else ""
    return f'''
    <article class="finding sev-{f['severity']}{' dismissed' if dismissed else ''}" id="finding-{esc(f['id'])}">
      <header>
        <div class="fmeta">{chip('sev ' + f['severity'], f['severity'])}{chip('ver ' + f['verdict'].lower(), f['verdict'].title())}
          {stack_chip}<span class="fid">{esc(f['id'])}</span>{loc}{where}{by}</div>
        <h4>{esc(f['title'])}</h4>
      </header>
      <div class="fbody">{stack_note}{f'<p class="impact">{ctx.inline(f["impact"])}</p>' if f.get("impact") else ""}{ctx.md(f['summary'])}
        <h5>How it breaks</h5>{ctx.md(f['scenario'])}
        {evidence}{fix}{verifier}{repro}
      </div>{triage}{fask}
    </article>'''


def render_stack(ctx, stack, tour, pr):
    info = tour.get("stack") or {}
    briefs = info.get("prs", {})
    rows = [f'<li class="srow sbase"><span class="snode" aria-hidden="true"></span><div><code>{esc(stack["bottomBase"])}</code> <span class="muted">base branch</span></div></li>']

    def row(p, focus=False):
        n = str(p["number"])
        b = briefs.get(n) or {}
        state = "draft" if p.get("isDraft") and p["state"] == "OPEN" else p["state"].lower()
        on = f' <span class="muted">on {ctx.inline("#" + str(p["parent"]))}</span>' if p.get("parent") else ""
        shared = ""
        if p.get("sharedFiles"):
            items = "".join(f"<li><code>{esc(x)}</code></li>" for x in p["sharedFiles"])
            shared = f'<details class="shared"><summary>Touches {len(p["sharedFiles"])} file(s) this PR also changes</summary><ul>{items}</ul></details>'
        brief = ctx.md(b.get("brief", "")) if not focus else f'<p>{ctx.inline((tour.get("summary") or {}).get("headline", ""))}</p>'
        rel = f'<div class="srel"><h5>How it relates</h5>{ctx.md(b["relation"])}</div>' if b.get("relation") and not focus else ""
        you = '<span class="you">Reviewing</span>' if focus else ""
        return (f'<li class="srow{" sfocus" if focus else ""}{" sclosed" if p["state"] == "CLOSED" else ""}"><span class="snode" aria-hidden="true"></span><div class="sbody">'
                f'<div class="shead"><a href="{esc(p["url"])}" target="_blank" rel="noopener" class="snum">#{p["number"]}</a>'
                f'<span class="stitle">{esc(p["title"])}</span>{chip("st " + state, state)}{you}'
                f'<span class="fnum"><span class="plus">+{p["additions"]}</span> <span class="minus">−{p["deletions"]}</span></span>{on}</div>'
                f'{brief}{rel}{shared}</div></li>')

    for p in stack["ancestors"]:
        rows.append(row(p))
    focus = {"number": pr["number"], "title": pr["title"], "url": pr["url"], "state": pr["state"], "isDraft": pr.get("isDraft"),
             "additions": pr["additions"], "deletions": pr["deletions"]}
    rows.append(row(focus, True))
    for p in stack["descendants"]:
        rows.append(row(p))
    health = "".join(f"<li>{ctx.inline(h)}</li>" for h in stack.get("health", []))
    health = f'<div class="health"><h3>Stack health</h3><ul>{health}</ul></div>' if health else ""
    pos = len(stack["ancestors"]) + 1
    kids = {}
    for p in stack["descendants"]:
        kids.setdefault(p["parent"], []).append(p["number"])
    names = lambda ns: ", ".join(f"#{n}" for n in ns[:-1]) + f" and #{ns[-1]}"
    forks = [f"{names(ns)} are {'both' if len(ns) == 2 else 'all'} built on #{parent}" for parent, ns in kids.items() if len(ns) > 1]
    branch = f'<p>{ctx.inline("The stack branches: " + "; ".join(forks) + ".")}</p>' if forks else ""
    return f'''
    <section id="stack" class="sec">
      <h2>Where this PR sits in its stack</h2>
      <p class="muted">PR {pos} from the bottom of a stack of {len(stack_prs(stack)) + 1}. The tour reviews #{pr["number"]} only; the others are context. PRs lower in the list are what it builds on; higher ones build on it.</p>
      {ctx.md(info.get("overview", ""))}{branch}{health}
      <ol class="stack" reversed>{"".join(reversed(rows))}</ol>
    </section>'''


def build(meta, pr, tour, files, stack=None):
    ctx = Ctx(meta)
    stacked = bool(stack_prs(stack))
    s, c = tour["summary"], tour["context"]
    chapters = tour["chapters"]
    findings = tour.get("findings", [])
    titles = {ch["id"]: ch["title"] for ch in chapters}
    for f in findings:
        f["_chapter"] = chapter_for(f, tour, files)
    sev_rank = {k: i for i, k in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (f["verdict"] == "DISMISSED", sev_rank[f["severity"]]))
    live = [f for f in findings if f["verdict"] != "DISMISSED"]
    # A chapter's severity is its worst live finding; most severe chapters first, ties in written order.
    worst = {}
    for f in live:
        if f["_chapter"]:
            worst[f["_chapter"]] = min(worst.get(f["_chapter"], 99), sev_rank[f["severity"]])
    chapters = sorted(chapters, key=lambda ch: worst.get(ch["id"], 99))
    sev_of = {cid: SEVERITIES[r] for cid, r in worst.items()}
    sev_chip = lambda cid: chip("sev " + sev_of[cid], sev_of[cid]) if cid in sev_of else ""

    nav = ['<li><a href="#overview">Overview</a></li>'] + (['<li><a href="#stack">Stack</a></li>'] if stacked else []) + ['<li><a href="#context">Before you read</a></li>']
    if tour.get("descriptionCheck"):
        nav.append('<li><a href="#description">Description check</a></li>')
    nav.append('<li class="navh">Chapters</li>')
    if (tour.get("status") or {}).get("chapters") == "pending":
        nav.append('<li class="muted navpend">Being written…</li>')
    for i, ch in enumerate(chapters, 1):
        n = sum(1 for f in live if f["_chapter"] == ch["id"])
        badge = f'<span class="nbadge" title="{n} finding(s)">{n}</span>' if n else ""
        nav.append(f'<li class="navch"><a href="#ch-{esc(ch["id"])}"><span class="tick" data-tick="{esc(ch["id"])}" aria-hidden="true"></span>'
                   f'<span class="navn">{i}</span><span class="navt">{esc(ch["title"])} {sev_chip(ch["id"])}</span>{badge}</a></li>')
    if tour.get("skim"):
        nav.append('<li><a href="#skim">Skim list</a></li>')
    nav.append(f'<li><a href="#findings">Findings <span class="muted">{len(live)}</span></a></li>')
    if tour.get("openQuestions"):
        nav.append('<li><a href="#questions">Questions for the author</a></li>')
    nav.append('<li><a href="#finish">Finish review</a></li>')

    main = []
    risk = s.get("risk", "medium")
    main.append(f'''
    <section id="overview" class="sec">
      <p class="lede">{ctx.inline(s.get("headline", ""))}</p>
      <div class="riskrow">{chip('risk ' + risk, risk + ' risk')}<span>{ctx.inline(s.get("riskReason", ""))}</span></div>
      <h3>Why this PR exists</h3>{ctx.md(s.get("why", ""))}
    </section>''')

    if stacked:
        main.append(render_stack(ctx, stack, tour, pr))

    gloss = ""
    if c.get("glossary"):
        rows = "".join(f'<tr><th scope="row">{esc(g["term"])}</th><td>{ctx.inline(g["meaning"])}'
                       f'{" " + ctx.inline("`" + g["ref"] + "`") if g.get("ref") else ""}</td></tr>' for g in c["glossary"])
        gloss = f'<h3>Terms you will meet</h3><div class="tablewrap"><table class="gloss">{rows}</table></div>'
    diagram = f'<h3>How the pieces connect</h3><pre class="mermaid">{esc(c["diagram"])}</pre>' if c.get("diagram") else ""
    quiz = ""
    if c.get("quiz"):
        qs = "".join(f'<details class="quiz"><summary>{ctx.inline(q["q"])}</summary>{ctx.md(q["a"])}</details>' for q in c["quiz"])
        quiz = f'<h3>Check yourself before the diff</h3>{qs}'
    main.append(f'''
    <section id="context" class="sec">
      <h2>Before you read the diff</h2>
      <div class="ba">
        <div><h3>How it works today</h3>{ctx.md(c.get("before", ""))}</div>
        <div><h3>What changes</h3>{ctx.md(c.get("after", ""))}</div>
      </div>{diagram}{gloss}{quiz}
    </section>''')

    if tour.get("descriptionCheck"):
        rows = "".join(f'<li class="dc dc-{d["kind"]}">{chip("dck " + d["kind"], DESC_KINDS[d["kind"]])}'
                       f'<div><p class="claim">{ctx.inline(d.get("claim", ""))}</p>{ctx.md(d.get("detail", ""))}</div></li>'
                       for d in tour["descriptionCheck"])
        main.append(f'''
    <section id="description" class="sec">
      <h2>Does the description match the code?</h2>
      <ul class="dclist">{rows}</ul>
    </section>''')

    ask_chapters = {}
    for i, ch in enumerate(chapters, 1):
        cid = esc(ch["id"])
        items = "".join(render_item(ctx, it, files) for it in ch.get("items", []))
        checks = "".join(f"<li>{ctx.inline(x)}</li>" for x in ch.get("check", []))
        checks = f'<div class="checks"><h3>What to check here</h3><ul>{checks}</ul></div>' if checks else ""
        here = "".join(render_finding(ctx, f, None) for f in live if f["_chapter"] == ch["id"])
        here = f'<h3>Findings in this chapter</h3>{here}' if here else ""
        cid = esc(ch["id"])
        main.append(f'''
    <section id="ch-{cid}" class="sec chapter" data-chapter="{cid}">
      <p class="eyebrow">Chapter {i} of {len(chapters)}</p>
      <h2>{sev_chip(ch["id"])} {esc(ch["title"])}</h2>
      {f'<p class="tldr">{ctx.inline(ch["tldr"])}</p>' if ch.get("tldr") else ""}
      <div class="intent">{ctx.md(ch.get("intent", ""))}</div>
      {ctx.md(ch["explain"])}{see_list(ctx, ch.get("see"))}{checks}
      <div class="items">{'<button type="button" class="codeall" data-codeall="' + cid + '">Show all code in this chapter</button>' if items else ""}{items}</div>
      {here}
      <div class="ask" data-ask="{cid}">
        <label for="ask-{cid}">Ask Claude about this chapter</label>
        <div class="askrow"><input id="ask-{cid}" type="text" autocomplete="off" placeholder="e.g. Who else calls this? Is it covered by a test?">
          <button type="button" class="askgo">Ask Claude</button></div>
        <div class="answers" aria-live="polite"></div>
      </div>
      <label class="notelbl" for="cn-{cid}">Your comments on this chapter</label>
      <textarea id="cn-{cid}" data-cnote="{cid}" rows="3" placeholder="Anything you want to tell the author about this part. Goes into the review body."></textarea>
      <div class="readrow"><button type="button" class="readbtn" data-read="{cid}" aria-pressed="false">Mark chapter as read</button></div>
    </section>''')
        lines = [f"Chapter {i}: {ch['title']}", ch.get("intent", ""), ch["explain"]]
        for it in ch.get("items", []):
            for f in files:
                hs = f["hunks"] if f["id"] == it["ref"] else [h for h in f["hunks"] if h["id"] == it["ref"]]
                if hs:
                    lines.append(f"--- {f['path']}" + (f" (note: {it['note']})" if it.get("note") else ""))
                    for h in hs:
                        lines.append(f"@@ -{h['oldStart']} +{h['newStart']} @@ {h['section']}")
                        lines.extend(k + t for k, _, _, t in h["lines"][:MAX_HUNK_LINES])
        ask_chapters[ch["id"]] = "\n".join(lines)[:60000]

    if tour.get("skim"):
        by_id = {f["id"]: f for f in files}
        by_hunk = {h["id"]: f for f in files for h in f["hunks"]}
        rows = []
        for sk in tour["skim"]:
            f = by_id.get(sk["ref"]) or by_hunk.get(sk["ref"])
            label = esc(f["path"]) + ("" if sk["ref"] == f["id"] else f' <span class="muted">({esc(sk["ref"])})</span>')
            url = f"https://github.com/{ctx.repo}/blob/{ctx.head}/{f['path']}"
            rows.append(f'<tr><td><a href="{esc(url)}" target="_blank" rel="noopener" class="fpath">{label}</a></td>'
                        f'<td class="num"><span class="plus">+{f["additions"]}</span> <span class="minus">−{f["deletions"]}</span></td>'
                        f'<td>{ctx.inline(sk.get("reason", ""))}</td></tr>')
        main.append(f'''
    <section id="skim" class="sec">
      <h2>Skim list</h2>
      <p class="muted">Generated, mechanical or low-risk changes. Open one only if you want to.</p>
      <div class="tablewrap"><table class="skim"><thead><tr><th>File</th><th>Lines</th><th>Why it is here</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
    </section>''')

    flist = "".join(f'<li><a href="#finding-{esc(f["id"])}">{chip("sev " + f["severity"], f["severity"])} '
                    f'<span class="fid">{esc(f["id"])}</span> {esc(f["title"])}</a>'
                    f'<span class="muted"> · {esc(titles.get(f["_chapter"], "General"))}</span> '
                    f'<span class="tstate" data-tstate="{esc(f["id"])}"></span></li>' for f in live)
    general = "".join(render_finding(ctx, f, None) for f in live if not f["_chapter"])
    general = f"<h3>Not tied to a chapter</h3>{general}" if general else ""
    dismissed = [f for f in findings if f["verdict"] == "DISMISSED"]
    dis = ""
    if dismissed:
        dis = (f'<details class="dismissed-group"><summary>{len(dismissed)} candidate finding(s) the verifier dismissed</summary>'
               + "".join(render_finding(ctx, f, titles.get(f["_chapter"])) for f in dismissed) + "</details>")
    status = tour.get("status") or {}
    level = status.get("level", "regular")
    intro = {
        "fast": "Fast review: one reviewer, no verification. Treat each finding as a lead to check yourself.",
        "regular": "Each finding was checked by a verifier from a different model that tried to disprove it.",
        "deep": "Claude and Codex reviewed the PR independently, then each tried to disprove the other's findings. Findings both raised are merged into one and say so.",
    }[level]
    legend = ("Confirmed: the verifier traced the failure in the code. Plausible: the logic holds but depends on something the code alone cannot show. "
              "Disputed: the two verifiers disagree; both positions are shown.") if level != "fast" else ""
    models = status.get("models") or {}
    who_ran = []
    if models.get("reviewers"):
        who_ran.append("Reviewed by " + " and ".join(models["reviewers"]))
    if models.get("verifiers"):
        who_ran.append("verified by " + " and ".join(models["verifiers"]))
    intro += (" " + ", ".join(who_ran) + ".") if who_ran else ""
    if status.get("findings") == "pending":
        body = f'<p class="pending">{esc(status.get("note") or "Reviewers are running. Findings will appear here, inside their chapters, when they are verified.")}</p>'
    else:
        empty = ('<p>No findings.</p>' if level == "fast" else '<p>No findings survived verification.</p>') if not live else ""
        body = f'{empty}<ul class="flist">{flist}</ul>{general}{dis}'
    main.append(f'''
    <section id="findings" class="sec">
      <h2>Findings</h2>
      <p class="muted">{intro} {legend}</p>
      {body}
    </section>''')

    if tour.get("openQuestions"):
        qs = "".join(f"<li>{ctx.inline(q)}</li>" for q in tour["openQuestions"])
        main.append(f'<section id="questions" class="sec"><h2>Questions for the author</h2><ul>{qs}</ul></section>')

    main.append('''
    <section id="finish" class="sec">
      <h2>Finish review</h2>
      <div id="finishSummary" class="finsum"></div>
      <label class="notelbl" for="finishText">Anything else for Claude</label>
      <textarea id="finishText" rows="5" placeholder="e.g. Merge F2 and F4 into one comment. Ask the author about the rollout plan. Open a follow-up issue for the missing tests."></textarea>
      <p class="muted">Claude reads this with your calls and notes when it drafts the review. Anything outside this page, like opening an issue, it confirms with you in Claude Code first.</p>
      <div class="finbtns"><button type="button" id="draftBtn" class="primary" data-needs-session="1">Draft my review</button><span id="draftStatus" class="muted" role="status"></span></div>
      <div id="draftBox" class="draftbox" hidden>
        <h3>Review draft</h3>
        <p class="muted small" id="draftMeta"></p>
        <p class="warn small" id="draftWarn"></p>
        <h5>Review comment</h5><pre id="draftBody"></pre>
        <h5>Line comments</h5><ul id="draftComments"></ul>
        <div class="finbtns"><button type="button" id="postBtn" class="primary" data-needs-session="1">Post this review</button>
          <span class="muted small">Posts a comment review on GitHub after you confirm in Claude Code. Never an approval or a change request.</span></div>
      </div>
      <p id="postedLine" hidden>Posted: <a id="postedLink" target="_blank" rel="noopener"></a></p>
      <div id="sessionHint">
        <p class="muted" id="storeNote">Claude Code isn't reachable from this page right now. In the session that built this tour, say <strong>reconnect the tour</strong>, or say <strong>finalize the PR tour</strong> there. If Claude can't read your notes from the page, copy them into the chat.</p>
        <div class="finbtns"><button type="button" id="copyNotes">Copy my notes</button><span id="copyMsg" class="muted" role="status"></span></div>
        <textarea id="notesOut" class="notesout" rows="4" readonly hidden aria-label="Your notes as text"></textarea>
      </div>
    </section>''')

    data = {
        "key": f"{meta['repo']}#{meta['number']}@{meta['headSha'][:7]}",
        "chapters": [{"id": ch["id"], "title": ch["title"]} for ch in chapters],
        "findings": [{"id": f["id"], "title": f["title"]} for f in live],
        "ask": {
            "base": (f"Pull request {meta['repo']}#{meta['number']}: {pr['title']}\n\n"
                     f"Summary: {s.get('headline', '')}\nWhy: {s.get('why', '')}\n\n"
                     f"How it works today:\n{c.get('before', '')}\n\nWhat changes:\n{c.get('after', '')}"
                     + (stack_text(stack, tour) if stacked else ""))[:30000],
            "chapters": ask_chapters,
            "findings": {f["id"]: f"Finding {f['id']}: {f['title']}\n{f.get('impact', '')}\n{f['summary']}\nHow it breaks: {f['scenario']}\nFix: {f.get('fix', '')}" for f in live},
        },
    }
    if stacked:
        below = stack["ancestors"][-1]["number"] if stack["ancestors"] else None
        above = [p["number"] for p in stack["descendants"] if p.get("depth") == 1]
        bits = ([f"on #{below}"] if below else []) + ([f"under {', '.join('#' + str(n) for n in above)}"] if above else [])
        stack_meta = f'<span><a href="#stack">Stacked</a> {ctx.inline(" · ".join(bits))}</span>'
    else:
        stack_meta = ""
    head_meta = stack_meta + (f'<span>{esc(pr["author"]["login"])}</span><span><code>{esc(pr["baseRefName"])}</code> ← <code>{esc(pr["headRefName"])}</code></span>'
                 f'<span><span class="plus">+{pr["additions"]}</span> <span class="minus">−{pr["deletions"]}</span> in {pr["changedFiles"]} files</span>'
                 f'<span>at <code>{meta["headSha"][:7]}</code></span>')
    return {
        "TITLE": esc(f"{meta['repo'].split('/')[-1]} #{meta['number']} tour"),
        "PR_TITLE": esc(pr["title"]),
        "PR_URL": esc(pr["url"]),
        "PR_REF": esc(f"{meta['repo']}#{meta['number']}"),
        "HEAD_META": head_meta + f'<span>{esc((tour.get("status") or {}).get("level", "regular"))} review</span>',
        "STATUS": status_banner(tour),
        "NAV": "".join(nav),
        "MAIN": "".join(main),
        "DATA": json.dumps(data).replace("</", "<\\/"),
    }


def status_banner(tour):
    st = tour.get("status") or {}
    waiting = [label for key, label in (("chapters", "the chapters"), ("findings", "the findings")) if st.get(key) == "pending"]
    if not waiting:
        return ""
    return (f'<div class="statusbar" role="status"><span class="pulse" aria-hidden="true"></span>'
            f'<span><strong>Reviewers are running. The tour is not fully ready.</strong> Still coming: {" and ".join(waiting)}. '
            f'This page updates in place; your notes are kept.</span></div>')


def stack_text(stack, tour):
    briefs = (tour.get("stack") or {}).get("prs", {})
    lines = ["\n\nThis PR is part of a stack (bottom first). Only this PR is under review:", (tour.get("stack") or {}).get("overview", "")]
    for p in stack["ancestors"]:
        lines.append(f"- below: #{p['number']} {p['title']} [{p['state']}]: {(briefs.get(str(p['number'])) or {}).get('brief', '')}")
    for p in stack["descendants"]:
        lines.append(f"- above (on #{p['parent']}): #{p['number']} {p['title']} [{p['state']}]: {(briefs.get(str(p['number'])) or {}).get('brief', '')}")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    run = args[0]
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(run, "tour.html")
    load = lambda name: json.load(open(os.path.join(run, name), encoding="utf-8"))
    meta, pr, tour, files = load("meta.json"), load("pr.json"), load("tour.json"), load("hunks.json")["files"]
    stack = load("stack.json") if os.path.exists(os.path.join(run, "stack.json")) else None
    errs = validate(tour, files, stack)
    if errs:
        print("tour.json has problems:\n- " + "\n- ".join(errs), file=sys.stderr)
        sys.exit(1)
    page = open(TEMPLATE, encoding="utf-8").read()
    vals = build(meta, pr, tour, files, stack)
    page = re.sub(r"\{\{(\w+)\}\}", lambda m: vals.get(m.group(1), m.group(0)), page)  # one pass: PR text may contain {{…}}
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(out)


if __name__ == "__main__":
    main()
