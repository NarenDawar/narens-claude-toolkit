# trip-expense-settler: a Claude Code skill by Naren

> Use when the user has a group's shared expenses (a chat log, notes, receipts, a messy list of who paid for what) from a trip, a house or an event and wants to know who owes whom and how to settle up with the fewest payments.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

You have a group chat or a list of "I paid for dinner, it was for three of us" lines and want to know who pays whom.

## What it does

Claude reads the notes and writes a ledger: who paid, how much, in what currency, and who shared it (equally, by weights, or by exact amounts). It lists every line it had to interpret, such as "I covered Ben's ticket", a refund to one person's card, or an uneven split described in words, and asks about any that could move a balance. A script then does the money in whole cents: one rounding per entry, shares that add to the total exactly, balances that sum to zero, and the fewest possible payments (it splits people into the most groups that each net to zero, which is the minimum). The report shows each person's paid, share and net, the payments, and each expense's split so any line can be audited.

It runs locally, uses no app and needs no account.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install trip-expense-settler@narens-claude-toolkit
```

**Manual**

Copy `plugins/trip-expense-settler/skills/trip-expense-settler` into `~/.claude/skills/`.

Needs Python 3.9 or newer. No other packages.

## Limits

- **No measured accuracy gain over plain Claude.** This skill was rated weak before it was built, because free apps (Splitwise, Tricount and others) already settle expenses. In two tests plain Claude, with Python available, was also right: on a seven-line chat log with an uneven split, a refund, a second currency and "I covered" lines it got every balance within one cent and flagged the ambiguous lines itself; on eight balances needing the fewest payments it found the minimum of five and proved it. The script's gain is repeatability and checks: shares always add to the total to the cent, balances sum to zero, and bad input (an unknown name, a missing rate, exact amounts that do not add up) is refused instead of guessed. If you only settle a few expenses, plain Claude is enough.
- **The script does not read your chat.** Claude turns the notes into the ledger, and that reading can be wrong. The assumptions list is there so you can catch it.
- **Rates.** Other currencies need a rate you or the group chose, or one looked up for the date; it does not know the rate your card used.
- **Settlement is a suggestion.** It does not move money.

## Example

**Before:** a balance table by hand, with shares like 15.575 left unrounded.

**After:** "Settle up: Dee pays Ana 144.87, Cy pays Ana 125.43, Ben pays Ana 29.95 (EUR). Assumed: the 40 EUR cleaning-fee refund to Ana belongs to all four; if it was hers alone, each of the other three owes 10.00 less."

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
