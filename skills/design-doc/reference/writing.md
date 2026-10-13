# Writing the doc

The reader is the human who owns this design: a capable engineer, reading between other work,
over several days. Each screen should make sense on the first read, without opening the code.

## Rules

1. **Plain words first, names second.** Say what a thing does, then name it: "the worker that
   retries failed uploads (`UploadRetrier`)".
2. **At most two code names per sentence, 25 words or fewer, one idea per sentence.** Paragraphs
   of four sentences or fewer.
3. **Explain a term the first time.** Project terms go in the glossary.
4. **Why before how.** What changes for users or operators first, then the mechanism.
5. **References at the end.** `path:line` refs go in `see`, `evidence`, or at the end of a sentence.
6. **Concrete over abstract.** "Two workers can pick the same job when the lease expires during a
   deploy" beats "there are concurrency concerns".
7. **Give scale.** "41 s at the slowest, 3 s typical" beats "slow".
8. **No padding, no hedging that changes nothing.** No "Note that", "It's worth noting".
9. **Never guess.** If the code doesn't show it, say so and make it a question or an assumption.
10. **Keep the human's words verbatim.** Rationales, answers and rebuttals are quoted as written.
    Fix nothing in them.

The Frame is in the human's terms, not the code's: `problem` has no code names at all.

Run `python3 SKILL_DIR/scripts/lint_prose.py RUN` before every render and fix what it flags. It
catches the mechanical half; read the result as the human would for the rest.
