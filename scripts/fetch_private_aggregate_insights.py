"""Create a privacy-safe activity snapshot using the locally authenticated gh CLI.

The GraphQL query requests only scalar totals and the authenticated login. It never
requests repository names, organizations, URLs, titles, node IDs or work-item data.
This script is intentionally local-only: do not put a broad personal token in the
public repository's GitHub Actions secrets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "profile.json"
PUBLIC_ACTIVITY_PATH = ROOT / "data" / "contributions.json"
OUTPUT_PATH = ROOT / "data" / "insights.json"
WINDOW_DAYS = 90

QUERY = """
query(
  $currentFrom: DateTime!
  $currentTo: DateTime!
  $previousFrom: DateTime!
  $previousTo: DateTime!
  $currentMerged: String!
  $previousMerged: String!
  $currentClosed: String!
  $previousClosed: String!
) {
  viewer {
    login
    current: contributionsCollection(from: $currentFrom, to: $currentTo) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
    }
    previous: contributionsCollection(from: $previousFrom, to: $previousTo) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
    }
  }
  currentMerged: search(type: ISSUE, query: $currentMerged, first: 1) {
    issueCount
  }
  previousMerged: search(type: ISSUE, query: $previousMerged, first: 1) {
    issueCount
  }
  currentClosed: search(type: ISSUE, query: $currentClosed, first: 1) {
    issueCount
  }
  previousClosed: search(type: ISSUE, query: $previousClosed, first: 1) {
    issueCount
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=datetime.now(timezone.utc).date(),
        help="Inclusive end date in YYYY-MM-DD format (default: today in UTC)",
    )
    return parser.parse_args()


def date_time(day: date, end_of_day: bool = False) -> str:
    clock = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(day, clock, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def period(end: date) -> tuple[date, date]:
    return end - timedelta(days=WINDOW_DAYS - 1), end


def run_query(username: str, ranges: dict[str, date]) -> dict[str, Any]:
    current_span = f"{ranges['current_from'].isoformat()}..{ranges['current_to'].isoformat()}"
    previous_span = f"{ranges['previous_from'].isoformat()}..{ranges['previous_to'].isoformat()}"
    fields = {
        "query": QUERY,
        "currentFrom": date_time(ranges["current_from"]),
        "currentTo": date_time(ranges["current_to"], end_of_day=True),
        "previousFrom": date_time(ranges["previous_from"]),
        "previousTo": date_time(ranges["previous_to"], end_of_day=True),
        "currentMerged": f"author:{username} is:pr is:merged merged:{current_span}",
        "previousMerged": f"author:{username} is:pr is:merged merged:{previous_span}",
        "currentClosed": f"author:{username} is:issue is:closed closed:{current_span}",
        "previousClosed": f"author:{username} is:issue is:closed closed:{previous_span}",
    }
    command = ["gh", "api", "graphql"]
    for key, value in fields.items():
        command.extend(("-f", f"{key}={value}"))

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "The aggregate GitHub query failed; no snapshot was written. "
            "Run `gh auth status` and try again."
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "GitHub returned an invalid aggregate response; no snapshot was written."
        ) from error


def active_days_from_public(start: date, end: date) -> int:
    payload = json.loads(PUBLIC_ACTIVITY_PATH.read_text(encoding="utf-8"))
    raw_days = payload.get("days")
    if not isinstance(raw_days, list):
        raise ValueError("Public contribution data does not contain a days list")

    counts: dict[date, int] = {}
    for raw_day in raw_days:
        parsed = date.fromisoformat(str(raw_day["date"]))
        count = raw_day["count"]
        if parsed in counts:
            raise ValueError("Public contribution data contains a duplicate date")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("Public contribution counts must be non-negative integers")
        counts[parsed] = count

    expected = [start + timedelta(days=offset) for offset in range(WINDOW_DAYS)]
    if expected[-1] != end or any(day not in counts for day in expected):
        raise ValueError(
            "Public contribution data does not cover the requested 90-day window. "
            "Run fetch_contributions.py first."
        )
    return sum(counts[day] > 0 for day in expected)


def non_negative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"GitHub returned an invalid count for {field}")
    return value


def work_mix(collection: dict[str, Any]) -> dict[str, int]:
    return {
        "commit_contributions": non_negative_int(
            collection["totalCommitContributions"], "commit contributions"
        ),
        "pull_requests_opened": non_negative_int(
            collection["totalPullRequestContributions"], "pull request contributions"
        ),
        "issues_opened": non_negative_int(
            collection["totalIssueContributions"], "issue contributions"
        ),
        "reviews_submitted": non_negative_int(
            collection["totalPullRequestReviewContributions"], "review contributions"
        ),
    }


def shipping_pulse(
    collection: dict[str, Any], merged: Any, closed: Any, active_days: int
) -> dict[str, int]:
    return {
        "pull_requests_merged": non_negative_int(merged, "merged pull requests"),
        "authored_issues_closed": non_negative_int(closed, "authored issues closed"),
        "repositories_with_commits": non_negative_int(
            collection["totalRepositoriesWithContributedCommits"],
            "repositories with contributed commits",
        ),
        "active_days": non_negative_int(active_days, "active days"),
    }


def main() -> None:
    args = parse_args()
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    username = str(profile["username"])

    current_from, current_to = period(args.as_of)
    previous_to = current_from - timedelta(days=1)
    previous_from, previous_to = period(previous_to)
    ranges = {
        "current_from": current_from,
        "current_to": current_to,
        "previous_from": previous_from,
        "previous_to": previous_to,
    }

    response = run_query(username, ranges)
    if set(response) != {"data"}:
        raise ValueError("Unexpected top-level fields in GitHub's aggregate response")
    data = response["data"]
    expected_fields = {
        "viewer",
        "currentMerged",
        "previousMerged",
        "currentClosed",
        "previousClosed",
    }
    if set(data) != expected_fields:
        raise ValueError("Unexpected fields in GitHub's aggregate response")

    viewer = data["viewer"]
    if str(viewer["login"]).casefold() != username.casefold():
        raise RuntimeError(
            f"The gh CLI is authenticated as a different account; expected {username}."
        )

    current_active_days = active_days_from_public(current_from, current_to)
    previous_active_days = active_days_from_public(previous_from, previous_to)
    snapshot = {
        "schema_version": 1,
        "generated_on": current_to.isoformat(),
        "window": {
            "from": current_from.isoformat(),
            "to": current_to.isoformat(),
            "days": WINDOW_DAYS,
        },
        "previous_window": {
            "from": previous_from.isoformat(),
            "to": previous_to.isoformat(),
            "days": WINDOW_DAYS,
        },
        "work_mix": {
            "current": work_mix(viewer["current"]),
            "previous": work_mix(viewer["previous"]),
        },
        "shipping_pulse": {
            "current": shipping_pulse(
                viewer["current"],
                data["currentMerged"]["issueCount"],
                data["currentClosed"]["issueCount"],
                current_active_days,
            ),
            "previous": shipping_pulse(
                viewer["previous"],
                data["previousMerged"]["issueCount"],
                data["previousClosed"]["issueCount"],
                previous_active_days,
            ),
        },
    }

    OUTPUT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {OUTPUT_PATH.relative_to(ROOT)}: two privacy-safe {WINDOW_DAYS}-day "
        "aggregate windows; repository and work-item metadata were never requested."
    )


if __name__ == "__main__":
    main()
