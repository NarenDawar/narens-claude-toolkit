# Structural tells, ranked

Contents: how to use this list, the patterns (1-12), and what is not evidence.

Structure outlasts vocabulary. Word habits change with every model release, while these moves persist, which is why they come first. The patterns come mostly from Wikipedia's volunteer guide "Signs of AI writing" (community-observed, not measured) plus measured grammar studies for items 5 and 6. One sighting of a minor pattern is not worth an edit. Act on the strong ones alone, and on weaker ones when several cluster in a paragraph.

Every pattern below has a fix. The fix is always to say the concrete thing, never just to delete or reword.

## Strong

1. **Vague attribution and significance inflation.** "Experts say", "Many believe", "stands as a testament to", "plays a pivotal role in the broader landscape of".
   Fix: name the source, the number or the event. If you cannot, cut the sentence.
   Before: "The festival has become a testament to the region's vibrant cultural heritage."
   After: "About 40,000 people came last year, and the town doubles its hotel prices that week."

2. **Negative parallelism.** "It's not just X, it's Y." "This isn't about A. It's about B." Also the split form across two sentences, and the reversed form ("not X, but Y").
   Fix: state Y. Keep the contrast only if a real person held position X and you are answering them.
   Before: "It's not just a tool, it's a whole new way of working."
   After: "It cut our review time from two days to three hours."

3. **Tacked-on participial analysis.** A sentence that ends in a comma and an -ing phrase supplying significance: ", highlighting the importance of...", ", underscoring...", ", reflecting a broader trend".
   Fix: delete the clause, or turn it into its own sentence with a fact.
   Before: "Sales rose 12%, reflecting growing demand for sustainable products."
   After: "Sales rose 12%. The refill packs drove most of it."

4. **Closers and summaries.** A last line that restates the point, offers a moral, or looks forward ("Ultimately...", "In the end...", "The future looks bright"). The "Despite its X, Y faces challenges" ending belongs here too.
   Fix: end on the last useful fact or on the action the reader should take.

## Medium

5. **Zombie nouns and copula avoidance.** "Serves as", "functions as", "boasts", "features" where "is" or "has" works; nominalizations ("the implementation of the removal of").
   Fix: use the plain verb. Measured: instruction-tuned models use nominalizations at roughly 1.5 to 2 times the human rate (Reinhart et al., PNAS 2025, via secondary summaries).

6. **Participial openers and stacked -ing clauses.** Models use present participial clauses at roughly 2 to 5 times the human rate (same source). Fix: make the clause a main verb.

7. **Forced triplets.** Three adjectives, three parallel verbs, three examples, every time. No measured source; community-observed.
   Fix: use the number of items that exist. Often one good example is enough.

8. **Uniform rhythm.** Every sentence about the same length, every paragraph about the same size, each starting with a topic sentence. The lint script reports sentence-length spread so you can compare it to the writer's own.
   Fix: vary by content, not by formula. Merge two thin sentences; let a long one run when the idea needs room.

9. **Template structure.** Headline-bold-then-explanation bullets, title-case headings, a summary section that repeats the body, symmetrical sections of equal length.
   Fix: write paragraphs. Use a list only when items are parallel and independent.

## Residue

10. **Assistant residue.** "Certainly!", "Great question!", "I hope this helps", "Let me know if you'd like...", "Here is a revised version", "As an AI". Also "You're absolutely right!" (Claude Code users reported it widely; see claude-habits.md).
    Fix: delete. Start with the content.

11. **Hedging stacks.** "It's worth noting that it can sometimes potentially...". Fix: one hedge, placed where the doubt actually is, with the reason.

12. **Promotional tone in neutral text.** "Nestled in", "rich tapestry", "vibrant", "boasts". Fix: describe what is there.

## Not evidence on their own

Perfect grammar, formal register, a single "Additionally" or "Moreover", curly quotes, a single em dash, "not just X but Y" in a human listicle. Humans do all of these, and human em dash use has risen. Individual expert readers still produced false positives up to 12% in one study (Russell et al., ACL 2025). A tell is weak evidence alone, stronger in combination, and never proof. When editing someone's own writing, a pattern they use consistently is part of their voice.
