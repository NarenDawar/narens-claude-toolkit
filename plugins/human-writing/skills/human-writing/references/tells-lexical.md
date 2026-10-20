# Vocabulary tells (as of 2026-10-19)

Use this last, and only as a backstop. Vocabulary is the best-measured layer and the most perishable one. Word habits shift with each model generation, and human writers adopt LLM-favoured words too. A banned word usually gets replaced by a near neighbour, so rewrite the sentence around a concrete fact instead of swapping the word.

Refresh this list when a new model ships: run lint.py on a few fresh outputs, look at what recurs, and update the dates.

## Measured (scientific abstracts only)

Kobak et al. (Science Advances, 2025) compared 15M+ PubMed abstracts from 2010 to 2024 and found excess-frequency ratios in 2024 of about 28.0 for "delves", 13.8 for "underscores" and 10.7 for "showcasing" (version 5 of the preprint; an earlier version gave 10.9 and 10.2 for the last two, so cite the version). About two thirds of the excess style words were verbs. Everything measured so far comes from scientific text. Transfer to blogs, email, marketing or fiction is not established.

Juzek and Ward (COLING 2025) identified 21 focal words and found results consistent with RLHF training playing a role. Their word list was not read for this skill.

## Community-observed (Wikipedia "Signs of AI writing", era judgments)

The page ties words to model generations. These are volunteer judgments, not measurements, and the newest entries need checking against the live page.

- Roughly 2023 to mid-2024: delve, tapestry, testament.
- Roughly mid-2024 to mid-2025: align with, fostering, highlighting.
- Roughly mid-2025 to mid-2026: emphasizing, showcasing.
- Later: leverage, multifaceted, prioritize.

"Delve" is said to have declined sharply from late 2024. No independent measurement of that decline was found.

## Blog-level, Claude-flavoured (anecdotal)

pivotal, robust, seamless, crucial, landscape, comprehensive, intricate, "worth noting", "it's important to note", "dive into", "navigate" (as in "navigate the complexities"). Treat these as hints only.

## What to do with a hit

1. Ask what the sentence should say. Say that.
2. If the word is doing real work ("robust" about a statistical method, say), keep it.
3. Do not mass-replace. A list of banned strings is how text ends up with odd synonyms and a different tic.
