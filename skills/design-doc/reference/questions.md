# Asking the human

The human is the author of this design, not a reviewer of yours. Every question and every card is
a chance for them to think, so it must arrive with enough context to think with, and nothing more.

## Before asking anything

Ask only what the code, the docs and the history can't answer. Look first: grep, read callers,
`git log -S`, existing docs and tests. If you can answer it yourself, do, and state the answer as a
fact or an assumption the human can flip.

Things only the human can answer: intent and priorities, what the users or the business need, team
and org constraints, risk appetite, deadlines, what they have seen in production, and taste.

## A good question (`questions[]`)

- **Sits where it matters.** Its `target` is the section or decision it changes. Never a loose
  list of questions at the end.
- **Says what you found** (`found`), in one to three sentences, so the human doesn't have to go and look.
- **Says why you can't decide** (`why`). If you can't say, you probably can decide: do it, and make
  it an assumption.
- **Offers answers** (`options`) the human can click, short and distinct, plus a free answer.
  Mark the one you would pick (`recommend`).
- **Says what changes** (`changes`) with each answer, so the human knows what they are deciding.
- **One question per card.** No "and also…".
- **At most three open at a time.** More means you are handing the human your research. Park the
  rest in your notes and ask them when they become the next thing.

Bad: "Should we use a queue?"
Good: *found:* "Uploads today are processed inline in the request; the slowest one in the last
month took 41 s." *why:* "Whether 41 s is acceptable is a product call." *q:* "Is it OK for a large
upload to keep the user waiting up to a minute?" *options:* "Yes, for now" / "No, it must return
fast" *changes:* "No means we need a background job and a status screen: decision D2 below."

## A good decision card (`decisions[]`)

- **One decision.** If the options answer different questions, split the card.
- **`matters` first:** what goes wrong if this is decided badly, in one or two sentences.
- **Two or three real options.** Each one is something a competent engineer would argue for. A
  straw man is not an option. "Do nothing" counts when it is real.
- **For and against are concrete:** "a second writer to the `jobs` table", not "more complex".
  Put `path:line` evidence on the option it supports.
- **Recommend, and say why** in two or three sentences. The human may disagree; that is the point.
- **`locksIn`:** what becomes hard to change after this. It tells the human how careful to be.
- **About 200 words in all.** It should fit on one screen. Detail goes behind an Ask.
- **`key: true`** for the decisions the design stands on: the ones a reviewer will ask about. Key
  decisions need the human's rationale to sign off.

## Checking the human's rationale

After a decision, read the human's reason against the evidence. Write `check` in two or three
sentences:

- `ok` when the reason holds.
- `gap` when it misses a con of the chosen option, relies on something the code contradicts, or
  argues for a different option than the one picked. Name the gap plainly and ask whether it
  changes their mind. Don't rewrite the reason for them; they may answer in the next turn.

Never fill in `rationale` yourself, not even as a draft. A reason the human didn't write is not one
they can defend.
