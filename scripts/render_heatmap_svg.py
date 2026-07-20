"""Render public contribution data as a self-contained animated SVG."""

from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "contributions.json"
OUTPUT_PATH = ROOT / "contribution-heatmap.svg"

WIDTH = 860
HEIGHT = 210
LEFT = 60
TOP = 47
CELL = 11
GAP = 3
STEP = CELL + GAP

COLORS = {
    0: "#21262d",
    1: "#0e4429",
    2: "#006d32",
    3: "#26a641",
    4: "#39d353",
}


def day_word(value: int) -> str:
    return "day" if value == 1 else "days"


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    days = payload["days"]
    stats = payload["stats"]
    username = str(payload["username"])

    first_date = date.fromisoformat(days[0]["date"])
    total = int(stats["total"])
    current = int(stats["current_streak"])
    longest = int(stats["longest_streak"])

    title = f"{username}'s contribution activity"
    description = (
        f"{total} contributions in the last year. "
        f"Current streak: {current} {day_word(current)}. "
        f"Longest streak: {longest} {day_word(longest)}."
    )

    delay_css = "\n".join(
        f"      .delay-{index} {{ animation-delay: {0.12 + index * 0.018:.3f}s; }}"
        for index in range(60)
    )

    month_labels: list[str] = []
    seen_months: set[str] = set()
    previous_x = -100
    for item in days:
        current_date = date.fromisoformat(item["date"])
        month_key = current_date.strftime("%Y-%m")
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        week = (current_date - first_date).days // 7
        x = LEFT + week * STEP
        if x - previous_x < 30 or x > WIDTH - 35:
            continue
        month_labels.append(
            f'    <text class="label" x="{x}" y="38">{current_date.strftime("%b")}</text>'
        )
        previous_x = x

    cells: list[str] = []
    for item in days:
        current_date = date.fromisoformat(item["date"])
        offset = (current_date - first_date).days
        week = offset // 7
        weekday = offset % 7
        x = LEFT + week * STEP
        y = TOP + weekday * STEP
        level = max(0, min(4, int(item["level"])))
        delay = min(59, week + weekday)
        cells.append(
            "    "
            f'<rect class="cell level-{level} delay-{delay}" '
            f'x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
            f'aria-label="{escape(str(item["date"]))}: {int(item["count"])} contributions" />'
        )

    legend_x = 687
    legend_cells = "\n".join(
        f'    <rect x="{legend_x + 36 + index * 16}" y="178" '
        f'width="10" height="10" rx="2" fill="{COLORS[index]}" />'
        for index in range(5)
    )

    stats_text = (
        f"{total:,} contributions  ·  "
        f"{current} {day_word(current)} current  ·  "
        f"{longest} {day_word(longest)} best"
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
  viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title description">
  <title id="title">{escape(title)}</title>
  <desc id="description">{escape(description)}</desc>
  <style>
    text {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
        "Liberation Mono", "Courier New", monospace;
    }}
    .heading {{ fill: #f0f6fc; font-size: 14px; font-weight: 600; }}
    .prompt {{ fill: #7ee787; }}
    .label {{ fill: #8b949e; font-size: 10px; }}
    .stat {{ fill: #8b949e; font-size: 11px; }}
    .cell {{
      opacity: 0;
      transform-box: fill-box;
      transform-origin: center;
      animation: reveal 0.34s cubic-bezier(.2,.8,.2,1) forwards;
    }}
    .level-0 {{ fill: {COLORS[0]}; }}
    .level-1 {{ fill: {COLORS[1]}; }}
    .level-2 {{ fill: {COLORS[2]}; }}
    .level-3 {{ fill: {COLORS[3]}; }}
    .level-4 {{ fill: {COLORS[4]}; }}
{delay_css}
    @keyframes reveal {{
      from {{ opacity: 0; transform: translateY(-7px) scale(.72); }}
      to {{ opacity: 1; transform: translateY(0) scale(1); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .cell {{ animation: none; opacity: 1; transform: none; }}
    }}
  </style>

  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14"
    fill="#0d1117" stroke="#30363d" />
  <circle cx="19" cy="20" r="4" fill="#ff7b72" />
  <circle cx="32" cy="20" r="4" fill="#d29922" />
  <circle cx="45" cy="20" r="4" fill="#3fb950" />
  <text class="heading" x="60" y="25"><tspan class="prompt">$</tspan> git activity --year</text>

{chr(10).join(month_labels)}
  <text class="label" x="24" y="{TOP + STEP + 9}">Mon</text>
  <text class="label" x="24" y="{TOP + STEP * 3 + 9}">Wed</text>
  <text class="label" x="24" y="{TOP + STEP * 5 + 9}">Fri</text>

{chr(10).join(cells)}

  <line x1="20" y1="160" x2="{WIDTH - 20}" y2="160" stroke="#21262d" />
  <text class="stat" x="24" y="187">{escape(stats_text)}</text>
  <text class="label" x="{legend_x}" y="187">less</text>
{legend_cells}
  <text class="label" x="{legend_x + 122}" y="187">more</text>
</svg>
"""
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.name} ({len(days)} cells).")


if __name__ == "__main__":
    main()
