# deal-sparring-partner: a Claude Code skill by Naren

> Use when the user is about to negotiate a purchase, rent, vendor, contract or service deal (a car, an apartment lease, a contractor quote, a subscription renewal) and wants to prepare, rehearse or practise it, or have the other side played back to them (for example 'help me negotiate this', 'play the landlord', 'let me practise before I call the dealer').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

You have a deal coming up that is not a salary talk: a used car, a lease renewal, a contractor quote, a vendor contract. You say "help me prepare" or "play the other side".

## What it does

Claude builds a prep sheet from comparable prices it opened and dated, estimates the other side's opening, target and walkaway, and a small script fixes their concession ladder: offers move toward their walkaway in steadily shrinking steps and never past it. Then Claude plays the other side one message at a time, without coaching. At the end the script scores the result: the share of the bargaining zone you kept, and whether you took a deal worse than your own alternative or walked away from one that was available. The debrief quotes your own messages.

It does not coach during the scene, and it does not judge a negotiation by how big your concessions were.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install deal-sparring-partner@narens-claude-toolkit
```

**Manual**

Copy `plugins/deal-sparring-partner/skills/deal-sparring-partner` into `~/.claude/skills/`.

Needs Python 3.9 or newer. No other packages.

## Limits

- **The other side's numbers are estimates.** The score is only as good as the estimated walkaway, so it is reported as approximate. Real people also bluff, get emotional and change their mind, which a ladder does not.
- **Everything is converted to one number.** Non-price terms get a dollar value you agree on, and that choice drives the score.
- **Plain Claude is already a decent counterpart.** In one scripted test it conceded in plausible steps and gave useful feedback (do not call an offer final and then move it; trade, do not give). Where it went wrong was the scoring: it judged who won by comparing concession sizes and said the seller "got more of the range", when the user had paid $100 above the seller's hidden floor. Its seller also caved at the end: after counters of $14,000, $13,800 and $13,400 it accepted $12,900, a bigger last step than the two before. With the ladder, the seller held to shrinking steps and would not accept $12,900 in five turns, which is tougher and more consistent. The skill's gain is that scoring and a concession pattern fixed in advance. One scenario, one run each, scripted user messages; treat it as a single data point.
- Not legal advice. For leases, employment or other high-stakes contracts, have a professional read the paper.

## Example

**Before:** "Score 6.5/10. The seller got more of the range."

**After** (scoring that same $12,900 deal): "Deal at $12,900. Your walkaway was $13,500 and the seller's estimated floor $12,800, so you kept about 86% of the zone. You called $11,800 final and then moved, which taught the seller to discount every later limit."

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
