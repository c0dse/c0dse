"""Fetch c0dse's public contribution calendar without authentication."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "profile.json"
OUTPUT_PATH = ROOT / "data" / "contributions.json"


class ContributionParser(HTMLParser):
    """Collect contribution cells and their matching accessible tooltips."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.days: dict[str, dict[str, object]] = {}
        self.tooltip_for: str | None = None
        self.tooltip_chunks: list[str] = []
        self.tooltips: dict[str, str] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = {key: value or "" for key, value in attrs}
        classes = set(attributes.get("class", "").split())

        if tag == "td" and "ContributionCalendar-day" in classes:
            cell_id = attributes.get("id")
            day = attributes.get("data-date")
            level = attributes.get("data-level")
            if cell_id and day and level is not None:
                self.days[cell_id] = {
                    "date": day,
                    "level": int(level),
                }

        if tag == "tool-tip" and attributes.get("for"):
            self.tooltip_for = attributes["for"]
            self.tooltip_chunks = []

    def handle_data(self, data: str) -> None:
        if self.tooltip_for is not None:
            self.tooltip_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip" and self.tooltip_for is not None:
            self.tooltips[self.tooltip_for] = " ".join(
                "".join(self.tooltip_chunks).split()
            )
            self.tooltip_for = None
            self.tooltip_chunks = []


def contribution_count(tooltip: str) -> int:
    if tooltip.startswith("No contributions"):
        return 0

    match = re.match(r"([0-9,]+) contributions?", tooltip)
    if not match:
        raise ValueError(f"Unexpected contribution tooltip: {tooltip!r}")
    return int(match.group(1).replace(",", ""))


def calculate_streaks(days: list[dict[str, object]]) -> tuple[int, int]:
    counts = {
        date.fromisoformat(str(day["date"])): int(day["count"]) for day in days
    }
    ordered_dates = sorted(counts)

    longest = 0
    running = 0
    previous: date | None = None
    for current in ordered_dates:
        if previous is None or current == previous + timedelta(days=1):
            running = running + 1 if counts[current] > 0 else 0
        else:
            running = 1 if counts[current] > 0 else 0
        longest = max(longest, running)
        previous = current

    cursor = ordered_dates[-1]
    # Do not let an unfinished, zero-contribution current day break the streak.
    if cursor == date.today() and counts[cursor] == 0:
        cursor -= timedelta(days=1)

    current_streak = 0
    while counts.get(cursor, 0) > 0:
        current_streak += 1
        cursor -= timedelta(days=1)

    return current_streak, longest


def build_payload(username: str, parser: ContributionParser) -> dict[str, object]:
    parsed_days: list[dict[str, object]] = []
    for cell_id, day in parser.days.items():
        tooltip = parser.tooltips.get(cell_id)
        if tooltip is None:
            raise ValueError(f"Missing tooltip for contribution cell {cell_id}")
        parsed_days.append(
            {
                "date": day["date"],
                "count": contribution_count(tooltip),
                "level": day["level"],
            }
        )

    parsed_days.sort(key=lambda item: str(item["date"]))
    if len(parsed_days) < 350:
        raise ValueError(
            f"Expected roughly one year of contribution cells, got {len(parsed_days)}"
        )

    current_streak, longest_streak = calculate_streaks(parsed_days)
    total = sum(int(day["count"]) for day in parsed_days)
    best = max(parsed_days, key=lambda item: int(item["count"]))

    monthly_totals: defaultdict[str, int] = defaultdict(int)
    for day in parsed_days:
        monthly_totals[str(day["date"])[:7]] += int(day["count"])

    return {
        "username": username,
        "source": f"https://github.com/users/{username}/contributions",
        # Date precision keeps repeat runs on the same day idempotent.
        "fetched_on": datetime.now(timezone.utc).date().isoformat(),
        "range": {
            "from": parsed_days[0]["date"],
            "to": parsed_days[-1]["date"],
        },
        "stats": {
            "total": total,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "best_day": {
                "date": best["date"],
                "count": best["count"],
            },
            "monthly_totals": dict(sorted(monthly_totals.items())),
        },
        "days": parsed_days,
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    username = config["username"]
    source = f"https://github.com/users/{username}/contributions"
    request = Request(
        source,
        headers={
            "Accept": "text/html",
            "User-Agent": f"{username}-profile-readme",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as error:
        raise SystemExit(f"Could not fetch public contributions: {error}") from error

    parser = ContributionParser()
    parser.feed(html)
    payload = build_payload(username, parser)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with "
        f"{payload['stats']['total']} contributions."
    )


if __name__ == "__main__":
    main()
