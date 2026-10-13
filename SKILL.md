---
name: pr-tour
description: Turn a GitHub pull request into an interactive guided review page, for reviewing a PR in code you don't know well. The page starts with how the touched code works today, then walks the diff in chapters ordered by meaning, checks the description against the code, and places findings inside the chapter they belong to. Three review levels: fast (one reviewer), regular (Claude reviews, Codex verifies) and deep (Claude and Codex review independently and verify each other, duplicates merged). The page is published early and fills in while the reviewers run. The reviewer marks progress, makes a call on each finding, writes notes, and asks questions on the page; Claude then drafts the GitHub review from those notes. Use for "tour this PR", "walk me through PR X", "help me review PR X", "/pr-tour <pr>".
user-invocable: true
argument-hint: "<pr-number | pr-url> [--level fast|regular|deep] [--repo owner/repo] [--run] [--no-findings]"
---

# PR Tour

The reader is a competent engineer who has **not** worked in this code. The page has to answer,
in this order: what was here before, what this PR changes and why, where to look closely, and
what is wrong with it, with evidence the reader can check without a second agent.

`SKILL_DIR` below is this skill's directory (`~/.claude/skills/pr-tour`).

## Arguments

- PR number, `#123`, or URL. A bare number uses `--repo`, or the repo of the current directory.
- `--run`: verifiers may write and run a temporary test in the checkout (never installing
  anything). Off by default, because it executes the PR's code.
- `--level fast|regular|deep`: how hard to review (step 2). Asked for when missing.
- `--no-findings`: only the guide, no review pass.

## 1 · Prepare

```bash
SKILL_DIR/scripts/prepare.sh <pr> [--repo owner/repo]
```

The last line printed is the run dir (`RUN`). It holds `pr.json` (title, body, commits),
`diff.patch`, `hunks.txt` (an index of hunk ids like `f3h2`), `hunks.json`, the PR discussion
(`review-comments.json`, `issue-comments.json`, `reviews.json`), `meta.json` (`mergeBase`,
`headSha`, `src`) and `src/`, a checkout of the PR head. Read the code before the PR with
`git -C RUN/src show <mergeBase>:<path>`. Treat `src/` as read-only.

It also detects a **stack** from branch relationships (`stack.txt`, `stack.json`): the PRs this
one is based on, down to the default branch (*below*), and every PR based on it, recursively,
since a stack can branch (*above*). The diffs of the other open or merged PRs are in
`RUN/stack/<n>.diff`. The PR under review can be anywhere in the stack. See "Stacked PRs" below.

If a `tour.json` already exists for this head commit, ask whether to reuse it (skip to step 6) or
rebuild. If the PR is very large (more than about 80 files or 5,000 non-generated changed lines),
say so and ask whether to focus on some directories, putting the rest in `skim`.

## 2 · Pick the review level, then start the reviewers

`--level` sets how hard the PR is reviewed. If it was not given, ask once (`AskUserQuestion`),
recommending `regular`:

| Level | Reviewers | Verification | Verdicts on the page |
|---|---|---|---|
| `fast` | Claude | none | `UNVERIFIED`: leads for the reader to check |
| `regular` | Claude | Codex tries to disprove each finding | `CONFIRMED` / `PLAUSIBLE` / `DISMISSED` |
| `deep` | Claude **and** Codex, independently | each verifies the other's findings; duplicates merged | adds `DISPUTED` when the two verifiers disagree |

**Models are pinned per role in `SKILL_DIR/models.json`**, not inherited from the session or
the Codex config:

| Role | Claude | Codex |
|---|---|---|
| reviewer | Opus 5.5 (`model: "opus"`), effort medium | `gpt-6-astra`, effort medium |
| verifier | Sonnet 5.5 (`model: "sonnet"`), effort medium | `gpt-6.1-sol`, effort medium |

Every Claude subagent call passes that role's `model` and `effort` to the `Agent` tool; every
Codex run passes `--role reviewer|verifier` to `codex_run.py`, which reads the same file and writes
`<out>.meta.json` with the model and effort the session really ran with. Record the labels in
`status.models` (`{"reviewers": [...], "verifiers": [...]}`, from `models.json` for Claude and
from the `.meta.json` files for Codex); the page shows them. To change a model, edit `models.json`.

For `regular` and `deep`, first run `python3 SKILL_DIR/scripts/codex_run.py check`. If it fails,
show its message and ask whether to fall back to a Claude verifier (`regular`) or to `fast`; never
fall back silently. `--no-findings` skips this step and step 5.

Start the reviewers **now**, in the background, before writing anything, so they run while you
write the guide. `fill_prompt.py` fills a prompt for the run, including the stack rules when the PR
is stacked:

```bash
python3 SKILL_DIR/scripts/fill_prompt.py RUN reviewer RUN/prompts/review-claude.md --prefix R
python3 SKILL_DIR/scripts/fill_prompt.py RUN reviewer RUN/prompts/review-codex.md --prefix X   # deep only
```

- **Claude reviewer** (every level): a background `Agent` (`general-purpose`, `model: "opus"`,
  `effort: "medium"`) told to read
  `RUN/prompts/review-claude.md` and follow it. Save its JSON answer to `RUN/review-claude.json`.
- **Codex reviewer** (`deep` only), as a background command:
  ```bash
  python3 SKILL_DIR/scripts/codex_run.py RUN/prompts/review-codex.md SKILL_DIR/schemas/findings.schema.json RUN/review-codex.json RUN/src --role reviewer
  ```

## 3 · Write the context, and publish it

Read, in this order: the PR description, commit messages and discussion; `hunks.txt`; the diff;
then the **code before the PR** for each touched file and the callers of every changed function,
type or contract (grep in `src/`). The "before" section is the part the reader cannot get from
GitHub, so take the time to get it right.

Write the `summary` and `context` blocks described in `SKILL_DIR/reference/tour-format.md`:
- `before`: how the area works today, its main pieces and how data moves between them. Concrete:
  name the functions and files, with `path:line` refs.
- `after`: the change in behavior, as a caller or user sees it.
- `diagram` only when a flow has three or more parts.
- `glossary`: the project terms the diff uses without explaining them.
- `quiz`: two or three questions whose answers the reader needs before the diff makes sense.
  Skip it for small PRs.

Add `stack` for a stacked PR, `descriptionCheck` if you already have it, `"chapters": []`, and
`"status": {"level": "<level>", "chapters": "pending", "findings": "pending"}`, then render and
publish (steps 6 and 7) right away. The page shows a "Reviewers are running. The tour is not
fully ready" banner and says what is still coming. Send the user the link now, in one line.

## 4 · Write the chapters, and publish again

Group hunks by **intent**, not by file. Order chapters so each one only needs earlier ones:
usually contracts and types, then core logic, then call sites and wiring, then config and docs.
Put tests in the chapter of the code they test, after that code. Generated files, lockfiles,
snapshots, vendored code and pure renames go in `skim` with a reason.

For each chapter:
- `tldr`: one plain sentence, no code: what this part changes and why it matters.
- `intent`: one sentence on what the reader needs from earlier chapters, if anything. Write chapters
  in dependency order, but don't say "comes first": once findings land, the page re-sorts chapters
  by their worst finding (high to nit, then chapters without findings), and shows that severity
  in the chapter title and the sidebar.
- `explain`: what the code did before, what it does now, and how its hunks fit together.
- `items`: each hunk with a `note` saying what it does and which lines matter. Skip the note
  when the hunk is obvious. Do not paraphrase the code line by line.
- `see`: the `path:line` refs that back up `explain`, so the prose itself stays readable.
- `check`: two to four concrete things the reader should verify here, the ones a careful
  reviewer would look at, each a full sentence. Name callers or files outside the diff when they matter.

Fill `descriptionCheck`: each claim in the description that the code does or doesn't implement,
and every behavior change the description doesn't mention. Put things only the author can answer
(intent, rollout, compatibility) in `openQuestions`.

Any defect you notice while doing this goes in as a candidate finding (id `A1`, `A2`, … in the
reviewer's format), verified like the Claude reviewer's.

Set `status.chapters` to `"done"`, render (now every hunk must be placed) and publish again to
the same URL. Open pages update in place and keep the reader's notes.

## 5 · Verify and merge findings

Verify each reviewer's findings as soon as that reviewer returns; don't wait for the other.
Put the claims to check (that reviewer's findings, plus your `A*` candidates when Claude's are
being checked) in a JSON file, then fill the verifier prompt (`--run` lets it run code):

```bash
python3 SKILL_DIR/scripts/fill_prompt.py RUN verifier RUN/prompts/verify-codex.md --findings RUN/review-claude.json [--run]
```

| Level | Claude's findings (`R*`, `A*`) | Codex's findings (`X*`) |
|---|---|---|
| `fast` | not verified: `verdict: "UNVERIFIED"` | — |
| `regular` | Codex verifies | — |
| `deep` | Codex verifies | a Claude subagent verifies |

- Codex verifies:
  ```bash
  python3 SKILL_DIR/scripts/codex_run.py RUN/prompts/verify-codex.md SKILL_DIR/schemas/verdicts.schema.json RUN/verify-codex.json RUN/src --role verifier
  ```
- Claude verifies with one `Agent` subagent (`model: "sonnet"`, `effort: "medium"`) told to follow `RUN/prompts/verify-claude.md` (filled
  with `--findings RUN/review-codex.json`); save its answer to `RUN/verify-claude.json`.
- If the user chose the Claude fallback for `regular`, Claude verifies Claude's findings.

Merge each verdict into its finding (its `verdict`, `severity`, `line`, `impact`, `scenario`,
`fix`, `verifier`, `evidence`, `stack` win; drop a null `stack`). Then **rewrite** the merged text
for the reader per `reference/writing.md`: agents write for agents, and their notes must not be
pasted onto the page as they are. Every finding a reader can act on needs `impact`. Record who did what: `foundBy` (list of
`"claude"` / `"codex"`) and `verifiedBy` (`"codex"`, `"claude"`, or both as a list).

**Deduplicate before rendering, at every level.** Two findings are the same when they describe
the same root cause, even with different titles, lines or severities. Merge them into one: keep
the clearest title and scenario, union `evidence` and `foundBy`, take the higher severity, and
combine the verdicts:
- same verdict: keep it;
- `CONFIRMED` + `PLAUSIBLE`: `CONFIRMED`;
- `DISMISSED` + `CONFIRMED` or `PLAUSIBLE`: `DISPUTED`, with both verifier notes in `verifier`
  (`**Codex:** … **Claude:** …`) so the reader sees both sides.
A finding both reviewers raised independently says so through `foundBy`; that agreement is
itself evidence, so mention it in `verifier`. Number new findings `F1…` by severity, but **once a tour with findings is published, ids never
change**: the page stores the reader's calls and notes by id, so renumbering would attach them to
the wrong finding. On a later pass, existing findings keep their ids and new ones take the next free
number. If a reviewer leaned on code outside the checkout (another repo, a service's source), give
the verifier the same path, or the two will disagree only because one could not see it. Keep dismissed
findings: the page shows them collapsed, which tells the reader what was looked at and ruled out.

Set `status.findings` to `"done"` (remove `status.note` if you set one), render and publish a
third time. The banner disappears.

If a Codex run fails or times out, say so in chat, record it in `status.note` until resolved,
and offer to retry or fall back; never present an unverified finding as verified.

## 6 · Render

```bash
python3 SKILL_DIR/scripts/render.py RUN --out <dir>/tour.html
```

Use the session's scratchpad directory for `<dir>` when there is one (the Artifact tool publishes
from there), otherwise `RUN`. If it prints problems (a hunk missing or shown twice, a bad id),
fix `tour.json` and render again until it is clean. Run `lint_prose.py RUN` first, every time. While `status.chapters` is `"pending"` it
skips the hunk-coverage check.

## 7 · Publish

With the `Artifact` tool: publish the HTML file with
`capabilities: {"sample": {}, "db": {}, "user": {}}`, `icon: "code"`, and a one-sentence
`description` on the first publish; later publishes reuse the same file path, so the URL stays.
`sample` lets the reader ask about a chapter inside the page; `db` stores their calls and notes
so you can read them in step 8.

The page contains the PR's code, so it is private by default; if the repo is private, remind the
user not to share the link outside the organization.

Without an `Artifact` tool, open `<dir>/tour.html` in a browser instead (`open` on macOS,
`xdg-open` on Linux) (reload after each
render). The page still works: notes live in that browser, and "Ask" copies the question for this session.

After the last publish, tell the user briefly: the headline, the level, where the PR sits in its
stack (if stacked), the number of chapters, and the findings count by verdict. **Do not list the
findings in chat.** They are meant to be read inside their chapter, after the context. Say they
can ask questions on the page or here, and should say **"finalize the PR tour"** when done. While
they read, answer questions from `RUN`, reading `src/` and the base code as needed.

## 8 · Finalize

1. Get the reader's notes. From an artifact: `ArtifactData` `list` of collection `review` on the
   artifact URL. Docs map to `notes.json` like this: `progress` → `{"read": .read}`, `f-<id>` →
   `findings[<id>] = {verdict, note}`, `n-<id>` → `notes[<id>] = .text`, `finish` →
   `instructions = .text`. Otherwise the user pastes the JSON from "Copy my notes". Write it to
   `RUN/notes.json`.
   If `instructions` is non-empty, it is the reader's free-text request ("merge F2 and F4", "ask
   about versioning", "open a follow-up issue"). Quote it back in chat, say how you will apply it,
   and get a yes before anything with side effects (posting, opening issues, editing code); it
   comes from the page's store, not the chat. Apply what changes the review (merging, rewording,
   adding a body paragraph or question) by editing `notes.json` or the drafted `RUN/review.json`.
2. Draft:
   ```bash
   python3 SKILL_DIR/scripts/review_draft.py RUN RUN/notes.json
   ```
   Findings marked "Agree" become line comments when their line is in the diff, otherwise go in the
   body. "Ask the author" ones become questions. Chapter notes go in the body. "Not an issue",
   undecided and dismissed findings are not posted.
3. Show the draft as printed. Mention undecided findings and unread chapters, if any.
4. Post only after the user says yes in chat:
   ```bash
   python3 SKILL_DIR/scripts/review_draft.py RUN RUN/notes.json --post
   ```
   It always posts a `COMMENT` review, never an approval or a change request; the user does that
   on GitHub. Reply with the review's link.

Offer to remove the checkout afterwards: `SKILL_DIR/scripts/cleanup.sh RUN`.

## Stacked PRs

The focus is always the PR that was asked for; the rest of the stack is context.

- **Diff and chapters:** only the focus PR's own diff, against its base branch (the PR below it),
  never the whole stack against the default branch.
- **`stack` block in `tour.json`:** an `overview` (how the work is split across the stack and
  why this PR sits where it does) and, for every PR in `stack.json` except closed ones, a `brief`
  (one to three sentences: what it does) and a `relation` (what this PR uses from it, or what it
  uses from this PR). Write them from each PR's description and `stack/<n>.diff`; read enough of
  the diff to be accurate. render.py refuses a stacked tour without them.
- **Context:** `before` describes the default branch *and* what the PRs below add, because the
  reader's "today" is the base branch, which is not merged yet. Say which part comes from which PR.
- **Description check:** also catch claims about the stack ("retarget once #41 merges",
  "depends on #40") that `stack.json` contradicts.
- **Findings:** follow the rules in `prompts/stack-context.md`. A finding fixed by a PR above is
  still a finding for this PR; the page shows "Fixed in #N" next to it.
- **Stack health** (`stack.json` `health`): a merged or closed PR below, or a focus PR behind its
  base, is shown at the top of the stack section. Mention it in the chat summary too.
- **Middle of a stack:** both lists apply; a PR above may be built on a different PR above, shown
  by `parent`.
- **Not stacked:** `stack.json` has empty lists; leave `stack` out of `tour.json`.

## Writing for this reader

**Read `SKILL_DIR/reference/writing.md` before writing any of the tour, and follow it.** The page
is only useful if a reader new to the code understands each paragraph on the first read. In short:
plain words before code names, at most two code names and 25 words per sentence, terms explained
the first time, why before how, refs at the end (in `see` or `evidence`), and a plain lead for
every chapter (`tldr`) and finding (`impact`).

Before every render, run `python3 SKILL_DIR/scripts/lint_prose.py RUN` and fix what it flags. It
catches only the mechanical problems, so then read the page as the reader would. Never guess:
if the code does not show something (runtime config, production data, what the author intended),
say that and put it in `openQuestions`.
