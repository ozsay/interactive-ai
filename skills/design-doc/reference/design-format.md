# design.json

Written by the session to `RUN/design.json`, validated and rendered by `scripts/render.py`, exported
to markdown by `render.py --md`. Text fields marked *md* accept paragraphs, `- ` lists, ``` fences,
`**bold**`, `[text](url)` and `` `code` ``. A code span that is exactly `path` or `path:line` and names
a real file in the repo becomes a link. How to write every field: `reference/writing.md`. How to
write questions and decision cards: `reference/questions.md`.

```jsonc
{
  "title": "Short name of the change",
  "slug": "kebab-case",
  "stage": "frame | ground | decide | design | challenge | defend | done",
  "seed": "The human's first prompt, verbatim.",
  "status": { "working": "What Claude is doing now, one line. Empty when idle." },

  "frame": {
    "status": "clarifying | draft | approved",   // clarifying: a vague prompt, interview first (SKILL step 1)
    "understood": ["While clarifying: what Claude has learned so far, one short line each, in the human's terms."],
    "problem": "md. The problem, in the human's terms. No solution yet.",
    "who": "md. Who has the problem and what it costs them.",
    "goals": ["One outcome per item."],
    "nonGoals": ["Things this work will deliberately not do."],
    "done": ["How we will know it worked: observable, checkable."],
    "constraints": ["Hard limits: compatibility, deadlines, team rules, budgets."],
    "assumptions": [
      // Claude guessed these; the human marks each right or wrong. At most 3, none while clarifying.
      { "id": "A1", "text": "The guess, one sentence.", "why": "What made Claude guess it.",
        "verdict": null, "correction": "" }      // verdict: null | "right" | "wrong"
    ]
  },

  "ground": {
    "status": "pending | draft | approved",
    "summary": "md. How the touched area works today, for someone who has never opened it.",
    "pieces": [{ "name": "Plain name", "what": "One line.", "ref": "src/queue/worker.ts" }],
    "flow": "md. How data or control moves through the pieces today.",
    "diagram": "optional mermaid source",
    "invariants": ["Things that hold today and must keep holding."],
    "surprises": ["md. What the research found that the Frame did not expect."],
    "glossary": [{ "term": "Lease", "meaning": "one line" }],
    "see": ["src/queue/worker.ts:40"]
  },

  "decisionsStatus": "pending | proposed | approved",   // proposed: the human approves the list first
  "decisions": [
    {
      "id": "D1", "title": "Short noun phrase",
      "question": "The decision as one question.",
      "matters": "md. Why this decision matters: what goes wrong if it is made badly.",
      "dependsOn": ["D0"],
      "key": true,                         // key decisions need the human's rationale to sign off
      "status": "upcoming | open | decided | parked | dropped",
      "options": [
        { "id": "a", "name": "Plain name", "summary": "md. What this option means in practice.",
          "pros": ["..."], "cons": ["..."], "evidence": ["src/x.ts:12"], "cost": "S | M | L" }
      ],
      "recommend": "a",
      "recommendWhy": "md. Claude's reason, two or three sentences.",
      "locksIn": "md. What becomes hard to change once this is picked.",
      "pick": null,                        // the option id the human chose
      "rationale": "",                     // the human's words, verbatim; never written by Claude
      "check": "md. Claude's check of the rationale against the evidence.",
      "checkStatus": "ok | gap",           // gap: the rationale misses or contradicts something
      "reopened": 0
    }
  ],

  "design": {
    "status": "pending | drafting | approved",
    "sections": [
      // status: upcoming | open | approved. Open one section at a time.
      { "id": "s1", "title": "Components and changes", "body": "md", "from": ["D1", "D2"], "status": "open" }
    ]
  },

  "challengeStatus": "pending | running | done",
  "challengers": ["Claude Opus 5.5", "Codex gpt-6-astra"],
  "objections": [
    {
      "id": "O1", "title": "...", "severity": "high | medium | low",
      "by": ["claude", "codex"],             // both = raised independently
      "target": "D2 | s3 | frame | ground",
      "body": "md. The objection, plainly, with the scenario it worries about.",
      "evidence": ["src/x.ts:40"],
      "response": { "kind": "rebut | accept | park", "text": "the human's words" },
      "outcome": "md. What changed because of it (accept), or why the rebuttal holds."
    }
  ],

  "defense": [
    // Questions a skeptical tech lead would ask. The human answers; Claude grades against the doc.
    { "id": "X1", "q": "Why not just extend the existing queue?", "answer": "",
      "grade": null, "note": "md" }          // grade: null | covered | partly | missing
  ],

  "questions": [
    // Questions Claude can't settle alone. Shown inside the section they affect.
    { "id": "Q1", "target": "frame | ground | D2 | s1",
      "q": "The question, one sentence.",
      "found": "md. What Claude already found in the code.",
      "why": "md. Why Claude can't decide this alone.",
      "options": ["Short answer the human can click"], "recommend": "the option Claude would pick",
      "changes": "md. What changes depending on the answer.",
      "status": "open | answered | parked", "answer": "" }
  ],

  "outputs": { "doc": "docs/design/<slug>.md", "plan": "RUN/plan.md" },
  "log": [{ "at": "ISO time", "by": "human | claude", "what": "D2 decided: option b, keep the lease table" }]
}
```

## Rules render.py enforces

- `frame.status` is clarifying, draft or approved. No assumptions while clarifying; at most 3 in a draft.
- Ids are unique across the doc. A question's or objection's `target` exists. `dependsOn` refers to decisions.
- A decided decision has a `pick` that is one of its options. A decision's `recommend` is one of its options.
- An open decision's dependencies are all decided. At most one decision and one design section are open at a time.
- `render.py --signoff` also checks that the doc is ready:
  - every decision is decided, parked or dropped;
  - every key decision has the human's rationale;
  - every objection has a response;
  - every defense question has an answer.

## Page ↔ session data

The page and the session share the artifact's database:

| Doc | Written by | Shape |
|---|---|---|
| `inputs/<target>` | page | `{kind, target, pick?, verdict?, response?, text, key, at}`: the last thing the human sent for that target |
| `asks/<key>` | page creates; session fills `a` | `{target, threadId, at, turns: [{q, a}]}` |

The page also keeps unsent text (a half-written rationale) in the browser only.

Requests reach the session as comments sent to Claude:

`[design-doc <kind> key=<key> target=<id> [pick=<option>] [verdict=right|wrong] [response=rebut|accept|park]] <the human's words>`

| kind | target | meaning |
|---|---|---|
| `approve` | `frame`, `ground`, `decisions`, `s<n>` | This part is right; move on. |
| `edit` | any | Change this part as the text says. |
| `assume` | `A<n>` | The assumption is right or wrong (`verdict`), with a correction. |
| `answer` | `Q<n>` | The answer to Claude's question. |
| `tell` | `frame` | While clarifying: the human describes what they want in their own words. |
| `enough` | `frame` | While clarifying: stop asking and draft the Frame from what you have. |
| `decide` | `D<n>` | `pick` plus the rationale in the text. |
| `park` | `D<n>`, `Q<n>`, `O<n>` | Not sure yet. |
| `reopen` | `D<n>` | Revisit a decided decision; the text says why. |
| `respond` | `O<n>` | `response` plus the human's words. |
| `defend` | `X<n>` | The human's answer. |
| `ask` | any | A question about this part. Answer it; change nothing. |
| `finalize` | `doc` | Sign off and write the outputs. |
