# Verification pass

Goal: try to kill each surviving idea, then report what is left. Run every check below for every survivor. If you have a subagent tool, give the checks to a fresh agent that has not seen your reasoning, with only the idea and the claims, and have it search independently. A second reader who is not invested catches what you rationalized.

## 1. Claim audit

List every factual claim your case for the idea rests on: numbers, payouts, user counts, competitor facts, policy facts, "nobody does this". For each:

- Open the page. A search result or its summary is a lead, not a source; a claim you never opened cannot be `confirmed`.
- Prefer primary sources (the platform's docs, filings, announcements) over blogs and trend sites. Skip content-farm and SEO pages; if a number appears only there, it is `unverified`.
- Record the URL and the publication or update date.
- Re-find the number in a second, independent source. Two pages that both cite the same original are one source.
- Mark it `confirmed`, `single-source` or `unverified`. A claim you could not source is `unverified`, however plausible.
- Check for conflicts. If sources disagree, report the range and why, not the convenient one. When two official sources disagree, the newer dated one is the lead; say the conflict exists.

## 2. Freshness

Platform payouts, policies, APIs and algorithms change. Anything older than about 18 months, or from before a known major change, must be re-checked against a current source or marked stale. Check the platform's own changelog, announcements or docs for changes since.

## 3. The payer test

Name who pays, for what, and find proof one real instance exists: a listing, a price page, a public payout, a review that mentions paying. If you cannot find any payer, the idea is demand-shaped but not money-shaped. Report it that way or kill it.

## 4. Competitor search

Do this for every survivor, not a sample. Search the idea at least three different ways: what it does, who it is for, and the words users would type. Check the platform's own marketplace or app listing, Product Hunt, GitHub, and the first two pages of web results. For each competitor found, note price, size, last update and the top complaints. A crowded space with unhappy users is a better sign than an empty one. An empty space needs an explanation: either it is new, or nobody pays.

## 5. Platform risk

Read the current terms, developer policy or API rules for the exact part the idea depends on. Look for: banned uses, required approvals, rate limits, revenue share, the platform building this itself, and a history of cutting off third parties. Report the dependency and how bad losing it would be.

## 6. Reality check on the numbers

If you estimate revenue, show the arithmetic with sourced inputs (audience size times conversion times price). Use conservative, labeled assumptions. Do not present a market-size figure as the opportunity.

## 7. Verdict

Each idea ends as one of:

- **Survives:** payer found, claims confirmed or honestly labeled, risk named, nothing fatal.
- **Survives, weak:** promising but a key claim is single-source or unverified. Say which, and make confirming it the first step of the test.
- **Killed:** state the specific failing check.

Never promote an idea because it is exciting or because you already wrote it up. If most ideas die, say so and run another round of candidates from the lenses before settling for weak ones.

## Say what you could not check

Paywalled data, private Discords, platform dashboards and anything behind a login are usually out of reach. List them in the report as things the user can check, rather than guessing.
