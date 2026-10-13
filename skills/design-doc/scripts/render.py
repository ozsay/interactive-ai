#!/usr/bin/env python3
"""Validate RUN/design.json and render it as the working page, or export it as markdown.

Usage: render.py <RUN> [--out page.html]      validate and render the page
       render.py <RUN> --md <out.md>          export the design doc as markdown
       render.py <RUN> --signoff              list what still blocks sign-off (exit 1 if anything)

The page shows each stage only once Claude has drafted it, and asks the human for one thing at a
time. See reference/design-format.md.
"""
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "template.html")
STAGES = [("frame", "Frame"), ("ground", "How it works today"), ("decide", "Decisions"), ("design", "Design"),
          ("challenge", "Challenge"), ("defend", "Defend"), ("done", "Sign off")]
STAGE_IDS = [s for s, _ in STAGES]
REF = re.compile(r"^([\w@./+-]+\.[\w]+|[\w@./+-]+/[\w@.+-]+)(?::(\d+)(?:-(\d+))?)?$")
GRADES = {"covered": "Covered by the doc", "partly": "Partly covered", "missing": "The doc doesn't say this"}
RESPONSES = {"rebut": "Rebutted", "accept": "Accepted", "park": "Parked"}
REOPEN = ('<details class="editbox"><summary>Reopen this decision</summary>'
          '<textarea data-field="text" rows="2" placeholder="What changed?" aria-label="Why reopen"></textarea>'
          '<div class="btns"><button type="button" data-send="reopen" data-need-text>Reopen</button></div></details>')
RESPOND = ('<textarea data-field="text" rows="3" placeholder="Your answer to this objection" aria-label="Your response"></textarea>'
           '<div class="btns"><button type="button" class="primary" data-send="respond" data-response="rebut" data-need-text>Rebut</button>'
           '<button type="button" data-send="respond" data-response="accept">Accept, change the plan</button>'
           '<button type="button" data-send="respond" data-response="park">Park as open question</button></div>')


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


class Ctx:
    def __init__(self, meta):
        self.repo, self.head, self.src = meta.get("repo", ""), meta.get("head", ""), meta.get("src", "")
        self.github = "/" in self.repo

    def ref_url(self, ref):
        m = REF.match(ref.strip())
        if not m or not self.github or not os.path.isfile(os.path.join(self.src, m.group(1))):
            return None
        lines = "" if not m.group(2) else f"#L{m.group(2)}" + (f"-L{m.group(3)}" if m.group(3) else "")
        return f"https://github.com/{self.repo}/blob/{self.head}/{m.group(1)}{lines}"

    def inline(self, text):
        out = []
        for p in re.split(r"(`[^`]+`)", str(text or "")):
            if p.startswith("`") and p.endswith("`") and len(p) > 1:
                url, tag = self.ref_url(p[1:-1]), f"<code>{esc(p[1:-1])}</code>"
                out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">{tag}</a>' if url else tag)
                continue
            s = esc(p)
            s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
            out.append(s)
        return "".join(out)

    def md(self, text):
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
            elif line.strip().startswith("```"):
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

    def ul(self, items, cls=""):
        items = [i for i in (items or []) if i]
        return f'<ul class="{cls}">' + "".join(f"<li>{self.inline(i)}</li>" for i in items) + "</ul>" if items else ""

    def refs(self, refs):
        refs = [r for r in (refs or []) if r]
        return ('<p class="refs small">' + " · ".join(self.inline(f"`{r}`") for r in refs) + "</p>") if refs else ""


# ---------------------------------------------------------------- validation

def validate(d):
    errs = []
    decs = d.get("decisions", [])
    ids = {}
    things = ([("decision", x) for x in decs] + [("section", x) for x in d.get("design", {}).get("sections", [])]
              + [("objection", x) for x in d.get("objections", [])] + [("question", x) for x in d.get("questions", [])]
              + [("defense", x) for x in d.get("defense", [])] + [("assumption", x) for x in d.get("frame", {}).get("assumptions", [])])
    for kind, x in things:
        i = x.get("id")
        if not i:
            errs.append(f"a {kind} has no id")
        elif i in ids:
            errs.append(f"id {i} is used twice")
        ids[i] = kind
    f = d.get("frame", {})
    if f.get("status") not in ("clarifying", "draft", "approved"):
        errs.append("frame.status must be clarifying, draft or approved")
    if f.get("status") == "clarifying" and f.get("assumptions"):
        errs.append("no assumptions while clarifying: ask instead, then draft the Frame")
    if f.get("status") == "draft" and len(f.get("assumptions", [])) > 3:
        errs.append("more than 3 assumptions: the prompt is too vague to guess; switch the Frame to clarifying")
    if d.get("stage") not in STAGE_IDS:
        errs.append(f"stage must be one of {STAGE_IDS}")
    targets = set(ids) | {"frame", "ground", "decisions", "design", "doc"}
    by_id = {x["id"]: x for x in decs if x.get("id")}
    for x in decs:
        opts = {o.get("id") for o in x.get("options", [])}
        if x.get("status") not in ("upcoming", "open", "decided", "parked", "dropped"):
            errs.append(f"{x.get('id')}: status must be upcoming, open, decided, parked or dropped")
        if x.get("status") in ("open", "decided") and len(opts) < 2:
            errs.append(f"{x.get('id')}: needs at least two options")
        if x.get("recommend") and x["recommend"] not in opts:
            errs.append(f"{x.get('id')}: recommend `{x['recommend']}` is not an option")
        if x.get("status") == "decided" and x.get("pick") not in opts:
            errs.append(f"{x.get('id')}: decided, but pick `{x.get('pick')}` is not an option")
        for dep in x.get("dependsOn", []):
            if dep not in by_id:
                errs.append(f"{x.get('id')}: dependsOn {dep}, which is not a decision")
            elif x.get("status") == "open" and by_id[dep].get("status") not in ("decided", "dropped"):
                errs.append(f"{x.get('id')} is open but {dep} is not decided yet")
    if sum(x.get("status") == "open" for x in decs) > 1:
        errs.append("more than one decision is open; open one at a time")
    if sum(s.get("status") == "open" for s in d.get("design", {}).get("sections", [])) > 1:
        errs.append("more than one design section is open; open one at a time")
    for x in d.get("questions", []) + d.get("objections", []):
        if x.get("target") and x["target"] not in targets:
            errs.append(f"{x.get('id')}: target {x['target']} does not exist")
    return errs


def blockers(d):
    out = []
    for x in d.get("decisions", []):
        if x.get("status") not in ("decided", "parked", "dropped"):
            out.append(f"{x['id']} ({x.get('title', '')}) is not decided or parked")
        elif x.get("status") == "decided" and x.get("key") and not (x.get("rationale") or "").strip():
            out.append(f"{x['id']} is a key decision without your rationale")
    for sec in d.get("design", {}).get("sections", []):
        if sec.get("status") != "approved":
            out.append(f"design section {sec['id']} ({sec.get('title', '')}) is not approved")
    for o in d.get("objections", []):
        if not (o.get("response") or {}).get("kind"):
            out.append(f"objection {o['id']} has no response")
    for x in d.get("defense", []):
        if not (x.get("answer") or "").strip():
            out.append(f"defense question {x['id']} is not answered")
    for q in d.get("questions", []):
        if q.get("status", "open") == "open":
            out.append(f"question {q['id']} is open (answer or park it)")
    if d.get("frame", {}).get("status") != "approved":
        out.append("the Frame is not approved")
    if d.get("challengeStatus") != "done":
        out.append("the challenge has not run")
    return out


# ---------------------------------------------------------------- page pieces

def req(target, body, cls="", anchor=True):
    """A box whose buttons send a request about `target` to the session."""
    rid = f' id="req-{esc(target)}"' if anchor else ""
    return f'<div class="req {cls}"{rid} data-target="{esc(target)}">{body}<p class="reqstate small" role="status"></p></div>'


def edit_box(target, placeholder="What should change?"):
    return req(target, f'''<details class="editbox"><summary>Something's off? Ask for a change</summary>
      <textarea data-field="text" rows="2" placeholder="{esc(placeholder)}" aria-label="Requested change"></textarea>
      <div class="btns"><button type="button" data-send="edit">Send the change</button></div></details>''', anchor=False)


def ask_box(target, label="Ask Claude about this"):
    return f'''<div class="ask" data-ask="{esc(target)}"><label class="small" for="ask-{esc(target)}">{esc(label)}</label>
      <div class="askrow"><input id="ask-{esc(target)}" type="text" placeholder="e.g. who else calls this? what breaks if we skip it?">
      <button type="button" class="askgo">Ask Claude</button></div><div class="answers"></div></div>'''


def question_cards(ctx, d, target):
    out = []
    for q in d.get("questions", []):
        if q.get("target") != target:
            continue
        st = q.get("status", "open")
        if st != "open":
            out.append(f'<div class="qcard done"><p class="small muted">{esc(q["id"])} · {"answered" if st == "answered" else "parked"}</p>'
                       f'<p><strong>{ctx.inline(q.get("q"))}</strong></p><p class="human">{esc(q.get("answer") or "Not sure yet.")}</p></div>')
            continue
        opts = "".join(f'<button type="button" data-send="answer" data-text="{esc(o)}"{" class=rec" if o == q.get("recommend") else ""}>{esc(o)}</button>' for o in q.get("options", []))
        parts = "".join(f"<h5>{t}</h5>{ctx.md(q[k])}" for k, t in (("found", "What I found"), ("why", "Why I can't decide this alone"),
                                                                   ("changes", "What changes with the answer")) if q.get(k))
        body = f'''<p class="small eyebrow">Claude needs your call · {esc(q["id"])}</p>
          <h4>{ctx.inline(q.get("q"))}</h4>{parts}
          {f'<p class="small">I would pick: <strong>{esc(q["recommend"])}</strong></p>' if q.get("recommend") else ""}
          {f'<div class="btns">{opts}</div>' if opts else ""}
          <textarea data-field="text" rows="2" placeholder="Or answer in your own words" aria-label="Your answer"></textarea>
          <div class="btns"><button type="button" class="primary" data-send="answer">Send answer</button><button type="button" data-send="park">Not sure yet</button></div>'''
        out.append(req(q["id"], body, cls="qcard"))
    return "".join(out)


def stage_state(d, sid):
    cur = STAGE_IDS.index(d.get("stage", "frame"))
    i = STAGE_IDS.index(sid)
    return "done" if i < cur else "here" if i == cur else "later"


def later(text):
    return f'<p class="later">{esc(text)}</p>'


def sec_clarify(ctx, d):
    """A vague prompt: build the Frame through a short interview, one question at a time."""
    f = d.get("frame", {})
    qs = [q for q in d.get("questions", []) if q.get("target") == "frame"]
    asked = "".join(f'<li><p class="q">{ctx.inline(q.get("q"))}</p><p class="human">{esc(q.get("answer") or "Not sure yet.")}</p></li>'
                    for q in qs if q.get("status", "open") != "open")
    cur = next((q for q in qs if q.get("status", "open") == "open"), None)
    if cur:
        opts = "".join(f'<button type="button" data-send="answer" data-text="{esc(o)}">{esc(o)}</button>' for o in cur.get("options", []))
        found = f'<p class="small muted">{ctx.inline(cur["found"])}</p>' if cur.get("found") else ""
        now = req(cur["id"], f'''<h3 class="cq">{ctx.inline(cur.get("q"))}</h3>{found}
          <textarea data-field="text" data-draft="clarify-{esc(cur["id"])}" rows="3" placeholder="In your own words" aria-label="Your answer"></textarea>
          <div class="btns"><button type="button" class="primary" data-send="answer" data-need-text>Send</button>{opts}<button type="button" data-send="park">Skip this one</button></div>''', cls="qcard clarify")
    else:
        now = '<p class="working"><span class="pulse"></span> Thinking about what to ask next.</p>'
    understood = ctx.ul(f.get("understood"))
    tell = req("frame", '''<details class="editbox"><summary>Rather just describe it? Tell Claude in your own words</summary>
      <textarea data-field="text" rows="4" placeholder="What you want, why now, who it is for, what done looks like. Any of it helps." aria-label="Describe what you want"></textarea>
      <div class="btns"><button type="button" data-send="tell" data-need-text>Send</button></div></details>''', anchor=False)
    enough = req("frame", '<div class="btns"><button type="button" data-send="enough">Enough questions, draft the Frame</button></div>', anchor=False)
    return f'''<p>Your prompt left a lot open, so instead of guessing, Claude will ask a few short questions, one at a time. The Frame is written from your answers.</p>
      {f'<div class="understood"><h3>What I understand so far</h3>{understood}</div>' if understood else ""}
      {f'<ol class="asked">{asked}</ol>' if asked else ""}
      {now}{tell}
      {enough if asked else ""}{ask_box("frame")}'''


def sec_frame(ctx, d):
    f = d.get("frame", {})
    if f.get("status") == "clarifying":
        return sec_clarify(ctx, d)
    if not f.get("problem"):
        return later("Claude is reading the code and drafting what it thinks you want.")
    approved = f.get("status") == "approved"
    lists = "".join(f"<h3>{t}</h3>{ctx.ul(f.get(k))}" for k, t in (("goals", "Goals"), ("nonGoals", "Not doing"),
                                                                    ("done", "What done looks like"), ("constraints", "Constraints")) if f.get(k))
    assumptions = []
    for a in f.get("assumptions", []):
        v = a.get("verdict")
        if v:
            state = "Right" if v == "right" else f"Wrong: {a.get('correction') or ''}"
            assumptions.append(f'<li class="assume {esc(v)}"><p>{ctx.inline(a["text"])}</p><p class="small human">{esc(state)}</p></li>')
        else:
            assumptions.append("<li>" + req(a["id"], f'''<p>{ctx.inline(a["text"])}</p>{f'<p class="small muted">Why I guessed: {ctx.inline(a["why"])}</p>' if a.get("why") else ""}
              <div class="btns"><button type="button" data-send="assume" data-verdict="right">Right</button>
              <button type="button" data-reveal>Wrong…</button></div>
              <div class="reveal" hidden><textarea data-field="text" rows="2" placeholder="What is actually true?" aria-label="Correction"></textarea>
              <div class="btns"><button type="button" data-send="assume" data-verdict="wrong">Send correction</button></div></div>''', cls="assume") + "</li>")
    gate = ('<p class="ok">Approved. Everything below builds on this.</p>' if approved else
            req("frame", '<div class="btns"><button type="button" class="primary" data-send="approve">This is what I want</button></div>', cls="gate"))
    return f'''<h3>The problem</h3>{ctx.md(f["problem"])}{f'<h3>Who has it</h3>{ctx.md(f["who"])}' if f.get("who") else ""}
      {lists}
      {f'<h3>What I assumed</h3><p class="small muted">Mark each one. A wrong guess here costs the most later.</p><ul class="assumptions">{"".join(assumptions)}</ul>' if assumptions else ""}
      {question_cards(ctx, d, "frame")}
      {gate}{"" if approved else edit_box("frame", "e.g. the real goal is X; drop goal 2; add a constraint")}{ask_box("frame")}'''


def sec_ground(ctx, d):
    g = d.get("ground", {})
    if g.get("status", "pending") == "pending":
        return later("Comes after the Frame. Claude is already researching it.")
    pieces = "".join(f'<tr><th>{esc(p.get("name"))}</th><td>{ctx.inline(p.get("what"))}</td><td>{ctx.inline("`" + p["ref"] + "`") if p.get("ref") else ""}</td></tr>' for p in g.get("pieces", []))
    gloss = "".join(f'<tr><th>{esc(x.get("term"))}</th><td>{ctx.inline(x.get("meaning"))}</td></tr>' for x in g.get("glossary", []))
    approved = g.get("status") == "approved"
    return f'''{ctx.md(g.get("summary"))}
      {f'<h3>The pieces</h3><div class="tablewrap"><table class="gloss"><tbody>{pieces}</tbody></table></div>' if pieces else ""}
      {f'<h3>How it flows</h3>{ctx.md(g["flow"])}' if g.get("flow") else ""}
      {f'<pre class="mermaid">{esc(g["diagram"])}</pre>' if g.get("diagram") else ""}
      {f'<h3>What must keep holding</h3>{ctx.ul(g.get("invariants"))}' if g.get("invariants") else ""}
      {f'<div class="callout"><h3>What surprised me</h3>{ctx.ul(g.get("surprises"))}</div>' if g.get("surprises") else ""}
      {f'<h3>Terms</h3><div class="tablewrap"><table class="gloss"><tbody>{gloss}</tbody></table></div>' if gloss else ""}
      {f'<h5>Where to look</h5>{ctx.refs(g.get("see"))}' if g.get("see") else ""}
      {question_cards(ctx, d, "ground")}
      {'<p class="ok">Confirmed.</p>' if approved else req("ground", '<div class="btns"><button type="button" class="primary" data-send="approve">I understand how it works today</button></div>', cls="gate")}
      {"" if approved else edit_box("ground", "e.g. you missed the retry path in the worker")}{ask_box("ground")}'''


def option_html(ctx, x, o, pickable):
    rec = o.get("id") == x.get("recommend")
    picked = o.get("id") == x.get("pick")
    radio = (f'<input type="radio" name="pick-{esc(x["id"])}" value="{esc(o["id"])}" data-field="pick" aria-label="Pick {esc(o.get("name"))}">' if pickable else "")
    return f'''<label class="opt{" rec" if rec else ""}{" picked" if picked else ""}">
      <span class="opthead">{radio}<strong>{esc(o.get("name"))}</strong>{'<span class="chip recchip">Claude recommends</span>' if rec else ""}{'<span class="chip okchip">Your pick</span>' if picked else ""}{f'<span class="chip">{esc(o["cost"])}</span>' if o.get("cost") else ""}</span>
      {ctx.md(o.get("summary"))}
      <div class="pc">{f'<div><h5>For</h5>{ctx.ul(o.get("pros"))}</div>' if o.get("pros") else ""}{f'<div><h5>Against</h5>{ctx.ul(o.get("cons"))}</div>' if o.get("cons") else ""}</div>
      {ctx.refs(o.get("evidence"))}</label>'''


def decision_card(ctx, d, x):
    st = x.get("status")
    head = f'<p class="eyebrow">{esc(x["id"])}{" · key decision" if x.get("key") else ""}</p><h3 class="dtitle">{esc(x.get("title"))}</h3>'
    if st in ("upcoming", "dropped"):
        deps = ", ".join(x.get("dependsOn", []))
        return f'<div class="dcard later" id="{esc(x["id"])}">{head}<p class="muted">{"Dropped." if st == "dropped" else ("Waits on " + deps + "." if deps else "Comes later.")} {ctx.inline(x.get("question"))}</p></div>'
    body = f'''<p class="dq">{ctx.inline(x.get("question"))}</p>{f'<h5>Why it matters</h5>{ctx.md(x["matters"])}' if x.get("matters") else ""}'''
    opts = "".join(option_html(ctx, x, o, st == "open") for o in x.get("options", []))
    rec = f'<div class="recwhy"><h5>Why Claude recommends {esc(next((o["name"] for o in x["options"] if o["id"] == x.get("recommend")), ""))}</h5>{ctx.md(x.get("recommendWhy"))}</div>' if x.get("recommend") else ""
    locks = f'<h5>What this locks in</h5>{ctx.md(x["locksIn"])}' if x.get("locksIn") else ""
    qs = question_cards(ctx, d, x["id"])
    if st == "open":
        need = "Required: this is a key decision, so the doc needs your reason." if x.get("key") else "Optional, but it is what you will say when someone asks."
        decide = req(x["id"], f'''<div class="opts">{opts}</div>{rec}{locks}
          <label class="lbl" for="why-{esc(x["id"])}">Why you picked it, in your own words</label>
          <p class="small muted">{need} Claude checks it against the evidence; it won't write it for you.</p>
          <textarea id="why-{esc(x["id"])}" data-field="text" data-draft="why-{esc(x["id"])}" rows="3" placeholder="We pick this because…"></textarea>
          <div class="btns"><button type="button" class="primary" data-send="decide"{" data-need-text" if x.get("key") else ""}>Decide</button>
          <button type="button" data-send="park">Not sure yet</button></div>''', cls="decide")
        return f'<div class="dcard open" id="{esc(x["id"])}">{head}{body}{qs}{decide}{edit_box(x["id"], "e.g. there is a third option: …; option b also costs …")}{ask_box(x["id"])}</div>'
    if st == "parked":
        return (f'<div class="dcard parked" id="{esc(x["id"])}">{head}<p><span class="chip">Parked</span> {ctx.inline(x.get("question"))}</p>'
                + req(x["id"], '<div class="btns"><button type="button" data-send="reopen">Pick this up again</button></div>') + "</div>")
    pick = next((o for o in x.get("options", []) if o.get("id") == x.get("pick")), {})
    gap = x.get("checkStatus") == "gap"
    check = f'<div class="check {"gap" if gap else "okc"}"><h5>{"Claude found a gap in the reason" if gap else "Claude checked the reason"}</h5>{ctx.md(x.get("check"))}</div>' if x.get("check") else ""
    return f'''<details class="dcard decided" id="{esc(x["id"])}"{" open" if gap else ""}><summary>{head}<p><span class="chip okchip">Decided</span> {esc(pick.get("name"))}{f' <span class="muted small">(reopened {x["reopened"]}×)</span>' if x.get("reopened") else ""}</p></summary>
      {body}<h5>Your reason</h5><blockquote class="human">{esc(x.get("rationale") or "No reason given.")}</blockquote>{check}
      <div class="opts">{opts}</div>{locks}
      {req(x["id"], REOPEN, anchor=False)}{ask_box(x["id"])}</details>'''


def sec_decide(ctx, d):
    st = d.get("decisionsStatus", "pending")
    if st == "pending":
        return later("Comes after How it works today. Claude is listing the decisions this work needs.")
    decs = d.get("decisions", [])
    rows = "".join(f'<tr><td><a href="#{esc(x["id"])}">{esc(x["id"])}</a></td><td>{esc(x.get("title"))}{" <span class=keyd>key</span>" if x.get("key") else ""}</td>'
                   f'<td class="muted">{esc(", ".join(x.get("dependsOn", [])) or "–")}</td><td><span class="dst {esc(x.get("status"))}">{esc(x.get("status"))}</span></td></tr>' for x in decs)
    table = f'<div class="tablewrap"><table class="dlist"><thead><tr><th></th><th>Decision</th><th>Waits on</th><th>State</th></tr></thead><tbody>{rows}</tbody></table></div>'
    if st == "proposed":
        intro = "<p>These are the decisions Claude thinks this work needs, in the order they depend on each other. Add, merge or drop any before we start.</p>"
        return intro + table + question_cards(ctx, d, "decisions") + req("decisions", '<div class="btns"><button type="button" class="primary" data-send="approve">Start with these</button></div>', cls="gate") + edit_box("decisions", "e.g. add a decision about rollout; D3 and D4 are the same") + ask_box("decisions")
    return table + "".join(decision_card(ctx, d, x) for x in decs) + question_cards(ctx, d, "decisions")


def sec_design(ctx, d):
    ds = d.get("design", {})
    if ds.get("status", "pending") == "pending":
        return later("Comes after the decisions. Each section follows from what you decided.")
    out = []
    for s in ds.get("sections", []):
        st = s.get("status")
        src = f'<p class="small muted">Follows from {", ".join(f"<a href=#{esc(i)}>{esc(i)}</a>" for i in s.get("from", []))}</p>' if s.get("from") else ""
        if st == "upcoming":
            out.append(f'<div class="dsec later" id="{esc(s["id"])}"><h3>{esc(s.get("title"))}</h3><p class="muted">Comes next.</p></div>')
        elif st == "open":
            out.append(f'''<div class="dsec open" id="{esc(s["id"])}"><h3>{esc(s.get("title"))}</h3>{src}{ctx.md(s.get("body"))}{question_cards(ctx, d, s["id"])}
              {req(s["id"], '<div class="btns"><button type="button" class="primary" data-send="approve">Looks right</button></div>', cls="gate")}{edit_box(s["id"])}{ask_box(s["id"])}</div>''')
        else:
            out.append(f'<details class="dsec done" id="{esc(s["id"])}"><summary><h3>{esc(s.get("title"))} <span class="chip okchip">Approved</span></h3></summary>{src}{ctx.md(s.get("body"))}{edit_box(s["id"])}{ask_box(s["id"])}</details>')
    return "".join(out)


def sec_challenge(ctx, d):
    st = d.get("challengeStatus", "pending")
    if st == "pending":
        return later("Comes after the design. Reviewers who took no part in the planning will read the doc cold and object.")
    if st == "running":
        return '<p class="working"><span class="pulse"></span> Reviewers are reading the doc cold. Their objections will appear here.</p>'
    names = " and ".join(d.get("challengers", [])) or "Independent reviewers"
    out = [f'<p>{esc(names)} read the doc without the conversation behind it. Answer each objection: rebut it in your words, accept it (Claude reopens what it touches), or park it as an open question.</p>']
    for o in sorted(d.get("objections", []), key=lambda o: ["high", "medium", "low"].index(o.get("severity", "low"))):
        r = o.get("response") or {}
        by = " and ".join({"claude": "Claude", "codex": "Codex"}.get(b, b) for b in o.get("by", []))
        head = f'''<header><span class="chip sev {esc(o.get("severity"))}">{esc(o.get("severity"))}</span> <span class="fid">{esc(o["id"])}</span>
          <h3>{esc(o.get("title"))}</h3><p class="small muted">Raised by {esc(by)}{f' · about <a href="#{esc(o["target"])}">{esc(o["target"])}</a>' if o.get("target") else ""}</p></header>'''
        body = f'{ctx.md(o.get("body"))}{ctx.refs(o.get("evidence"))}'
        if r.get("kind"):
            out.append(f'''<details class="obj sev-{esc(o.get("severity"))}" id="{esc(o["id"])}"><summary>{head}<p><span class="chip okchip">{RESPONSES.get(r["kind"], r["kind"])}</span></p></summary>{body}
              <h5>Your response</h5><blockquote class="human">{esc(r.get("text"))}</blockquote>{f'<h5>What came of it</h5>{ctx.md(o["outcome"])}' if o.get("outcome") else ""}</details>''')
        else:
            out.append(f'''<div class="obj open sev-{esc(o.get("severity"))}" id="{esc(o["id"])}">{head}{body}
              {req(o["id"], RESPOND)}{ask_box(o["id"], "Ask Claude for evidence")}</div>''')
    return "".join(out)


def sec_defend(ctx, d):
    if not d.get("defense"):
        return later("Comes after the challenge: the questions a skeptical tech lead would ask you.")
    out = ['<p>Answer these as you would in a design review, without asking Claude. Claude then grades each answer against the doc. A gap means the doc, or your understanding of it, is missing something.</p>']
    for x in d["defense"]:
        if x.get("answer"):
            g = x.get("grade")
            out.append(f'''<div class="dq-card" id="{esc(x["id"])}"><h4>{ctx.inline(x.get("q"))}</h4><blockquote class="human">{esc(x["answer"])}</blockquote>
              {f'<p><span class="chip grade {esc(g)}">{esc(GRADES.get(g, g))}</span></p>{ctx.md(x.get("note"))}' if g else '<p class="muted small">Claude is grading this.</p>'}</div>''')
        else:
            out.append(f'<div class="dq-card" id="{esc(x["id"])}"><h4>{ctx.inline(x.get("q"))}</h4>' + req(x["id"], f'''<textarea data-field="text" data-draft="def-{esc(x["id"])}" rows="3" placeholder="Your answer" aria-label="Your answer"></textarea>
              <div class="btns"><button type="button" class="primary" data-send="defend" data-need-text>Send answer</button></div>''') + "</div>")
    return "".join(out)


def sec_done(ctx, d, meta):
    b = blockers(d)
    outs = d.get("outputs") or {}
    if d.get("stage") == "done":
        return (f'<p class="ok">Signed off.</p>' + (f'<p>Design doc: <code>{esc(outs["doc"])}</code></p>' if outs.get("doc") else "")
                + (f'<p>Implementation plan: <code>{esc(outs["plan"])}</code></p>' if outs.get("plan") else ""))
    lst = "".join(f"<li>{esc(x)}</li>" for x in b)
    return (f'<p>When nothing is left below, Claude writes the design doc into the repo (after you confirm in Claude Code) and drafts the implementation plan from it.</p>'
            + (f'<h3>Still open</h3><ul>{lst}</ul>' if b else "<p class=ok>Nothing blocks sign-off.</p>")
            + req("doc", f'<div class="btns"><button type="button" class="primary" data-send="finalize"{" disabled" if b else ""}>Sign off and write the doc</button></div>'))


def build(meta, d):
    ctx = Ctx(meta)
    sections = {"frame": sec_frame(ctx, d), "ground": sec_ground(ctx, d), "decide": sec_decide(ctx, d), "design": sec_design(ctx, d),
                "challenge": sec_challenge(ctx, d), "defend": sec_defend(ctx, d), "done": sec_done(ctx, d, meta)}
    nav, main = [], []
    for i, (sid, title) in enumerate(STAGES, 1):
        state = stage_state(d, sid)
        nav.append(f'<li><a href="#{sid}" class="st-{state}"><span class="navn">{i}</span><span class="navt">{esc(title)}</span><span class="tick {state}" aria-hidden="true"></span></a></li>')
        if sid == "decide":
            for x in d.get("decisions", []):
                nav.append(f'<li class="sub"><a href="#{esc(x["id"])}"><span class="navt">{esc(x["id"])} · {esc(x.get("title"))}</span><span class="dst {esc(x.get("status"))}" aria-label="{esc(x.get("status"))}"></span></a></li>')
        main.append(f'<section class="sec st-{state}" id="{sid}"><h2><span class="snum">{i}</span> {esc(title)}</h2>{sections[sid]}</section>')
    log = d.get("log", [])
    if log:
        rows = "".join(f'<li><span class="muted small">{esc(e.get("at", "")[:16].replace("T", " "))}</span> <span class="by {esc(e.get("by"))}">{"You" if e.get("by") == "human" else "Claude"}</span> {ctx.inline(e.get("what"))}</li>' for e in reversed(log))
        main.append(f'<section class="sec" id="log"><details><summary><h2>How we got here <span class="muted small">({len(log)} entries)</span></h2></summary><ul class="log">{rows}</ul></details></section>')
        nav.append('<li><a href="#log"><span class="navn">·</span><span class="navt">How we got here</span></a></li>')
    working = (d.get("status") or {}).get("working")
    status = (f'<div class="statusbar" role="status"><span class="pulse" aria-hidden="true"></span><span><strong>Claude is working:</strong> {esc(working)}. The page updates in place.</span></div>' if working else "")
    decs = d.get("decisions", [])
    dn = sum(x.get("status") == "decided" for x in decs)
    branch = f' · <code>{esc(meta["branch"])}</code>' if meta.get("branch") else ""
    head_meta = (f'<span><code>{esc(meta.get("repo"))}</code>{branch}</span>'
                 f'<span>Started {esc((meta.get("created") or "")[:10])}</span>'
                 + (f'<span>{dn} of {len(decs)} decisions made</span>' if decs else ""))
    rendered = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data = {"key": f"{meta.get('repo')}:{d.get('slug')}", "renderedAt": rendered,
            "titles": {x["id"]: x.get("title") or x.get("q") or x.get("text", "")[:60] for x in
                       decs + d.get("design", {}).get("sections", []) + d.get("objections", []) + d.get("questions", []) + d.get("defense", []) + d.get("frame", {}).get("assumptions", [])},
            "waiting": waiting_list(d), "doc": to_md(d, meta)[:40000]}
    return {
        "TITLE": esc(f"{d.get('title') or d.get('slug')} design"),
        "DOC_TITLE": esc(d.get("title") or "Untitled design"),
        "SEED": esc(d.get("seed")),
        "HEAD_META": head_meta,
        "STAGEBAR": "".join(f'<span class="sb {stage_state(d, sid)}" title="{esc(t)}"></span>' for sid, t in STAGES),
        "STATUS": status,
        "NAV": "".join(nav),
        "MAIN": "".join(main),
        "MERMAID": '<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>' if d.get("ground", {}).get("diagram") else "",
        "DATA": json.dumps(data).replace("</", "<\\/"),
    }


def waiting_list(d):
    """What the human owes, with the id to jump to. Same rules as `new_run.py show`."""
    targets = []
    for q in d.get("questions", []):
        if q.get("status", "open") == "open":
            targets.append({"id": q["id"], "label": f"Answer: {q.get('q', '')}"})
    if d.get("frame", {}).get("status") == "clarifying":
        targets = targets[:1]  # one interview question at a time
    elif d.get("frame", {}).get("problem") and d["frame"].get("status") == "draft":
        targets.append({"id": "frame", "label": "Approve or correct the Frame"})
    if d.get("ground", {}).get("status") == "draft":
        targets.append({"id": "ground", "label": "Confirm how it works today"})
    if d.get("decisionsStatus") == "proposed":
        targets.append({"id": "decide", "label": "Approve the list of decisions"})
    for x in d.get("decisions", []):
        if x.get("status") == "open":
            targets.append({"id": x["id"], "label": f"Decide {x['id']}: {x.get('title', '')}"})
        elif x.get("status") == "decided" and x.get("checkStatus") == "gap":
            targets.append({"id": x["id"], "label": f"{x['id']}: look at the gap in your reason"})
    for s in d.get("design", {}).get("sections", []):
        if s.get("status") == "open":
            targets.append({"id": s["id"], "label": f"Review: {s.get('title', '')}"})
    for o in d.get("objections", []):
        if not (o.get("response") or {}).get("kind"):
            targets.append({"id": o["id"], "label": f"Respond to {o['id']}: {o.get('title', '')}"})
    for x in d.get("defense", []):
        if not x.get("answer"):
            targets.append({"id": x["id"], "label": f"Answer: {x.get('q', '')}"})
    return targets


# ---------------------------------------------------------------- markdown export

def to_md(d, meta):
    f, g = d.get("frame", {}), d.get("ground", {})
    L = [f"# {d.get('title') or d.get('slug')}", "",
         f"Status: {'signed off' if d.get('stage') == 'done' else 'in progress (' + d.get('stage', '') + ')'} · Repo: `{meta.get('repo')}` · Started {(meta.get('created') or '')[:10]}", ""]

    def lst(title, items):
        if items:
            L.extend([f"## {title}", ""] + [f"- {i}" for i in items] + [""])

    if f.get("problem"):
        L += ["## Problem", "", f["problem"], ""] + (["### Who has it", "", f["who"], ""] if f.get("who") else [])
    lst("Goals", f.get("goals"))
    lst("Non-goals", f.get("nonGoals"))
    lst("Success criteria", f.get("done"))
    lst("Constraints", f.get("constraints"))
    lst("Assumptions", [a["text"] + (f" (wrong: {a.get('correction')})" if a.get("verdict") == "wrong" else "") for a in f.get("assumptions", [])])
    if g.get("summary"):
        L += ["## How it works today", "", g["summary"], ""]
        if g.get("pieces"):
            L += [f"- **{p.get('name')}**: {p.get('what')}" + (f" (`{p['ref']}`)" if p.get("ref") else "") for p in g["pieces"]] + [""]
        if g.get("flow"):
            L += [g["flow"], ""]
        if g.get("diagram"):
            L += ["```mermaid", g["diagram"], "```", ""]
        lst("Invariants", g.get("invariants"))
    decs = [x for x in d.get("decisions", []) if x.get("status") != "dropped"]
    if decs:
        L += ["## Decisions", ""]
        for x in decs:
            pick = next((o for o in x.get("options", []) if o.get("id") == x.get("pick")), None)
            L += [f"### {x['id']}. {x.get('title')}", "", f"**Question:** {x.get('question', '')}", ""]
            if x.get("matters"):
                L += [x["matters"], ""]
            L += ["**Options considered:**", ""]
            for o in x.get("options", []):
                L.append(f"- **{o.get('name')}**{' (chosen)' if pick is o else ''}: {o.get('summary', '')}")
                L += [f"  - For: {p}" for p in o.get("pros", [])] + [f"  - Against: {c}" for c in o.get("cons", [])]
            L.append("")
            if x.get("status") == "decided" and pick:
                L += [f"**Decision:** {pick.get('name')}.", ""]
                if x.get("rationale"):
                    L += [f"**Why:** {x['rationale']}", ""]
                if x.get("locksIn"):
                    L += [f"**What this locks in:** {x['locksIn']}", ""]
            elif x.get("status") == "parked":
                L += ["**Decision:** open, parked.", ""]
            else:
                L += ["**Decision:** not made yet.", ""]
    for s in d.get("design", {}).get("sections", []):
        if s.get("status") != "upcoming" and s.get("body"):
            L += [f"## {s.get('title')}", "", s["body"], ""]
    objs = d.get("objections", [])
    if objs:
        L += ["## Review objections", ""]
        for o in objs:
            r = o.get("response") or {}
            L += [f"### {o['id']}. {o.get('title')} ({o.get('severity')})", "", o.get("body", ""), ""]
            if r.get("kind"):
                L += [f"**{RESPONSES.get(r['kind'], r['kind'])}:** {r.get('text', '')}", ""]
            if o.get("outcome"):
                L += [o["outcome"], ""]
    opens = [q.get("q") for q in d.get("questions", []) if q.get("status") == "parked"]
    opens += [f"{x['id']}: {x.get('question')}" for x in decs if x.get("status") == "parked"]
    opens += [f"{o['id']}: {o.get('title')}" for o in objs if (o.get("response") or {}).get("kind") == "park"]
    lst("Open questions", opens)
    if d.get("log"):
        L += ["## Decision log", ""] + [f"- {e.get('at', '')[:10]} ({'author' if e.get('by') == 'human' else 'Claude'}): {e.get('what')}" for e in d["log"]] + [""]
    return "\n".join(L).rstrip() + "\n"


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    run = a[0]
    meta = json.load(open(os.path.join(run, "meta.json"), encoding="utf-8"))
    d = json.load(open(os.path.join(run, "design.json"), encoding="utf-8"))
    errs = validate(d)
    if errs:
        print("design.json has problems:\n- " + "\n- ".join(errs), file=sys.stderr)
        sys.exit(1)
    if "--signoff" in a:
        b = blockers(d)
        print("\n".join(f"- {x}" for x in b) if b else "ready to sign off")
        sys.exit(1 if b else 0)
    if "--md" in a:
        out = a[a.index("--md") + 1]
        open(out, "w", encoding="utf-8").write(to_md(d, meta))
        print(out)
        return
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join(run, "design.html")
    vals = build(meta, d)
    page = re.sub(r"\{\{(\w+)\}\}", lambda m: vals.get(m.group(1), m.group(0)), open(TEMPLATE, encoding="utf-8").read())
    open(out, "w", encoding="utf-8").write(page)
    print(out)


if __name__ == "__main__":
    main()
