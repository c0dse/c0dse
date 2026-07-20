"""Render a clear, GitHub-native developer signal from public activity data."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "contributions.json"
CONFIG_PATH = ROOT / "profile.json"
OUTPUT_PATH = ROOT / "developer-signal.svg"

WIDTH = 860
HEIGHT = 430
WEEK_COUNT = 26

MONTHS = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)


def clean_label(value: object) -> str:
    """Normalize separators while keeping profile configuration human-readable."""
    return str(value).replace("Â", "").replace("·", "/")


def short_date(value: date) -> str:
    return f"{value.day} {MONTHS[value.month - 1].title()}"


def build_weeks(days: list[dict[str, object]]) -> list[dict[str, object]]:
    counts = {
        date.fromisoformat(str(day["date"])): int(day["count"]) for day in days
    }
    end = max(counts)
    current_week = end - timedelta(days=end.weekday())
    starts = [
        current_week - timedelta(weeks=offset)
        for offset in reversed(range(WEEK_COUNT))
    ]

    weeks: list[dict[str, object]] = []
    for start in starts:
        finish = min(start + timedelta(days=6), end)
        total = sum(
            counts.get(start + timedelta(days=day_offset), 0)
            for day_offset in range(7)
        )
        weeks.append({"start": start, "end": finish, "count": total})
    return weeks


def contribution_insights(
    days: list[dict[str, object]], weeks: list[dict[str, object]]
) -> dict[str, object]:
    counts = [int(day["count"]) for day in days]
    active_days = sum(count > 0 for count in counts)
    active_weeks = sum(int(week["count"]) > 0 for week in weeks)
    last_28 = sum(counts[-28:])
    previous_28 = sum(counts[-56:-28])

    if previous_28 == 0:
        momentum = "NEW" if last_28 else "0%"
    else:
        change = round((last_28 - previous_28) / previous_28 * 100)
        momentum = f"{change:+d}%"

    weekday_totals: defaultdict[int, int] = defaultdict(int)
    for day in days:
        parsed = date.fromisoformat(str(day["date"]))
        weekday_totals[parsed.weekday()] += int(day["count"])
    busiest_weekday = max(weekday_totals, key=weekday_totals.get)

    return {
        "active_days": active_days,
        "active_weeks": active_weeks,
        "average_active_day": sum(counts) / active_days if active_days else 0.0,
        "last_28": last_28,
        "previous_28": previous_28,
        "momentum": momentum,
        "busiest_weekday": (
            "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
        )[busiest_weekday],
    }


def render_chart(
    weeks: list[dict[str, object]], total: int
) -> tuple[str, str, str, dict[str, object]]:
    chart_left = 40.0
    chart_right = 585.0
    baseline = 296.0
    chart_height = 134.0
    step = (chart_right - chart_left) / (len(weeks) - 1)
    bar_width = 11.0
    maximum = max(int(week["count"]) for week in weeks) or 1
    average = total / 52
    peak = max(weeks, key=lambda week: int(week["count"]))

    bars: list[str] = []
    points: list[str] = []
    for index, week in enumerate(weeks):
        count = int(week["count"])
        ratio = count / maximum
        height = max(2.0, ratio * chart_height) if count else 2.0
        x = chart_left + index * step
        y = baseline - height
        if count == 0:
            level = "zero"
        elif ratio < 0.20:
            level = "one"
        elif ratio < 0.45:
            level = "two"
        elif ratio < 0.72:
            level = "three"
        else:
            level = "four"
        bars.append(
            f'    <rect class="bar level-{level}" x="{x - bar_width / 2:.1f}" '
            f'y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" rx="2" />'
        )
        points.append(f"{x:.1f},{y:.1f}")

    label_specs: list[tuple[float, str]] = []
    previous_month: int | None = None
    for index, week in enumerate(weeks):
        start = week["start"]
        if not isinstance(start, date) or start.month == previous_month:
            continue
        previous_month = start.month
        x = chart_left + index * step
        label = MONTHS[start.month - 1]
        if start.month == 1:
            label += f" '{str(start.year)[-2:]}"
        label_specs.append((x, label))

    # A range can begin in the final week of a month. Drop that partial-month
    # label when it would collide with the first full month.
    if len(label_specs) > 1 and label_specs[1][0] - label_specs[0][0] < 42:
        label_specs = label_specs[1:]
    labels = [
        f'    <text class="axis month-label" x="{x:.1f}" y="318">{label}</text>'
        for x, label in label_specs
    ]

    average_y = baseline - min(average / maximum, 1) * chart_height
    grid = []
    for fraction in (0.0, 0.5, 1.0):
        value = round(maximum * fraction)
        y = baseline - fraction * chart_height
        grid.append(
            f'    <line class="grid" x1="34" y1="{y:.1f}" x2="592" y2="{y:.1f}" />\n'
            f'    <text class="axis" x="29" y="{y + 3:.1f}" text-anchor="end">{value}</text>'
        )

    peak_index = weeks.index(peak)
    peak_x = chart_left + peak_index * step
    peak_y = baseline - int(peak["count"]) / maximum * chart_height
    path = "M " + " L ".join(points)
    chart = f"""  <g aria-label="Weekly public contribution totals for the last 26 weeks">
{chr(10).join(grid)}
    <line class="average-line" x1="34" y1="{average_y:.1f}" x2="592" y2="{average_y:.1f}" />
    <text class="axis average-label" x="588" y="{average_y - 5:.1f}" text-anchor="end">12M AVG {average:.1f}/WK</text>
{chr(10).join(bars)}
    <path class="trajectory" pathLength="1" d="{path}" />
    <path class="signal-runner" pathLength="1" d="{path}" />
    <circle class="peak-dot" cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="4" />
    <line class="peak-guide" x1="{peak_x:.1f}" y1="{peak_y - 7:.1f}" x2="{peak_x:.1f}" y2="125" />
{chr(10).join(labels)}
  </g>"""
    return chart, short_date(peak["start"]), short_date(peak["end"]), peak


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    profile = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    days = payload["days"]
    stats = payload["stats"]
    total = int(stats["total"])
    weeks = build_weeks(days)
    insights = contribution_insights(days, weeks)
    chart, peak_start, peak_end, peak = render_chart(weeks, total)

    fetched = date.fromisoformat(str(payload["fetched_on"]))
    updated = f"{fetched.day} {MONTHS[fetched.month - 1]} {fetched.year}"
    longest = int(stats["longest_streak"])
    momentum = escape(str(insights["momentum"]))
    momentum_class = (
        "positive" if str(insights["momentum"]).startswith("+") else "neutral"
    )

    identity = (
        f'{clean_label(profile["role"])} @ {clean_label(profile["company"])}'
        f' / {clean_label(profile["location"])}'
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
  viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">c0dse developer signal</title>
  <desc id="desc">A GitHub-themed analysis of c0dse's public contributions. It shows 26 weekly totals, one-year activity metrics and the change between two 28-day periods.</desc>
  <style>
    :root {{
      color-scheme: light dark;
      --canvas: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #f0f6fc; --muted: #8b949e; --green: #3fb950;
      --green-1: #0e4429; --green-2: #006d32; --green-3: #26a641;
      --blue: #58a6ff; --orange: #d29922;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --canvas: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
        --text: #1f2328; --muted: #59636e; --green: #1f883d;
        --green-1: #aceebb; --green-2: #4ac26b; --green-3: #2da44e;
        --blue: #0969da; --orange: #9a6700;
      }}
    }}
    text {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      fill: var(--text); text-rendering: geometricPrecision;
    }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }}
    .canvas {{ fill: var(--canvas); }}
    .frame {{ fill: none; stroke: var(--border); }}
    .divider {{ stroke: var(--border); stroke-width: 1; }}
    .eyebrow {{ fill: var(--muted); font-size: 10px; font-weight: 600; letter-spacing: 1.1px; }}
    .title {{ font-size: 26px; font-weight: 650; letter-spacing: -.5px; }}
    .subtitle {{ fill: var(--muted); font-size: 12px; }}
    .section-title {{ fill: var(--text); font-size: 11px; font-weight: 600; }}
    .axis {{ fill: var(--muted); font-size: 9px; }}
    .month-label {{ font-weight: 600; letter-spacing: .7px; }}
    .grid {{ stroke: var(--border); stroke-width: 1; stroke-dasharray: 2 5; }}
    .average-line {{ stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 4; opacity: .6; }}
    .bar {{ shape-rendering: geometricPrecision; }}
    .level-zero {{ fill: var(--surface); }}
    .level-one {{ fill: var(--green-1); }}
    .level-two {{ fill: var(--green-2); }}
    .level-three {{ fill: var(--green-3); }}
    .level-four {{ fill: var(--green); }}
    .trajectory, .signal-runner {{ fill: none; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }}
    .trajectory {{ stroke: var(--blue); stroke-width: 1.5; opacity: .44; }}
    .signal-runner {{
      stroke: var(--green); stroke-width: 2.6; stroke-dasharray: .11 .89;
      stroke-dashoffset: 1; animation: signal-travel 3.8s linear infinite;
    }}
    .peak-dot {{ fill: var(--canvas); stroke: var(--orange); stroke-width: 2; }}
    .peak-guide {{ stroke: var(--orange); stroke-width: 1; stroke-dasharray: 2 3; }}
    .big-number {{ font-size: 48px; font-weight: 650; letter-spacing: -2px; }}
    .number-caption {{ fill: var(--muted); font-size: 11px; }}
    .metric-value {{ font-size: 20px; font-weight: 650; }}
    .metric-label {{ fill: var(--muted); font-size: 9px; letter-spacing: .6px; }}
    .momentum {{ font-size: 34px; font-weight: 650; letter-spacing: -1px; }}
    .positive {{ fill: var(--green); }}
    .neutral {{ fill: var(--blue); }}
    .focus-line {{ fill: var(--muted); font-size: 11px; }}
    .focus-value {{ font-size: 12px; font-weight: 600; }}
    .legend-dot {{ fill: var(--green); }}
    @keyframes signal-travel {{ to {{ stroke-dashoffset: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .signal-runner {{ animation: none; display: none; }}
    }}
  </style>

  <rect class="canvas" width="{WIDTH}" height="{HEIGHT}" rx="6" />
  <rect class="frame" x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="6" />

  <text class="title mono" x="28" y="38">c0dse</text>
  <text class="eyebrow mono" x="127" y="34">/ DEVELOPER SIGNAL</text>
  <text class="subtitle" x="28" y="61">{escape(identity)}</text>
  <circle class="legend-dot" cx="703" cy="31" r="3" />
  <text class="eyebrow mono" x="714" y="34">LIVE PUBLIC DATA</text>
  <text class="subtitle mono" x="831" y="58" text-anchor="end">UPDATED {updated}</text>
  <line class="divider" x1="1" y1="78" x2="859" y2="78" />

  <text class="section-title mono" x="34" y="106">WEEKLY VELOCITY / LAST 26 WEEKS</text>
  <text class="eyebrow mono" x="592" y="106" text-anchor="end">PEAK {int(peak['count'])} / {peak_start}-{peak_end}</text>
  <text class="axis mono" x="34" y="122">ONE BAR = ONE WEEK / HEIGHT = PUBLIC CONTRIBUTIONS</text>
{chart}

  <line class="divider" x1="612" y1="94" x2="612" y2="306" />
  <text class="eyebrow mono" x="633" y="108">PUBLIC SIGNAL / 12 MONTHS</text>
  <text class="big-number" x="630" y="160">{total:,}</text>
  <text class="number-caption" x="632" y="178">contributions recorded by GitHub</text>
  <line class="divider" x1="632" y1="194" x2="831" y2="194" />

  <text class="metric-value" x="632" y="230">{insights['active_days']}</text>
  <text class="metric-label mono" x="632" y="245">ACTIVE DAYS</text>
  <text class="metric-value" x="744" y="230">{longest}d</text>
  <text class="metric-label mono" x="744" y="245">LONGEST STREAK</text>
  <text class="metric-value" x="632" y="282">{int(peak['count'])}</text>
  <text class="metric-label mono" x="632" y="297">26W PEAK</text>
  <text class="metric-value" x="744" y="282">{insights['average_active_day']:.1f}</text>
  <text class="metric-label mono" x="744" y="297">AVG / ACTIVE DAY</text>

  <line class="divider" x1="1" y1="332" x2="859" y2="332" />
  <text class="eyebrow mono" x="28" y="356">28-DAY CHANGE</text>
  <text class="momentum {momentum_class}" x="28" y="397">{momentum}</text>
  <text class="focus-line" x="122" y="378">{insights['last_28']} contributions now</text>
  <text class="focus-line" x="122" y="397">vs {insights['previous_28']} in the prior 28 days</text>

  <line class="divider" x1="290" y1="350" x2="290" y2="407" />
  <text class="eyebrow mono" x="316" y="356">HOW TO READ</text>
  <text class="focus-value" x="316" y="379">bars = weekly totals / line = trajectory</text>
  <text class="focus-line" x="316" y="399">orange marker = 26-week peak</text>

  <text class="axis mono" x="831" y="419" text-anchor="end">busiest public contribution rhythm = {insights['busiest_weekday']}</text>
</svg>
"""
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH.name}: {total} contributions, "
        f"{insights['active_days']} active days, {insights['momentum']} 28-day change."
    )


if __name__ == "__main__":
    main()
