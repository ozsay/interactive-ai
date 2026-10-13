# design-doc

A [Claude Code](https://claude.com/claude-code) skill for planning a change *with* Claude, one
decision at a time, until you have a design doc you can defend.

Agent plan mode usually works like this: you write a prompt, the agent researches, and a long plan
appears. Three things go wrong:

1. The prompt never captures the whole intent, so the plan goes through many rewrites.
2. The agent's questions arrive without context: "sync or async?" with no picture of what that touches.
3. The plan is too long to read carefully at once, so it gets accepted mostly unread.

Underneath all three: you can't defend the plan. It feels like the agent planned it and knows what
it's doing. `design-doc` brings back the way design docs used to be written, over time and with
real thinking. Claude reads the code, drafts the options and finds the evidence. You make every
call, in your own words.

## The flow

| Stage | Claude | You |
|---|---|---|
| **1 · Frame** | Writes what it thinks you want: problem, goals, non-goals, success criteria, constraints, and the assumptions it had to make. | Mark each assumption right or wrong, correct the rest, approve. |
| **2 · How it works today** | Explains the code the work touches, for someone who has never opened it, plus what surprised it. | Confirm you understand it, or ask. |
| **3 · Decisions** | Lists the decisions the work needs, then brings **one card at a time**: why it matters, two or three real options with evidence, a recommendation, and what it locks in. | Pick, and write *why* in your own words. Claude checks your reason against the code and tells you if it has a gap. |
| **4 · Design** | Writes the sections that follow from your decisions, one at a time. | Approve or correct each one. |
| **5 · Challenge** | Independent reviewers (Claude and Codex) who never saw the conversation read the doc cold and object. | Rebut each objection, accept it (the plan changes), or park it as an open question. |
| **6 · Defend** | Asks the four or five questions a skeptical tech lead would ask. | Answer without help. Claude grades each answer against the doc. |
| **Sign off** | Writes the design doc into the repo (after you confirm), and an implementation plan from it. | |

Rules that keep it moving:

- **One thing at a time.** You never see a stage before the one before it is approved.
- **Small screens.** A decision card is about 200 words.
- **Questions sit where they matter.** Each says what Claude already found, why it can't decide
  alone, and what changes with your answer. Questions the code can answer aren't asked.
- **You never wait.** While you read one stage, background agents research the next.
- **It keeps its history.** Every call goes into a decision log, and decisions can be reopened.
- **It takes days if you want.** Everything persists; say "resume the design doc" in a new session.

The doc you end with has the sections reviewers expect: problem, goals, how it works today,
decisions with alternatives considered and *your* reasons, design, review objections and responses,
open questions, and a decision log.

## Talking to the session

The page is wired to the Claude Code session that runs the plan. Its buttons don't copy text;
they send a comment that wakes the session, which updates the doc and republishes the page in
place. **Ask Claude** on any part answers with the whole repository at hand. Anything that leaves
the page, such as writing the doc into the repo, is confirmed once in the terminal.

This needs Claude Code connected to claude.ai, with the session open. Without it, buttons copy a
message to paste into the session, and you can always answer in the chat instead.

## Install

This skill is part of [interactive-ai](../../README.md). As a Claude Code plugin, with both skills:

```
/plugin marketplace add ozsay/interactive-ai
/plugin install interactive-ai@interactive-ai
```

Or this skill alone:

```bash
git clone https://github.com/ozsay/interactive-ai ~/interactive-ai
ln -s ~/interactive-ai/skills/design-doc ~/.claude/skills/design-doc
```

## Use

```
/design-doc let users schedule exports to S3 every night
/design-doc resume
```

## Requirements

- [Claude Code](https://claude.com/claude-code), `git` and `python3`. macOS and Linux.
- Recommended: Claude Code connected to claude.ai, so the page is a private Artifact that talks
  to your session.
- Optional: the [Codex CLI](https://github.com/openai/codex), logged in, for a second, independent
  challenger. Without it, the challenge runs with Claude only.

## Models

Set in [`models.json`](models.json): the researcher is `sonnet` at medium effort; the challengers
are `opus` and `gpt-6-astra`, both at medium. Change the Codex model to one your account offers.

## Configuration

- `DESIGN_DOC_HOME`: where runs live. Default `~/.cache/design-doc`.
- `DESIGN_DOC_CODEX`: path to the `codex` binary, if it isn't on the `PATH` of the shell Claude Code uses.

## Privacy and safety

- The page quotes the code it talks about. Published Artifacts are private by default; don't share
  a page about a private repository outside the people who can read that repository.
- Nothing in the repository changes until you sign off and confirm in the chat. Challengers read
  the code in a read-only sandbox.

## How it works

```
SKILL.md                  the workflow Claude follows
models.json               model and effort per role
scripts/new_run.py        create, list and show runs (where it stands, what waits on you)
scripts/render.py         validate design.json, render the page, export markdown, check sign-off
scripts/lint_prose.py     flag hard-to-read text and oversized cards
scripts/fill_prompt.py    fill a prompt template
scripts/codex_run.py      one read-only Codex pass with a JSON schema
prompts/                  researcher and challenger instructions
reference/                the doc's data format, how to ask questions, how to write
schemas/                  the challengers' output format
assets/template.html      the page
```

## License

[MIT](../../LICENSE)
