# interactive-ai

[Claude Code](https://claude.com/claude-code) skills that keep the human engaged in agent work.

An agent that reviews or plans on its own hands you a result to accept. You end up trusting it
because checking it is hard, not because you understand it. These skills turn the work into a
live page wired to your Claude Code session. You build the understanding step by step, make the
calls, and finish with something you can explain and defend.

| Skill | What it does |
|---|---|
| [**pr-tour**](skills/pr-tour) | Turns a pull request into a guided review: how the code works today, the diff in chapters, findings checked by an independent verifier. You make the call on each finding and post the review. |
| [**design-doc**](skills/design-doc) | Plans a change with you one decision at a time. You correct the framing, decide each card in your own words, answer an independent challenge, and end with a design doc you can defend. |

Both use the same pattern. The page is a private claude.ai Artifact; its buttons and questions go
straight to the session that built it, which answers with the whole repository at hand and
updates the page in place. Anything that leaves the page (posting a review, writing into the repo)
is confirmed once in the terminal.

## Install

As a Claude Code plugin, with both skills:

```
/plugin marketplace add ozsay/interactive-ai
/plugin install interactive-ai@interactive-ai
```

Or clone and link the skills you want:

```bash
git clone https://github.com/ozsay/interactive-ai ~/interactive-ai
ln -s ~/interactive-ai/skills/pr-tour ~/.claude/skills/pr-tour
ln -s ~/interactive-ai/skills/design-doc ~/.claude/skills/design-doc
```

## Requirements

Claude Code, `git` and `python3`, on macOS or Linux. pr-tour also needs `gh`, `jq` and `bash`. The
[Codex CLI](https://github.com/openai/codex) is needed for pr-tour's `regular` and `deep` levels and
optional for design-doc. Each skill's README has the details.

## License

[MIT](LICENSE)
