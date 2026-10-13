You are researching a codebase for a design doc that a human is writing with Claude. Read code;
change nothing. Write your notes to `{{OUT}}` as plain markdown.

## The work being planned

{{FRAME}}

## Your task: {{TASK}}

## How to write the notes

- Facts from the code, each with a `path:line` reference. Separate what you read from what you infer.
- Name the pieces the work touches, how data or control flows through them today, and what must
  keep holding (invariants, contracts with other code, compatibility).
- List surprises: anything that contradicts the description of the work above, or makes it bigger
  or smaller than it looks.
- List the decisions you think the work needs, each with two or three real options and the evidence
  for and against each one. Don't pick for the human; say which you would pick and why.
- List what you could not find out from the code. Those become questions for the human.
- Be brief. The session that reads this turns it into one screen at a time.
