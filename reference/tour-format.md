# tour.json

Written by the agent to `<rundir>/tour.json`, validated and rendered by `scripts/render.py`.
How to write every text field: `reference/writing.md`. Text fields marked *md* accept paragraphs, `- ` lists, ``` fences, `**bold**`, `[text](url)` and
`` `code` ``. A code span that is exactly `path:line` or `path:line-line` becomes a link to the PR
head on GitHub; prefix `base:` (`` `base:src/a.ts:40` ``) to link the code before the PR.

```jsonc
{
  "status": {                             // while reviewers run; the page shows a banner
    "level": "fast | regular | deep",
    "chapters": "pending | done",          // pending: chapters may be [] and coverage is not checked
    "findings": "pending | done",
    "note": "optional text shown in the Findings section while pending",
    "models": { "reviewers": ["Claude Opus 5.5", "Codex gpt-6-astra"], "verifiers": ["Codex gpt-6.1-sol"] }
  },
  "summary": {
    "headline": "One sentence: what this PR does, in the reader's terms.",
    "why": "md. The problem it solves and why now. From the description, linked issues, commits.",
    "risk": "low | medium | high",
    "riskReason": "One sentence: what could break and for whom."
  },
  "context": {
    "before": "md. How the touched area works TODAY, from the base code: the main pieces, how data flows, what invariants hold. Written for someone who has never opened these files.",
    "after": "md. What is different after the PR, as behavior: what callers, users or operators now see.",
    "diagram": "optional mermaid source (flowchart or sequenceDiagram) of the flow the PR touches",
    "glossary": [{ "term": "RetryPolicy", "meaning": "what it is, one line", "ref": "src/retry.ts:12" }],
    "quiz": [{ "q": "What happens today when the socket drops?", "a": "md answer" }]
  },
  "stack": {                              // only when stack.json lists other PRs
    "overview": "md. How the work is split across the stack and where this PR sits.",
    "prs": {
      "41": { "brief": "md. What #41 does, 1-3 sentences.", "relation": "md. What this PR uses from it, or what it uses from this PR." }
    }
  },
  "descriptionCheck": [
    // kind: matches | missing (claimed, not in code) | unmentioned (in code, not claimed) | contradicts
    { "kind": "unmentioned", "claim": "short statement", "detail": "md with `path:line`" }
  ],
  "chapters": [
    {
      "id": "c1",
      "title": "Short noun phrase",
      "tldr": "One plain sentence, no code: what this part changes and why it matters.",
      "intent": "One sentence: what the reader needs from earlier chapters, if anything. The page sorts chapters by their worst finding.",
      "explain": "md. Walk through the change: what the code did before, what it does now, how the hunks fit together.",
      "see": ["src/client.ts:33", { "ref": "src/socket.ts:61", "note": "where events are dispatched" }],
      "check": ["Concrete thing to verify while reading, e.g. 'every caller of X passes a timeout'"],
      "items": [
        { "ref": "f15h1", "note": "md. What this hunk does. Point at the lines that matter." },
        { "ref": "f8" }                      // a file id = all its hunks
      ]
    }
  ],
  "skim": [{ "ref": "f2", "reason": "Lockfile for the new dev dependencies" }],
  "findings": [
    {
      "id": "F1", "title": "...", "severity": "high | medium | low | nit",
      "verdict": "CONFIRMED | PLAUSIBLE | DISPUTED | UNVERIFIED | DISMISSED",
      "foundBy": ["claude", "codex"],          // who raised it; both = found independently
      "verifiedBy": "codex",                   // or "claude", or both as a list; absent at level fast
      "chapter": "c2",                       // optional; inferred from file/line when omitted
      "file": "src/client.ts", "line": 88,   // PR head line number
      "impact": "One plain sentence, no code: who notices and what they see.",
      "summary": "md", "scenario": "md", "fix": "md",
      "evidence": [{ "ref": "src/client.ts:88", "note": "..." }],
      "verifier": "md. What the verifier checked and why it decided so.",
      "repro": { "status": "failed-as-predicted | passed | not-run", "command": "...", "output": "..." },
      "stack": { "pr": 43, "kind": "from-below | fixed-above | changed-above | breaks-above", "note": "md" }  // optional
    }
  ],
  "openQuestions": ["Things only the author can answer (intent, rollout, compatibility)."]
}
```

## Rules render.py enforces

- Every hunk id in `hunks.txt` appears exactly once, in a chapter's `items` or in `skim`. A file
  id covers all its hunks. Files with no textual hunks (binary, pure rename) need their file id.
- Chapter ids and finding ids are unique; a finding's `chapter` must exist.
- Every finding has `title`, `summary`, `scenario`, a valid `severity` and `verdict`.
- A stacked PR needs `stack.overview` and a `brief` for every non-closed PR in `stack.json`; a
  finding's `stack.pr` must be in the stack.
- `#123` in any md text links to that PR.

Hunks longer than 400 lines are cut off in the page with a link to GitHub, so a generated file
belongs in `skim` unless its content is the point.

## Page ↔ session data

The page and this session share the artifact's database:

| Doc | Written by | Shape |
|---|---|---|
| `review/progress` | page | `{read: {chapterId: bool}}` |
| `review/f-<id>` | page | `{verdict: "agree" \| "ask" \| "reject" \| null, note}` |
| `review/n-<chapterId>` | page | `{text}` |
| `review/finish` | page | `{text}`: the reader's free-text instructions |
| `asks/<key>` | page creates; session fills `a` | `{kind: "ask" \| "act", target, threadId, at, turns: [{q, a}]}` |
| `review/draft` | session | `review_draft.py --json` output: `{body, comments: [{path, line, body}], undecided, unread, at}` |
| `review/posted` | session | `{url, at}` |

Requests reach the session as comments sent to Claude, tagged
`[pr-tour ask|act|finalize|post key=… target=…]`.

