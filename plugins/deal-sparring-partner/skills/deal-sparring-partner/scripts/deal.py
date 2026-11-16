#!/usr/bin/env python3
"""Numbers for a negotiation role-play: the other side's concession ladder, and the final score.

Usage:
  python deal.py ladder --side buyer --opening 14500 --target 13800 --reservation 12800 [--rungs 6]
  python deal.py score  --side buyer --walkaway 13500 --reservation 12800 --final 12900
  python deal.py score  --side buyer --walkaway 13500 --reservation 12800 --no-deal

--side is the USER's side. For a buyer the other side is the seller: the seller opens high and will
not go below its reservation. All amounts are one comparable number (turn months of free rent,
warranty and so on into money first). Read-only; prints JSON.
"""
import argparse
import json
import sys

SHRINK = 0.6  # each concession is 60% of the one before: real counterparts slow down


def ladder(side, opening, target, reservation, rungs=6):
    """The other side's offers, round by round, moving from opening towards reservation in
    steadily smaller steps. The target rung is where it would be happy to close."""
    if side == "buyer":
        ok = opening >= target >= reservation
    else:
        ok = opening <= target <= reservation
    if not ok:
        raise ValueError("the other side must open best for itself, then target, then reservation (its worst)")
    if rungs < 2:
        raise ValueError("need at least 2 rungs")
    weights = [SHRINK ** i for i in range(rungs - 1)]
    total = sum(weights)
    span = reservation - opening
    offers, at = [opening], opening
    for weight in weights:
        at += span * weight / total
        offers.append(round(at, 2))
    offers[-1] = reservation
    return {
        "other_side": "seller" if side == "buyer" else "buyer",
        "rungs": [{"round": i, "offer": o, "at_or_past_target": (o <= target if side == "buyer" else o >= target)}
                  for i, o in enumerate(offers)],
        "never_cross": reservation,
    }


def score(side, walkaway, reservation, final=None):
    """Where the final price fell inside the zone both sides could accept."""
    buyer = side == "buyer"
    zone_exists = reservation <= walkaway if buyer else reservation >= walkaway
    low, high = sorted((walkaway, reservation))
    zone = round(high - low, 2)
    out = {"zone": [low, high], "zone_exists": zone_exists, "zone_width": zone if zone_exists else 0}
    if final is None:
        out["outcome"] = "no-deal"
        out["verdict"] = "missed deal: a price both could accept existed" if zone_exists else "no deal was possible"
        return out
    worse_than_walkaway = final > walkaway if buyer else final < walkaway
    if worse_than_walkaway:
        out["outcome"] = "worse-than-walkaway"
        out["verdict"] = "the user agreed to a deal worse than their own alternative"
        return out
    if not zone_exists:
        out["outcome"] = "deal-outside-zone"
        out["verdict"] = "the other side went past its own reservation: the scenario was too easy"
        return out
    kept = (walkaway - final) if buyer else (final - walkaway)
    share = 100.0 if zone == 0 else round(kept / zone * 100, 1)
    out.update({"outcome": "deal", "final": final, "user_share_of_zone_pct": min(100.0, max(0.0, share))})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ladder", "score"):
        p = sub.add_parser(name)
        p.add_argument("--side", choices=["buyer", "seller"], required=True)
        p.add_argument("--reservation", type=float, required=True, help="the OTHER side's worst acceptable amount")
        if name == "ladder":
            p.add_argument("--opening", type=float, required=True)
            p.add_argument("--target", type=float, required=True)
            p.add_argument("--rungs", type=int, default=6)
        else:
            p.add_argument("--walkaway", type=float, required=True, help="the USER's worst acceptable amount")
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("--final", type=float)
            group.add_argument("--no-deal", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "ladder":
            result = ladder(args.side, args.opening, args.target, args.reservation, args.rungs)
        else:
            result = score(args.side, args.walkaway, args.reservation, None if args.no_deal else args.final)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
