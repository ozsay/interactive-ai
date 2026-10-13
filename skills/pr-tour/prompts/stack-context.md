## The stack

This PR, #{{FOCUS}}, is one PR in a stack. **Review only #{{FOCUS}}'s diff** (`{{RUN}}/diff.patch`).
The other PRs are context; their diffs are in `{{RUN}}/stack/<number>.diff` and their
descriptions in `{{RUN}}/stack.json`.

{{STACK_LIST}}

"Below" PRs are already in this PR's base branch but not yet in `{{DEFAULT}}`: the code before
this PR (`{{MERGE_BASE}}`) includes them. "Above" PRs are built on this one and are not in the
checkout.

How the stack changes what counts:
- A defect that comes from a PR below belongs to that PR's review. Report it only if this PR
  relies on it or makes it worse, and mark it `"stack": {"pr": <n>, "kind": "from-below", "note": "..."}`.
- If a PR above already fixes or changes what you found, still report it, because the stack can
  merge one PR at a time. Mark it `"kind": "fixed-above"` or `"changed-above"`, and say in the note
  whether this PR is safe to merge without that one.
- If this PR changes something a PR above relies on (a function, type, file, config) and that PR
  does not adapt, report it with `"kind": "breaks-above"`.
- Check the "above" diffs for each finding before deciding.
