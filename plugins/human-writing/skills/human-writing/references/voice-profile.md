# Writing to a person's voice

Contents: why samples, what to ask for, what to extract, how to write to the profile, and how to check.

Giving a model two to five real samples of the person's writing is the best-supported way to get closer to their voice (a study across 400+ authors found few-shot samples clearly beat none, with small gains from going past a handful). Two limits to remember: samples chosen by matching topic did worse than samples chosen by matching genre, and casual blog or forum writing was the hardest style to imitate. Even good imitation can still read as machine-made in aggregate statistics, so treat the sample as a way to sound like the person, not as proof of anything.

## What to ask for

Two or three passages, 150 to 400 words each, that the user wrote and likes, in the same genre as the new piece. An email sample for an email, a post for a post. Ask for finished writing, not notes. If the user has none, offer to work from the principles in SKILL.md and say that it will sound less like them.

## What to extract

Read the samples and note, in a few lines:

- Sentence length: typical, shortest, longest, and how often a very short sentence follows a long one.
- Person and address: I and you, or we, or neither.
- Contractions: always, sometimes, never.
- Punctuation habits: dashes, semicolons, parentheses, exclamation marks, ellipses.
- Openings and endings: how paragraphs and the whole piece usually start and stop.
- Hedging and certainty: how often they commit, and how they voice doubt.
- Vocabulary: plain or technical, any favourite words or running jokes.
- Things they never do: no bullets, no questions, no jokes.

For numbers, run the lint script on the sample file; it prints sentence length, dash rate and others, which you can compare to the draft with --sample.

## Writing to the profile

Draft in that voice, copying the habits above, not the sample's topics or phrases. Do not reuse sentences from the sample. If the samples clash with the principles in SKILL.md (for example the user hedges a lot), keep the user's habit in genres where it fits and mention it only if it works against their goal.

## Checking

Run lint.py on the draft with --sample. Compare the sentence-length spread, dash use and contraction rate against the sample. Large gaps are worth a look. Matching the person's own numbers matters more than any fixed target.
