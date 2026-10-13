Another reviewer claims the pull request below has these defects. Your job is to try to prove
each claim wrong. You did not write them and get no credit for agreeing. A claim survives only
if you trace the failure in the code yourself.

## The claims

```json
{{FINDINGS}}
```

## Inputs

- The diff: `{{RUN}}/diff.patch`
- The PR head checked out: `{{SRC}}` (read-only unless reproduction is allowed below)
- The code before the PR: `git -C {{SRC}} show {{MERGE_BASE}}:<path>`
- PR description and discussion: `{{RUN}}/pr.json`, `{{RUN}}/review-comments.json`
{{STACK}}

## How to check each claim

1. Read the cited lines and the code around them at the PR head.
2. Follow the scenario through the real call path: who calls this, with what values, and is
   there a guard, a type, a validation, a default or a test that prevents it?
3. Check whether it is new in this PR or already true before it (`{{MERGE_BASE}}`). A defect
   that exists before the PR and is not made worse is out of scope: dismiss it and say so.
4. Check whether the PR discussion already settles it.
5. Weigh whether it is a real defect or a hardening suggestion below the bar.
6. {{REPRO}}

## Verdict

- `CONFIRMED`: you traced the scenario to the wrong result through actual code, and nothing prevents it.
- `PLAUSIBLE`: the code allows it, but whether it happens depends on something the code cannot
  show (runtime config, external service behavior, data in production).
- `DISMISSED`: something prevents it, it predates the PR, the scenario is unrealistic, or it is a
  matter of taste. Name the line that prevents it.

Correct the severity, the line, the scenario or the fix if the reviewer got them wrong.

Reply with only a JSON object, no prose, with exactly one verdict per claim:

```json
{"verdicts": [{"id": "the claim's id", "verdict": "CONFIRMED|PLAUSIBLE|DISMISSED",
  "severity": "high|medium|low|nit", "line": 123,
  "impact": "one plain sentence, no code: who notices and what they see",
  "scenario": "corrected or confirmed scenario", "fix": "corrected or confirmed fix",
  "verifier": "2-3 plain sentences: your verdict and the deciding reason. No refs here; put them in evidence",
  "evidence": [{"ref": "path:line", "note": "..."}],
  "stack": null}]}
```

A person who does not know this code will read your text. Keep sentences to 25 words or fewer,
with at most two code names each.

`stack` stays null unless the PR is stacked and a stack rule applies; correct or clear the reviewer's.
