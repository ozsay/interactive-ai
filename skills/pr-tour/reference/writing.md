# Writing the tour

The reader is a capable engineer who has never opened these files, reading between other work.
Each paragraph should make sense on the first read, without opening the code. If they have to
reread a sentence to parse it, the sentence is wrong.

## Rules

1. **Plain words first, names second.** Say what a thing does, then name it:
   "the function that turns a raw socket message into an event (`decode`)". A sentence that is
   mostly identifiers is unreadable to someone who doesn't know them yet.
2. **At most two code names per sentence.** Need more? Split the sentence or use a list.
3. **One idea per sentence, 25 words or fewer.** Paragraphs of four sentences or fewer.
4. **Explain a term the first time it appears.** Project terms go in the glossary. A language
   or tool feature (`satisfies`, discriminated union, JSON Schema `$ref`) gets a short gloss inline
   the first time ("a `satisfies` check, which makes the compiler fail if…"), or is left out.
5. **Why before how.** Start with what changes for the reader or the user, then how the code does it.
6. **References at the end, not in the middle.** Put `path:line` refs in a chapter's `see` list or
   a finding's `evidence`. In running text, at most one ref per paragraph, at the end of a sentence.
7. **Concrete over abstract.** "If the server returns a user without a profile,
   `user.profile.name` throws" beats "the type lies about the profile".
8. **No insider shorthand.** Don't write "drift", "on the wire", "frame", "residue", "the type
   lies" or "plumbing" unless the glossary explains it. Write what you mean.
9. **Hunk notes are one or two sentences:** what to notice and why it matters. Say where by
   pointing at the code ("the `if` at the top", "the new `catch`"), not only "lines 13-32".
10. **Findings start with impact.** `impact` is one plain sentence: who notices, and what they see.
    `scenario` is three short sentences: the situation, what happens, what should happen. No `->` arrows.
11. **Rewrite verifier output, don't paste it.** Two or three plain sentences with the deciding
    reason. Move its refs into `evidence`. When two verifiers are shown, give each one a sentence or two.
12. **No padding.** No "Note that", "It's worth noting", "Importantly". No hedging that changes nothing.
13. **Give scale.** "28 of the generated doc comments" says more than "many".

Then run `python3 SKILL_DIR/scripts/lint_prose.py RUN` and fix what it flags. It catches the
mechanical half of these rules (long sentences, too many code names, missing leads, arrows, refs
mid-sentence). It cannot judge whether the text is clear, so read the result as the reader would.

## Before and after

The examples are from a made-up PR that adds retries to an HTTP client.

**Chapter explain, before:**
> `client.ts` wraps `fetchJson` in `withRetry(fetchJson, { retries: opts.maxRetries ?? 3, backoff: expBackoff })`,
> and `RetryPolicy` is now part of `ClientOptions`, threaded through `createClient` to `Transport`.

**After:**
> Requests that fail with a network error or a 5xx are now retried, up to three times by default.
> The wait between attempts doubles each time. Callers can change the number of retries with a
> new `maxRetries` option on the client.

**Finding, before:**
> *scenario:* POST with idempotency unset -> 503 -> withRetry re-sends -> duplicate write server-side.

**After:**
> *impact:* A user who clicks "Pay" once can be charged twice when the payment service is briefly down.
>
> *scenario:* The client sends a payment request and the server answers 503. The client retries it,
> though nothing tells the server the second request is the same payment. Only safe-to-repeat
> requests (`GET`, or ones with an idempotency key) should be retried.

**Verifier note, before:**
> transport.ts:88 calls withRetry for all methods; no isIdempotent guard; api/payments.ts:14 lacks
> Idempotency-Key; confirmed.

**After:**
> Confirmed. Every request goes through the retry wrapper, whatever its method, and the payment
> call sends no idempotency key, so the server cannot tell a retry from a new payment.

## Shape of each section

- **Headline:** one sentence, plain words, no code. What the PR does for its users.
- **Why:** the problem, in two or three short paragraphs. Who had it and what it cost them.
- **Before / after:** a short paragraph or a list of three to five points each. Name at most the
  three or four pieces the reader will meet again in the chapters.
- **Chapter `tldr`:** one sentence, no code: what this part changes and why it matters.
- **Chapter `explain`:** the story of the change in plain words, then the names.
- **Chapter `check`:** questions a careful reviewer would ask, each a full sentence.
