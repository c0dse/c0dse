"""Render compact, privacy-safe profile statistics for desktop and mobile."""

from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSIGHTS_PATH = ROOT / "data" / "insights.json"
WORK_MIX_PATH = ROOT / "work-mix.svg"
SHIPPING_PULSE_PATH = ROOT / "shipping-pulse.svg"

WIDTH = 360
HEIGHT = 336

THEME_CSS = """
    :root {
      color-scheme: light dark;
      --canvas: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #f0f6fc; --muted: #8b949e; --green: #3fb950;
      --blue: #58a6ff; --orange: #d29922;
    }
    @media (prefers-color-scheme: light) {
      :root {
        --canvas: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
        --text: #1f2328; --muted: #59636e; --green: #1f883d;
        --blue: #0969da; --orange: #9a6700;
      }
    }
    text {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      fill: var(--text); text-rendering: geometricPrecision;
    }
    .mono { font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }
    .canvas { fill: var(--canvas); }
    .surface { fill: var(--surface); }
    .frame { fill: none; stroke: var(--border); }
    .divider { stroke: var(--border); stroke-width: 1; }
    .eyebrow { fill: var(--muted); font-size: 10px; font-weight: 650; letter-spacing: .8px; }
    .panel-title { font-size: 21px; font-weight: 650; letter-spacing: -.35px; }
    .subtitle { fill: var(--muted); font-size: 11px; }
    .label { fill: var(--muted); font-size: 9.5px; font-weight: 650; letter-spacing: .45px; }
    .row-value { font-size: 16px; font-weight: 650; }
    .body { font-size: 12px; }
    .big-value { font-size: 38px; font-weight: 650; letter-spacing: -1px; }
    .small { fill: var(--muted); font-size: 9.5px; }
    .green { fill: var(--green); }
    .blue { fill: var(--blue); }
    .orange { fill: var(--orange); }
"""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"Invalid keys at {path}: missing={missing}, extra={extra}")


def require_non_negative_counts(value: dict[str, Any], path: str) -> None:
    for key, count in value.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"{path}.{key} must be a non-negative integer")


def validate_insights(payload: dict[str, Any]) -> None:
    require_exact_keys(
        payload,
        {
            "schema_version",
            "generated_on",
            "window",
            "previous_window",
            "work_mix",
            "shipping_pulse",
        },
        "insights",
    )
    if payload["schema_version"] != 1:
        raise ValueError("Unsupported insights schema")

    for key in ("window", "previous_window"):
        window = payload[key]
        require_exact_keys(window, {"from", "to", "days"}, key)
        start = date.fromisoformat(window["from"])
        end = date.fromisoformat(window["to"])
        if window["days"] != (end - start).days + 1:
            raise ValueError(f"{key}.days does not match its inclusive date range")

    work_keys = {
        "commit_contributions",
        "pull_requests_opened",
        "issues_opened",
        "reviews_submitted",
    }
    shipping_keys = {
        "pull_requests_merged",
        "authored_issues_closed",
        "repositories_with_commits",
        "active_days",
    }
    for section_name, expected in (
        ("work_mix", work_keys),
        ("shipping_pulse", shipping_keys),
    ):
        section = payload[section_name]
        require_exact_keys(section, {"current", "previous"}, section_name)
        for period in ("current", "previous"):
            require_exact_keys(section[period], expected, f"{section_name}.{period}")
            require_non_negative_counts(section[period], f"{section_name}.{period}")

    generated_on = date.fromisoformat(payload["generated_on"])
    if generated_on != date.fromisoformat(payload["window"]["to"]):
        raise ValueError("generated_on must equal the current window end date")


def display_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return parsed.strftime("%d %b %Y").upper().lstrip("0")


def percentage_shares(values: dict[str, int]) -> dict[str, int]:
    """Return stable integer shares that total exactly 100 when activity exists."""
    total = sum(values.values())
    if total == 0:
        return {key: 0 for key in values}

    shares = {key: value * 100 // total for key, value in values.items()}
    remaining = 100 - sum(shares.values())
    positions = {key: index for index, key in enumerate(values)}
    order = sorted(
        values,
        key=lambda key: (-(values[key] * 100 % total), positions[key]),
    )
    for key in order[:remaining]:
        shares[key] += 1
    return shares


def compact_delta(current: int, previous: int, suffix: bool = False) -> str:
    delta = current - previous
    value = "EVEN" if delta == 0 else f"{delta:+d}"
    return f"{value} vs prior" if suffix else value


def panel_shell(title: str, description: str, content: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
  viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(description)}</desc>
  <style>{THEME_CSS}
  </style>
  <rect class="canvas" width="{WIDTH}" height="{HEIGHT}" rx="6" />
  <rect class="frame" x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="6" />
{content}
</svg>
"""


def composition_rail(current: dict[str, int]) -> str:
    x = 20.0
    y = 108.0
    width = 320.0
    height = 12.0
    total = sum(current.values())
    class_by_key = {
        "commit_contributions": "green",
        "pull_requests_opened": "blue",
        "issues_opened": "orange",
        "reviews_submitted": "surface",
    }
    parts = [
        f'  <rect class="surface" x="{x}" y="{y}" width="{width}" height="{height}" rx="3" />'
    ]
    if not total:
        return "\n".join(parts)

    non_zero = [(key, value) for key, value in current.items() if value]
    cursor = x
    for index, (key, value) in enumerate(non_zero):
        segment_width = width * value / total
        radius = 3 if index in {0, len(non_zero) - 1} else 0
        parts.append(
            f'  <rect class="{class_by_key[key]}" x="{cursor:.1f}" y="{y}" '
            f'width="{segment_width:.1f}" height="{height}" rx="{radius}" />'
        )
        cursor += segment_width
    return "\n".join(parts)


def render_work_mix(payload: dict[str, Any]) -> str:
    current = payload["work_mix"]["current"]
    previous = payload["work_mix"]["previous"]
    shares = percentage_shares(current)
    total = sum(current.values())
    rows = (
        ("commit_contributions", "COMMITS", "green"),
        ("pull_requests_opened", "PRS OPENED", "blue"),
        ("issues_opened", "ISSUES OPENED", "orange"),
        ("reviews_submitted", "REVIEW CONTRIBUTIONS", ""),
    )
    row_markup: list[str] = []
    for index, (key, label, color_class) in enumerate(rows):
        y = 174 + index * 35
        swatch = color_class or "surface"
        value_class = f" {color_class}" if color_class else ""
        row_markup.extend(
            [
                f'  <circle class="{swatch}" cx="24" cy="{y - 4}" r="3.5" />',
                f'  <text class="label mono" x="34" y="{y}">{label}</text>',
                f'  <text class="row-value{value_class}" x="230" y="{y}" text-anchor="end">{current[key]}</text>',
                f'  <text class="body mono" x="282" y="{y}" text-anchor="end">{shares[key]}%</text>',
                f'  <text class="small mono" x="340" y="{y}" text-anchor="end">{compact_delta(current[key], previous[key])}</text>',
            ]
        )
        if index < len(rows) - 1:
            row_markup.append(
                f'  <line class="divider" x1="20" y1="{y + 14}" x2="340" y2="{y + 14}" />'
            )

    content = f"""  <text class="eyebrow mono" x="20" y="23">LAST 90 DAYS</text>
  <text class="eyebrow mono" x="340" y="23" text-anchor="end">AS OF {display_date(payload['generated_on'])}</text>
  <text class="panel-title" x="20" y="51">Work mix</text>
  <text class="subtitle" x="20" y="70">GitHub-counted contribution types</text>
  <line class="divider" x1="1" y1="88" x2="359" y2="88" />

{composition_rail(current)}
  <text class="label mono" x="34" y="145">TYPE</text>
  <text class="label mono" x="230" y="145" text-anchor="end">COUNT</text>
  <text class="label mono" x="282" y="145" text-anchor="end">MIX</text>
  <text class="label mono" x="340" y="145" text-anchor="end">VS PRIOR</text>
{chr(10).join(row_markup)}

  <line class="divider" x1="1" y1="302" x2="359" y2="302" />
  <text class="small mono" x="20" y="323">ANONYMIZED TOTALS / {total} COUNTED ACTIONS</text>"""
    return panel_shell(
        "c0dse work mix",
        (
            "An anonymous 90-day composition of GitHub-counted commit, pull request, "
            "issue and review contributions, compared with the previous 90 days."
        ),
        content,
    )


def render_shipping_pulse(payload: dict[str, Any]) -> str:
    current = payload["shipping_pulse"]["current"]
    previous = payload["shipping_pulse"]["previous"]
    metrics = (
        ("pull_requests_merged", "MERGED PRS", "", 20, 143, "green"),
        (
            "authored_issues_closed",
            "AUTHORED ISSUES",
            "CLOSED IN WINDOW",
            198,
            143,
            "blue",
        ),
        (
            "repositories_with_commits",
            "REPOS WITH COMMITS",
            "",
            20,
            260,
            "orange",
        ),
        ("active_days", "ACTIVE DAYS", "PUBLIC CALENDAR", 198, 260, ""),
    )
    metric_markup: list[str] = []
    for key, label, note, x, y, color_class in metrics:
        value_class = f" {color_class}" if color_class else ""
        metric_markup.extend(
            [
                f'  <text class="big-value{value_class}" x="{x}" y="{y}">{current[key]}</text>',
                f'  <text class="label mono" x="{x}" y="{y + 23}">{label}</text>',
            ]
        )
        if note:
            metric_markup.append(
                f'  <text class="small mono" x="{x}" y="{y + 37}">{note}</text>'
            )
        metric_markup.append(
            f'  <text class="small mono" x="{x}" y="{y + 55}">{compact_delta(current[key], previous[key], suffix=True)}</text>'
        )

    content = f"""  <text class="eyebrow mono" x="20" y="23">LAST 90 DAYS</text>
  <text class="eyebrow mono" x="340" y="23" text-anchor="end">AS OF {display_date(payload['generated_on'])}</text>
  <text class="panel-title" x="20" y="51">Shipping pulse</text>
  <text class="subtitle" x="20" y="70">Anonymous totals / repository details omitted</text>
  <line class="divider" x1="1" y1="88" x2="359" y2="88" />

  <line class="divider" x1="180" y1="104" x2="180" y2="320" />
  <line class="divider" x1="20" y1="212" x2="340" y2="212" />
{chr(10).join(metric_markup)}"""
    return panel_shell(
        "c0dse shipping pulse",
        (
            "Anonymous 90-day totals for merged pull requests, authored issues closed, "
            "repositories with commit contributions and public active days."
        ),
        content,
    )


def main() -> None:
    insights = load_json(INSIGHTS_PATH)
    validate_insights(insights)
    WORK_MIX_PATH.write_text(render_work_mix(insights), encoding="utf-8")
    SHIPPING_PULSE_PATH.write_text(render_shipping_pulse(insights), encoding="utf-8")
    print(
        f"Wrote {WORK_MIX_PATH.name} and {SHIPPING_PULSE_PATH.name} "
        "from privacy-safe aggregate data."
    )


if __name__ == "__main__":
    main()
