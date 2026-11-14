#!/usr/bin/env python3
"""How a GitHub repository treats pull requests from outside contributors.

Usage: python repo_pulse.py OWNER/REPO [OWNER/REPO ...] [--prs N]

Reads the last N pull requests (default 100) through the gh CLI and prints a JSON list, one
object per repo. Read-only. Needs `gh` installed and logged in.
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone

EXTERNAL = {"NONE", "FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR", "CONTRIBUTOR"}
MAINTAINER = {"OWNER", "MEMBER", "COLLABORATOR"}
MIN_EXTERNAL = 8  # fewer outside PRs than this is too little to judge
MIN_CLOSED = 5  # fewer closed outside PRs than this gives no merge rate
IGNORED_AFTER_DAYS = 14  # an open PR with no maintainer reply after this long counts as ignored
STALE_OPEN_DAYS = 30
FAST_REPLY_HOURS = 72
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

QUERY = """
query($owner: String!, $name: String!, $n: Int!) {
  repository(owner: $owner, name: $name) {
    isArchived
    defaultBranchRef { target { ... on Commit { committedDate } } }
    pullRequests(first: $n, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        createdAt closedAt mergedAt state isDraft authorAssociation
        author { login __typename }
        comments(first: 20) { nodes { createdAt authorAssociation author { login __typename } } }
        reviews(first: 10) { nodes { createdAt authorAssociation author { login __typename } } }
      }
    }
  }
}
"""


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def human(author):
    """True for a real, present, non-bot account."""
    return bool(author) and author.get("__typename") != "Bot" and not author["login"].endswith("[bot]")


def first_maintainer_reply(pr):
    """When a human maintainer other than the author first commented or reviewed, else None."""
    writer = (pr.get("author") or {}).get("login")
    times = [
        when(item["createdAt"])
        for item in pr["comments"]["nodes"] + pr["reviews"]["nodes"]
        if human(item.get("author"))
        and item["author"]["login"] != writer
        and item.get("authorAssociation") in MAINTAINER
    ]
    return min(times) if times else None


def grade(m):
    """(grade, reasons). The thresholds are a heuristic, not a measurement of intent."""
    if m["archived"]:
        return "archived", ["the repository is archived"]
    if m["judged_prs"] < MIN_EXTERNAL:
        return "insufficient-data", [f"only {m['judged_prs']} outside PRs old enough to judge in the sample"]
    reasons = []
    age = m["days_since_last_commit"]
    if age is not None and age > 365:
        reasons.append(f"no commit to the default branch for {age} days")
    if m["ignored_share"] >= 0.5:
        reasons.append(f"{round(m['ignored_share'] * 100)}% of outside PRs got no maintainer reply")
    if m["merge_rate"] is not None and m["merge_rate"] < 0.2:
        reasons.append(f"only {round(m['merge_rate'] * 100)}% of closed outside PRs were merged")
    if reasons:
        return "avoid", reasons
    reply = m["median_hours_to_first_reply"]
    if (
        m["ignored_share"] <= 0.2
        and reply is not None
        and reply <= FAST_REPLY_HOURS
        and (m["merge_rate"] is None or m["merge_rate"] >= 0.5)
        and (age is None or age <= 90)
    ):
        return "responsive", ["fast replies, few ignored PRs, most closed PRs merged"]
    return "slow", ["answers outside PRs, but slowly or selectively"]


def analyze(repo, data, now=None):
    """Summarise a GraphQL `repository` object for outside contributors."""
    now = now or datetime.now(timezone.utc)
    prs = [
        p for p in data["pullRequests"]["nodes"]
        if p["authorAssociation"] in EXTERNAL and human(p.get("author"))
    ]
    closed = [p for p in prs if p["state"] != "OPEN"]
    merged = [p for p in prs if p["mergedAt"]]
    replies = {id(p): first_maintainer_reply(p) for p in prs}
    hours = [(replies[id(p)] - when(p["createdAt"])).total_seconds() / 3600 for p in prs if replies[id(p)]]
    days_merge = [(when(p["mergedAt"]) - when(p["createdAt"])).total_seconds() / 86400 for p in merged]
    # A PR can only count as ignored once it is closed or has waited long enough; younger open
    # PRs would otherwise dilute the share on busy repos where the sample spans only days.
    # Drafts are not waiting for review.
    judged = [
        p for p in prs
        if p["state"] != "OPEN" or (not p.get("isDraft") and (now - when(p["createdAt"])).days > IGNORED_AFTER_DAYS)
    ]
    ignored = [p for p in judged if not replies[id(p)] and not p["mergedAt"]]  # a merge is an answer
    stale_open = [
        p for p in prs if p["state"] == "OPEN" and (now - when(p["createdAt"])).days > STALE_OPEN_DAYS
    ]
    commit = ((data.get("defaultBranchRef") or {}).get("target") or {}).get("committedDate")
    metrics = {
        "repo": repo,
        "archived": bool(data["isArchived"]),
        "days_since_last_commit": (now - when(commit)).days if commit else None,
        "external_prs": len(prs),
        "merge_rate": round(len(merged) / len(closed), 2) if len(closed) >= MIN_CLOSED else None,
        "median_hours_to_first_reply": round(statistics.median(hours), 1) if hours else None,
        "judged_prs": len(judged),
        "ignored_share": round(len(ignored) / len(judged), 2) if judged else None,
        "median_days_to_merge": round(statistics.median(days_merge), 1) if days_merge else None,
        "stale_open_external_prs": len(stale_open),
    }
    metrics["grade"], metrics["why"] = grade(metrics)
    return metrics


def gh_graphql(owner, name, n):
    out = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"owner={owner}",
         "-f", f"name={name}", "-F", f"n={n}"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    return out.stdout


def pulse(repo, n=100, run=gh_graphql):
    """One repo's summary, or {"repo", "error"} when it cannot be read."""
    if not REPO_NAME.match(repo):
        raise ValueError(f"not an OWNER/REPO name: {repo!r}")
    owner, name = repo.split("/")
    try:
        reply = json.loads(run(owner, name, n))
    except subprocess.CalledProcessError as error:
        return {"repo": repo, "error": (error.stderr or "gh failed").strip()[:300]}
    except subprocess.TimeoutExpired:
        return {"repo": repo, "error": "gh timed out"}
    data = (reply.get("data") or {}).get("repository")
    if not data:
        return {"repo": repo, "error": "repository not found or not readable"}
    return analyze(repo, data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repos", nargs="+", help="OWNER/REPO")
    parser.add_argument("--prs", type=int, default=100, help="pull requests to sample (default 100)")
    args = parser.parse_args(argv)
    if not 10 <= args.prs <= 100:
        parser.error("--prs must be between 10 and 100")
    try:
        results = [pulse(repo, args.prs) for repo in args.repos]
    except FileNotFoundError:
        print("gh is not installed or not on PATH", file=sys.stderr)
        return 2
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    lines = ",\n".join(json.dumps(result) for result in results)
    print(f"[\n{lines}\n]")  # one repo per line
    return 0


if __name__ == "__main__":
    sys.exit(main())
