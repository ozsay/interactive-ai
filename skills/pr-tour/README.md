# pr-tour

A [Claude Code](https://claude.com/claude-code) skill that turns a GitHub pull request into an
interactive, guided review page, built for reviewing a PR in code you don't know well.

AI code review usually hands you a list of findings. That leaves three problems:

1. The findings point into code you have never read, so you can't judge them.
2. Without reading the diff you don't really know what the PR does; the description is never complete.
3. You end up asking a second agent whether the first one was right.

`pr-tour` builds the understanding first, then puts each finding where it belongs, with the
evidence and an independent verifier's verdict next to it.

## What the page contains

- **Overview and context:** what the PR does and why, how the touched code works *today*
  (read from the base branch), what changes, a glossary, and a few self-check questions.
- **Stack:** when the PR is part of a stack of dependent PRs, where it sits, a brief on every other
  PR, and warnings such as "the PR below was merged, retarget this one". The PR can be anywhere
  in the stack; the review stays on the one you asked for.
- **Description check:** claims in the PR description the code does or doesn't implement, and
  changes the description doesn't mention.
- **Chapters:** the diff grouped by intent, with a plain-language summary, notes on each change,
  and what to check. Code is collapsed until you open it. Chapters are sorted by the severity of
  the findings inside them.
- **Findings:** each one with its impact, how it breaks, evidence, a suggested fix, and the
  verifier's reasoning. Dismissed candidates stay visible, collapsed, so you can see what was ruled out.
- **Your review:** mark chapters as read, make a call on each finding (post it, ask the author,
  not an issue), write notes, and leave free-text instructions. Press **Draft my review** and the
  draft appears on the page; **Post this review** posts it after you confirm in Claude Code,
  always as a comment review, never an approval.

The page is published as soon as the context is written and fills in while the reviewers run.

## Talking to the session

The page is wired to the Claude Code session that built it. Its buttons don't copy text for you
to paste; they send a comment to that session, which wakes up and handles it:

- **Ask Claude** on any chapter or finding: the session answers with the whole repository at hand
  (the PR checkout, the code before the PR, the other PRs in a stack), so it can grep, read
  callers and check history. The answer appears under the chapter and in the comment thread.
- **Follow up** on an answer, or ask Claude to act on it ("add this as a question for the
  author", "re-check this against the PR above"): the session changes the tour and republishes it
  in place. Your notes and calls are kept.
- **Draft my review / Post this review:** the session turns your calls, notes and instructions
  into a GitHub review and shows the draft on the page.

Anything that leaves the page, such as posting the review, opening an issue or editing code, is
confirmed once in the Claude Code terminal. A click on a page can't authorize that on its own.

This needs Claude Code connected to claude.ai and the session still open. The page shows whether
it can reach the session. If it can't, say "reconnect the tour" in the session; meanwhile, Ask
gives a quick answer from the page alone, and your notes can be copied into the chat.

## Review levels

| Level | Reviewers | Verification |
|---|---|---|
| `fast` | Claude | none: findings are marked unverified |
| `regular` | Claude | Codex tries to disprove each finding |
| `deep` | Claude and Codex, independently | each verifies the other's findings; duplicates merged, disagreements shown as "disputed" with both arguments |

## Requirements

- [Claude Code](https://claude.com/claude-code).
- [`gh`](https://cli.github.com/) logged in, plus `git`, `jq`, `python3` and `bash`. macOS and Linux.
- For `regular` and `deep`: the [Codex CLI](https://github.com/openai/codex), logged in.
- Recommended: Claude Code connected to claude.ai, so the page is published as a private
  Artifact that talks to your session (see above). Without it the page is a local HTML file:
  notes stay in your browser (copy them into the chat and say "finalize the PR tour") and "Ask"
  copies the question for your Claude Code session.

## Install

This skill is part of [interactive-ai](../../README.md). As a Claude Code plugin, with both skills:

```
/plugin marketplace add ozsay/interactive-ai
/plugin install interactive-ai@interactive-ai
```

Or this skill alone:

```bash
git clone https://github.com/ozsay/interactive-ai ~/interactive-ai
ln -s ~/interactive-ai/skills/pr-tour ~/.claude/skills/pr-tour
```

## Use

In Claude Code:

```
/pr-tour 123
/pr-tour https://github.com/owner/repo/pull/123 --level deep
```

Options:

- `--level fast|regular|deep`: asked for when missing.
- `--repo owner/repo`: for a bare PR number outside that repo's checkout.
- `--run`: let verifiers write and run a temporary test in the PR checkout to reproduce a finding.
  Off by default, because it runs the PR's code. It never installs anything.
- `--no-findings`: only the guided tour, no review.

## Models

Each role's model and reasoning effort is set in [`models.json`](models.json):

| Role | Claude | Codex |
|---|---|---|
| reviewer | `opus`, medium | `gpt-6-astra`, medium |
| verifier | `sonnet`, medium | `gpt-6.1-sol`, medium |

Change the Codex models to ones your account offers. The page states which models produced its findings.

## Configuration

- `PR_TOUR_HOME`: where runs and repository caches live. Default `~/.cache/pr-tour`.
- `PR_TOUR_CODEX`: path to the `codex` binary, if it isn't on the `PATH` of the shell Claude Code uses.

## Privacy and safety

- The page embeds the PR's code. Published Artifacts are private to you by default; don't share a
  page for a private repository outside the people who can read that repository.
- Reviewers and verifiers read the code; they don't run it unless you pass `--run`. The Codex
  runs use a read-only sandbox with no MCP servers.
- Nothing is posted to GitHub until you approve the drafted review in the chat.

## How it works

```
SKILL.md              the workflow Claude follows
models.json           model and effort per role
scripts/prepare.sh    fetch the PR, its diff and discussion, check out its head, detect the stack
scripts/stack.py      find the PRs below and above in a stack
scripts/hunks.py      split the diff into addressable hunks
scripts/fill_prompt.py  fill reviewer and verifier prompts for a run
scripts/codex_run.py  one read-only Codex pass with a JSON schema
scripts/lint_prose.py flag hard-to-read text before rendering
scripts/render.py     validate the tour and render the page
scripts/review_draft.py  turn your calls and notes into a GitHub review
scripts/cleanup.sh    remove a run's checkout
prompts/              reviewer, verifier and stack instructions
reference/            the tour's data format and the writing rules
schemas/              output formats for findings and verdicts
assets/template.html  the page
```

`render.py` refuses a tour that leaves any part of the diff out, so nothing is silently skipped.

## License

[MIT](../../LICENSE)
