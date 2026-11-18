#!/usr/bin/env python3
"""Settle a shared-expense ledger: who owes what, and the fewest payments that clear it.

Usage:
  python settle.py LEDGER.json

LEDGER.json:
  {"base": "EUR", "rates": {"USD": "0.92"},            # 1 USD = 0.92 EUR; one rate per other currency
   "people": ["Ana", "Ben", "Cy"],
   "entries": [
     {"id": "airbnb", "payer": "Ana", "amount": "480", "currency": "EUR", "split": {"equal": ["Ana", "Ben", "Cy"]}},
     {"id": "boat",   "payer": "Ben", "amount": "110", "split": {"shares": {"Ben": 40, "Cy": 30, "Ana": 40}}},
     {"id": "ticket", "payer": "Ana", "amount": "18",  "split": {"exact": {"Ben": "18"}}},
     {"id": "refund", "payer": "Ana", "amount": "-40", "split": {"equal": ["Ana", "Ben", "Cy"]}}]}

A negative amount is a refund to the payer. Money is worked in whole cents: each entry is converted
once, rounded half-to-even, and split so the shares add up to the total to the cent (largest
remainder). Prints JSON with each entry's shares, each person's balance (positive: is owed money),
and the payments. Read-only.
"""
import itertools
import json
import sys
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

CENT = Decimal("0.01")
MAX_EXACT = 12  # the fewest-payments search tries every subset of people; above this use the greedy answer


class LedgerError(Exception):
    pass


def money(value, what):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise LedgerError(f"{what}: {value!r} is not a number")
    if not number.is_finite():
        raise LedgerError(f"{what}: {value!r} is not a number")
    return number


def cents(amount):
    return int((amount / CENT).to_integral_value(ROUND_HALF_EVEN))


def fmt(c):
    sign = "-" if c < 0 else ""
    return f"{sign}{abs(c) // 100}.{abs(c) % 100:02d}"


def allocate(total, weights):
    """Split total cents by weights so the parts add to the total exactly (largest remainder; ties go
    to the earlier name in the list)."""
    whole = sum(weights.values())
    parts = {name: total * w // whole for name, w in weights.items()}
    leftover = total - sum(parts.values())
    order = sorted(weights, key=lambda name: (-(total * weights[name] % whole), list(weights).index(name)))
    for name in order[:leftover]:
        parts[name] += 1
    return parts


def entry_shares(entry, rate, people):
    """(total cents, {person: share in cents}) for one entry, in the base currency."""
    eid = entry.get("id", "?")
    amount = money(entry.get("amount"), f"entry {eid} amount")
    if amount == 0:
        raise LedgerError(f"entry {eid}: amount is zero")
    sign = 1 if amount > 0 else -1
    total = cents(abs(amount) * rate)
    split = entry.get("split") or {}
    if "equal" in split:
        names = list(dict.fromkeys(split["equal"]))
        weights = {n: 1 for n in names}
    elif "shares" in split:
        names = list(split["shares"])
        weights = {n: money(w, f"entry {eid} share") for n, w in split["shares"].items()}
        if any(w <= 0 for w in weights.values()):
            raise LedgerError(f"entry {eid}: shares must be positive")
        scale = max((abs(w.as_tuple().exponent) for w in weights.values()), default=0)
        weights = {n: int(w * 10 ** scale) for n, w in weights.items()}
    elif "exact" in split:
        names = list(split["exact"])
        listed = {n: cents(abs(money(v, f"entry {eid} exact amount")) * rate) for n, v in split["exact"].items()}
        if sum(listed.values()) != total and abs(sum(listed.values()) - total) > len(listed):
            raise LedgerError(f"entry {eid}: exact amounts add to {fmt(sum(listed.values()))}, not {fmt(total)}")
        weights = listed
    else:
        raise LedgerError(f"entry {eid}: split needs one of equal, shares or exact")
    if not names or not set(names) <= set(people):
        raise LedgerError(f"entry {eid}: unknown person in split: {sorted(set(names) - set(people))}")
    if "exact" in split and sum(weights.values()) == total:
        parts = weights
    else:
        parts = allocate(total, weights)
    return sign * total, {n: sign * c for n, c in parts.items()}


def fewest_payments(balances):
    """Payments (from, to, cents) that clear the balances. Splits the people into the largest number
    of groups that each net to zero, then settles each group greedily: that is the minimum count."""
    people = [p for p, b in balances.items() if b != 0]
    groups = [people]
    if 1 < len(people) <= MAX_EXACT:
        groups = best_partition(people, balances)
    payments = []
    for group in groups:
        owed = {p: balances[p] for p in group}
        while any(owed.values()):
            debtor = min(owed, key=lambda p: owed[p])
            creditor = max(owed, key=lambda p: owed[p])
            pay = min(-owed[debtor], owed[creditor])
            payments.append((debtor, creditor, pay))
            owed[debtor] += pay
            owed[creditor] -= pay
    return payments


def best_partition(people, balances):
    n = len(people)
    value = [balances[p] for p in people]
    full = (1 << n) - 1
    total = {0: 0}
    for mask in range(1, full + 1):
        low = (mask & -mask).bit_length() - 1
        total[mask] = total[mask & (mask - 1)] + value[low]
    zero = [m for m in range(1, full + 1) if total[m] == 0]
    best = {0: (0, [])}  # mask -> (groups, list of masks)
    for mask in range(1, full + 1):
        low = mask & -mask
        choice = None
        for sub in zero:
            if sub & low and sub & mask == sub and (mask ^ sub) in best:
                groups = best[mask ^ sub][0] + 1
                if choice is None or groups > choice[0]:
                    choice = (groups, best[mask ^ sub][1] + [sub])
        if choice:
            best[mask] = choice
    return [[people[i] for i in range(n) if m >> i & 1] for m in best[full][1]]


def settle(ledger):
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), list) or not ledger["entries"]:
        raise LedgerError("the ledger needs an entries list")
    people = list(ledger.get("people") or [])
    if not people or len(set(people)) != len(people):
        raise LedgerError("the ledger needs a people list with no repeated names")
    base = ledger.get("base", "EUR")
    rates = {c: money(r, f"rate for {c}") for c, r in (ledger.get("rates") or {}).items()}
    if any(r <= 0 for r in rates.values()):
        raise LedgerError("rates must be positive")
    balances, detail = {p: 0 for p in people}, []
    for entry in ledger["entries"]:
        eid = entry.get("id", "?")
        if entry.get("payer") not in balances:
            raise LedgerError(f"entry {eid}: payer {entry.get('payer')!r} is not in people")
        currency = entry.get("currency", base)
        if currency != base and currency not in rates:
            raise LedgerError(f"entry {eid}: no rate for {currency}")
        total, shares = entry_shares(entry, Decimal(1) if currency == base else rates[currency], people)
        balances[entry["payer"]] += total
        for name, share in shares.items():
            balances[name] -= share
        detail.append({"id": eid, "payer": entry["payer"], "total": fmt(total), "currency_paid": currency,
                       "shares": {n: fmt(c) for n, c in shares.items()}})
    payments = fewest_payments(balances)
    return {
        "base": base,
        "entries": detail,
        "balances": {p: fmt(b) for p, b in balances.items()},
        "payments": [{"from": a, "to": b, "amount": fmt(c)} for a, b, c in payments],
        "checks": {"balances_sum_to_zero": sum(balances.values()) == 0,
                   "payments_clear_every_balance": clears(balances, payments),
                   "payment_count": len(payments)},
    }


def clears(balances, payments):
    left = dict(balances)
    for a, b, c in payments:
        left[a] += c
        left[b] -= c
    return all(v == 0 for v in left.values())


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__.splitlines()[0] + "\nusage: settle.py LEDGER.json", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as handle:
            result = settle(json.load(handle))
    except (OSError, ValueError, LedgerError) as error:
        print(f"bad ledger: {error}", file=sys.stderr)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
