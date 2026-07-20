"""Render c0dse's contribution signal as a unique cartographic SVG."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "contributions.json"
CONFIG_PATH = ROOT / "profile.json"
OUTPUT_PATH = ROOT / "systems-atlas.svg"

WIDTH = 860
HEIGHT = 500
MAP_CENTER = (302.0, 251.0)
BIN_COUNT = 72

PAPER = "#e9e3d3"
PAPER_LIGHT = "#f3eee2"
INK = "#20251f"
GRID = "#bdb5a4"
SAGE = "#526b58"
SAGE_LIGHT = "#a8b49b"
ORANGE = "#d45f37"

MONTHS = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]


def aggregate_activity(days: list[dict[str, object]]) -> list[float]:
    buckets = [0 for _ in range(BIN_COUNT)]
    for index, item in enumerate(days):
        bucket = min(BIN_COUNT - 1, index * BIN_COUNT // len(days))
        buckets[bucket] += int(item["count"])

    values = [math.log1p(value) for value in buckets]
    for _ in range(3):
        values = [
            (
                values[(index - 2) % BIN_COUNT]
                + 2 * values[(index - 1) % BIN_COUNT]
                + 3 * values[index]
                + 2 * values[(index + 1) % BIN_COUNT]
                + values[(index + 2) % BIN_COUNT]
            )
            / 9
            for index in range(BIN_COUNT)
        ]

    maximum = max(values, default=0)
    return [value / maximum if maximum else 0 for value in values]


def terrain_points(
    activity: list[float], username: str, scale: float
) -> list[tuple[float, float]]:
    digest = hashlib.sha256(username.encode("utf-8")).digest()
    phase_a = int.from_bytes(digest[:2], "big") / 65535 * math.tau
    phase_b = int.from_bytes(digest[2:4], "big") / 65535 * math.tau
    center_x, center_y = MAP_CENTER
    points: list[tuple[float, float]] = []

    for index, intensity in enumerate(activity):
        angle = -math.pi / 2 + math.tau * index / BIN_COUNT
        signature = (
            4.5 * math.sin(angle * 3 + phase_a)
            + 2.8 * math.sin(angle * 7 + phase_b)
        )
        radius = (
            136 * scale
            + 46 * intensity * (0.62 + 0.38 * scale)
            + signature * scale
        )
        points.append(
            (
                center_x + math.cos(angle) * radius * 1.34,
                center_y + math.sin(angle) * radius * 0.84,
            )
        )
    return points


def closed_curve(points: list[tuple[float, float]]) -> str:
    commands = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    count = len(points)
    for index in range(count):
        previous = points[(index - 1) % count]
        current = points[index]
        following = points[(index + 1) % count]
        after = points[(index + 2) % count]
        control_1 = (
            current[0] + (following[0] - previous[0]) / 6,
            current[1] + (following[1] - previous[1]) / 6,
        )
        control_2 = (
            following[0] - (after[0] - current[0]) / 6,
            following[1] - (after[1] - current[1]) / 6,
        )
        commands.append(
            f"C {control_1[0]:.1f} {control_1[1]:.1f} "
            f"{control_2[0]:.1f} {control_2[1]:.1f} "
            f"{following[0]:.1f} {following[1]:.1f}"
        )
    commands.append("Z")
    return " ".join(commands)


def month_markers(
    days: list[dict[str, object]], outer_points: list[tuple[float, float]]
) -> tuple[list[str], list[str]]:
    starts: list[tuple[int, date]] = []
    previous_month = ""
    for index, item in enumerate(days):
        current = date.fromisoformat(str(item["date"]))
        key = current.strftime("%Y-%m")
        if key != previous_month:
            starts.append((index, current))
            previous_month = key

    starts = starts[-12:]
    groups: list[str] = []
    css: list[str] = []
    center_x, center_y = MAP_CENTER

    for marker_index, (day_index, current) in enumerate(starts):
        point_index = round(day_index * (BIN_COUNT - 1) / max(1, len(days) - 1))
        point_x, point_y = outer_points[point_index]
        vector_x = point_x - center_x
        vector_y = point_y - center_y
        length = math.hypot(vector_x, vector_y)
        unit_x = vector_x / length
        unit_y = vector_y / length
        tick_x = point_x + unit_x * 10
        tick_y = point_y + unit_y * 10
        label_x = point_x + unit_x * 21
        label_y = point_y + unit_y * 21 + 3
        anchor = "start" if unit_x > 0.25 else "end" if unit_x < -0.25 else "middle"
        label = MONTHS[current.month - 1]

        groups.append(
            f"""  <g class="month month-{marker_index}">
    <line x1="{point_x:.1f}" y1="{point_y:.1f}" x2="{tick_x:.1f}" y2="{tick_y:.1f}" />
    <text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="{anchor}">{label}</text>
  </g>"""
        )
        css.append(
            f"    .month-{marker_index} {{ animation-delay: "
            f"{1.05 + marker_index * 0.045:.3f}s; }}"
        )

    return groups, css


def crop_marks() -> str:
    return """
  <path class="crop" d="M12 27 V12 H27 M833 12 H848 V27
    M12 473 V488 H27 M833 488 H848 V473" />"""


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    profile = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    days = payload["days"]
    stats = payload["stats"]
    username = str(profile["username"])
    activity = aggregate_activity(days)

    scales = [1.0, 0.87, 0.74, 0.61, 0.48, 0.35]
    contour_points = [
        terrain_points(activity, username, scale) for scale in scales
    ]
    contour_paths = [closed_curve(points) for points in contour_points]
    outer_points = contour_points[0]
    marker_groups, marker_css = month_markers(days, outer_points)

    contour_elements: list[str] = []
    contour_css: list[str] = []
    for index, path in enumerate(contour_paths):
        contour_elements.append(
            f'  <path class="contour contour-{index}" pathLength="1" d="{path}" />'
        )
        contour_css.append(
            f"    .contour-{index} {{ animation-delay: {0.18 + index * 0.12:.2f}s; }}"
        )

    best_day = stats["best_day"]
    peak_date = date.fromisoformat(str(best_day["date"]))
    peak_day_index = next(
        index for index, item in enumerate(days) if item["date"] == best_day["date"]
    )
    peak_point_index = round(
        peak_day_index * (BIN_COUNT - 1) / max(1, len(days) - 1)
    )
    peak_x, peak_y = outer_points[peak_point_index]
    center_x, center_y = MAP_CENTER
    peak_vector_x = peak_x - center_x
    peak_vector_y = peak_y - center_y
    peak_length = math.hypot(peak_vector_x, peak_vector_y)
    peak_unit_x = peak_vector_x / peak_length
    peak_unit_y = peak_vector_y / peak_length
    peak_label_x = peak_x + peak_unit_x * 18
    peak_label_y = peak_y + peak_unit_y * 18 - 6
    peak_anchor = (
        "start" if peak_unit_x > 0.15 else "end" if peak_unit_x < -0.15 else "middle"
    )

    total = int(stats["total"])
    longest = int(stats["longest_streak"])
    best_count = int(best_day["count"])
    range_from = date.fromisoformat(str(payload["range"]["from"]))
    range_to = date.fromisoformat(str(payload["range"]["to"]))
    date_range = f"{range_from:%Y.%m}—{range_to:%Y.%m}"
    best_label = f"{best_count} / {peak_date.day:02d} {MONTHS[peak_date.month - 1]}"

    description = (
        f"A generated topographic portrait of {username}'s {len(days)} daily "
        f"GitHub contribution samples. {total} contributions shape the terrain; "
        f"the peak is {best_count} on {peak_date.isoformat()}."
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
  viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title description">
  <title id="title">C0DSE Systems Atlas</title>
  <desc id="description">{escape(description)}</desc>
  <style>
    .display {{
      font-family: Georgia, "Times New Roman", serif;
      fill: {INK};
    }}
    .mono {{
      font-family: "Courier New", ui-monospace, monospace;
      fill: {INK};
    }}
    .kicker {{
      font-family: "Courier New", ui-monospace, monospace;
      font-size: 9px;
      letter-spacing: 2.1px;
      fill: {SAGE};
    }}
    .label {{
      font-family: "Courier New", ui-monospace, monospace;
      font-size: 8px;
      letter-spacing: 1.4px;
      fill: {SAGE};
    }}
    .value {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 13px;
      fill: {INK};
    }}
    .atlas-fill {{
      opacity: .18;
      animation: terrain-in .8s cubic-bezier(.16,1,.3,1) forwards;
    }}
    .contour {{
      fill: none;
      stroke: {SAGE};
      stroke-width: 1.1;
      vector-effect: non-scaling-stroke;
      stroke-dasharray: 1;
      stroke-dashoffset: 1;
      animation: draw 1.35s cubic-bezier(.16,1,.3,1) forwards;
    }}
    .contour-0 {{ stroke: {INK}; stroke-width: 1.6; }}
{chr(10).join(contour_css)}
    .month {{
      opacity: 0;
      animation: settle .48s cubic-bezier(.16,1,.3,1) forwards;
    }}
    .month line {{ stroke: {INK}; stroke-width: .8; }}
    .month text {{
      font-family: "Courier New", ui-monospace, monospace;
      font-size: 8px;
      letter-spacing: 1px;
      fill: {INK};
    }}
{chr(10).join(marker_css)}
    .peak-beam {{
      stroke: {ORANGE};
      stroke-width: 1.4;
      stroke-dasharray: 1;
      stroke-dashoffset: 1;
      animation: draw .8s cubic-bezier(.16,1,.3,1) 1.72s forwards;
    }}
    .peak {{
      opacity: 0;
      animation: peak-in .5s cubic-bezier(.34,1.56,.64,1) 2.15s forwards;
    }}
    .metadata {{
      opacity: 0;
      animation: settle .65s cubic-bezier(.16,1,.3,1) 2.35s forwards;
    }}
    .crop {{ fill: none; stroke: {INK}; stroke-width: 1; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    @keyframes terrain-in {{ to {{ opacity: .72; }} }}
    @keyframes settle {{
      from {{ opacity: 0; transform: translateY(7px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes peak-in {{
      from {{ opacity: 0; transform: scale(.35); }}
      to {{ opacity: 1; transform: scale(1); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .atlas-fill, .contour, .month, .peak-beam, .peak, .metadata {{
        animation: none;
        opacity: 1;
        transform: none;
        stroke-dashoffset: 0;
      }}
      .atlas-fill {{ opacity: .72; }}
    }}
  </style>

  <rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}" />
  <rect x="1" y="1" width="{WIDTH - 2}" height="{HEIGHT - 2}"
    fill="none" stroke="{INK}" stroke-width="1" />
{crop_marks()}

  <g aria-hidden="true" opacity=".42">
    <path d="M42 84 H578 M42 164 H578 M42 244 H578 M42 324 H578 M42 404 H578"
      stroke="{GRID}" stroke-width=".7" stroke-dasharray="2 5" />
    <path d="M62 76 V422 M182 76 V422 M302 76 V422 M422 76 V422 M542 76 V422"
      stroke="{GRID}" stroke-width=".7" stroke-dasharray="2 5" />
  </g>

  <text class="display" x="30" y="38" font-size="29" font-weight="700">C0DSE</text>
  <text class="kicker" x="151" y="34">SYSTEMS ATLAS</text>
  <text class="mono" x="151" y="53" font-size="9" fill="{INK}">
    DAILY CONTRIBUTION TERRAIN / {date_range}
  </text>
  <text class="kicker" x="830" y="34" text-anchor="end">51.97 N · 5.67 E</text>
  <text class="mono" x="830" y="53" text-anchor="end" font-size="9">
    SHEET WG-{hashlib.sha1(username.encode()).hexdigest()[:4].upper()}
  </text>

  <line x1="610" y1="78" x2="610" y2="420" stroke="{INK}" stroke-width="1" />

  <path class="atlas-fill" d="{contour_paths[0]}" fill="{SAGE_LIGHT}" />
{chr(10).join(contour_elements)}
{chr(10).join(marker_groups)}

  <g aria-label="Origin: Wageningen">
    <circle cx="{center_x:.1f}" cy="{center_y:.1f}" r="7"
      fill="{PAPER_LIGHT}" stroke="{INK}" />
    <circle cx="{center_x:.1f}" cy="{center_y:.1f}" r="2.5" fill="{ORANGE}" />
    <path d="M{center_x - 12:.1f} {center_y:.1f} H{center_x + 12:.1f}
      M{center_x:.1f} {center_y - 12:.1f} V{center_y + 12:.1f}"
      stroke="{INK}" stroke-width=".7" />
    <text class="label" x="{center_x + 13:.1f}" y="{center_y - 10:.1f}">
      ORIGIN / WAGENINGEN
    </text>
  </g>

  <line class="peak-beam" pathLength="1" x1="{center_x:.1f}" y1="{center_y:.1f}"
    x2="{peak_x:.1f}" y2="{peak_y:.1f}" />
  <g class="peak" transform-origin="{peak_x:.1f}px {peak_y:.1f}px">
    <circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="5.5"
      fill="{PAPER}" stroke="{ORANGE}" stroke-width="2" />
    <circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="2" fill="{ORANGE}" />
    <text class="mono" x="{peak_label_x:.1f}" y="{peak_label_y:.1f}"
      text-anchor="{peak_anchor}" font-size="8" fill="{ORANGE}">
      PEAK · {best_label}
    </text>
  </g>

  <g class="metadata">
    <text class="label" x="640" y="98">OPERATOR</text>
    <text class="display" x="640" y="127" font-size="25" font-style="italic">
      {escape(username)}
    </text>
    <line x1="640" y1="143" x2="830" y2="143" stroke="{GRID}" />

    <text class="label" x="640" y="169">ROLE</text>
    <text class="value" x="640" y="190">{escape(str(profile["role"]))}</text>
    <text class="mono" x="640" y="206" font-size="9">{escape(str(profile["company"]))}</text>

    <text class="label" x="640" y="235">FIELD</text>
    <text class="value" x="640" y="256">{escape(str(profile["focus"]))}</text>

    <text class="label" x="640" y="285">SYSTEMS</text>
    <text class="value" x="640" y="306">{escape(str(profile["stack"]))}</text>
    <text class="mono" x="640" y="323" font-size="9">{escape(str(profile["data"]))}</text>

    <text class="label" x="640" y="351">TOOLS</text>
    <text class="value" x="640" y="372">{escape(str(profile["tools"]))}</text>

    <text class="label" x="640" y="400">BASE</text>
    <text class="mono" x="640" y="417" font-size="10">{escape(str(profile["location"]))}</text>

    <line x1="24" y1="440" x2="836" y2="440" stroke="{INK}" />

    <text class="label" x="30" y="460">SAMPLE</text>
    <text class="value" x="30" y="482">{len(days)} daily samples</text>

    <text class="label" x="232" y="460">SIGNAL</text>
    <text class="value" x="232" y="482">{total:,} contributions</text>

    <text class="label" x="438" y="460">RIDGE</text>
    <text class="value" x="438" y="482">{longest} day best streak</text>

    <text class="label" x="650" y="460">PEAK</text>
    <text class="value" x="650" y="482">{best_label}</text>
  </g>
</svg>
"""
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH.name}: {len(days)} samples, "
        f"{total} contribution signals."
    )


if __name__ == "__main__":
    main()
