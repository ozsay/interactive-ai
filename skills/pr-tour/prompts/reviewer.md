You are reviewing a pull request for defects. Another agent is writing the reader's guide; your
only job is to find real problems. A different agent will then try to disprove each one, so
report only what you can defend from the code.

## Inputs

- PR metadata, description and discussion: `{{RUN}}/pr.json`, `{{RUN}}/review-comments.json`, `{{RUN}}/issue-comments.json`
- The diff: `{{RUN}}/diff.patch` (hunk index: `{{RUN}}/hunks.txt`)
- The PR head checked out (read-only, do not edit): `{{SRC}}`
- The code before the PR: `git -C {{SRC}} show {{MERGE_BASE}}:<path>`
- Project review rules, if the repo has any: check `{{SRC}}` for `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `.github/` review docs, and apply them.
{{CONTEXT}}

## What counts

Look for, in this order: wrong behavior on a realistic input or state, broken contracts with
callers that are not in the diff (grep for them), security problems, data loss, races, missing
error handling on a path that does fail, tests that do not test what they claim, and claims in
the PR description the code does not implement.

Leave out style, naming, formatting and "consider adding" suggestions unless the project's own
rules require them. Do not repeat a point already raised in the PR discussion unless it is still
unaddressed at the head commit; if so, say so.

Every finding needs a concrete failure: the input or state, what the code does, and what it
should do. If you cannot write one, it is not a finding. Read the callers and the code before the
change; a guard elsewhere often makes a suspicion moot. At most 8 findings; an empty list is a
good outcome. Do not run any code from the PR. Verify by reading.

## Output

Reply with only a JSON object, no prose:

```json
{"findings": [{"id": "{{PREFIX}}1", "title": "short claim", "severity": "high|medium|low|nit",
  "file": "path/in/repo", "line": 123,
  "impact": "one plain sentence, no code: who notices and what they see",
  "summary": "one or two sentences: what is wrong",
  "scenario": "three short sentences: the situation, what the code does, what it should do",
  "evidence": [{"ref": "path:line", "note": "what this line shows"}],
  "fix": "the smallest change that fixes it",
  "stack": null}]}
```

A person who does not know this code will read these. Write `impact`, `summary`, `scenario` and
`fix` in plain sentences of 25 words or fewer, with at most two code names per sentence; put
`path:line` refs in `evidence`, not in the prose.

Number ids `{{PREFIX}}1`, `{{PREFIX}}2`, …. `line` is a line number in the PR head version of
`file` (null if none fits); prefer a line the PR added or changed. Severity: high = wrong results,
data loss or security in normal use; medium = breaks in a realistic edge case; low = minor or
unlikely; nit = harmless but worth a word. `stack` stays null unless the PR is stacked and a
stack rule above applies; then `{"pr": 123, "kind": "from-below|fixed-above|changed-above|breaks-above", "note": "..."}`.
