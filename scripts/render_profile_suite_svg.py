"""Render the static, GitHub-native panels used on the c0dse profile."""

from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSIGHTS_PATH = ROOT / "data" / "insights.json"
PROFILE_PATH = ROOT / "profile.json"
WORK_LEDGER_PATH = ROOT / "work-ledger.svg"
OPERATING_CONTEXT_PATH = ROOT / "operating-context.svg"

WIDTH = 860

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
    .eyebrow { fill: var(--muted); font-size: 10px; font-weight: 600; letter-spacing: 1px; }
    .title { font-size: 26px; font-weight: 650; letter-spacing: -.5px; }
    .subtitle { fill: var(--muted); font-size: 12px; }
    .section-title { font-size: 12px; font-weight: 650; letter-spacing: .5px; }
    .label { fill: var(--muted); font-size: 10px; font-weight: 600; letter-spacing: .65px; }
    .body { font-size: 13px; }
    .value { font-size: 18px; font-weight: 650; }
    .big-value { font-size: 38px; font-weight: 650; letter-spacing: -1px; }
    .small { fill: var(--muted); font-size: 10px; }
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


def delta_label(current: int, previous: int) -> str:
    delta = current - previous
    if delta == 0:
        return "EVEN VS PRIOR"
    return f"{delta:+d} VS PRIOR"


def percentage_shares(values: dict[str, int]) -> dict[str, int]:
    """Return stable integer shares that add up to exactly 100 when non-zero."""
    total = sum(values.values())
    if total == 0:
        return {key: 0 for key in values}

    shares = {key: value * 100 // total for key, value in values.items()}
    remaining = 100 - sum(shares.values())
    order = sorted(
        values,
        key=lambda key: (-(values[key] * 100 % total), list(values).index(key)),
    )
    for key in order[:remaining]:
        shares[key] += 1
    return shares


def svg_shell(height: int, title: str, description: str, content: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}"
  viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(description)}</desc>
  <style>{THEME_CSS}
  </style>
  <rect class="canvas" width="{WIDTH}" height="{height}" rx="6" />
  <rect class="frame" x=".5" y=".5" width="{WIDTH - 1}" height="{height - 1}" rx="6" />
{content}
</svg>
"""


def render_composition_rail(values: list[tuple[str, int]]) -> str:
    x = 28.0
    y = 124.0
    width = 516.0
    height = 14.0
    total = sum(value for _, value in values)
    parts = [
        f'  <rect class="surface" x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="3" />'
    ]
    cursor = x
    class_by_key = {
        "commit_contributions": "green",
        "pull_requests_opened": "blue",
        "issues_opened": "orange",
        "reviews_submitted": "surface",
    }
    if total:
        non_zero = [(key, value) for key, value in values if value]
        for index, (key, value) in enumerate(non_zero):
            segment_width = width * value / total
            radius = 3 if index in {0, len(non_zero) - 1} else 0
            parts.append(
                f'  <rect class="{class_by_key[key]}" x="{cursor:.1f}" y="{y:.1f}" '
                f'width="{segment_width:.1f}" height="{height:.1f}" rx="{radius}" />'
            )
            cursor += segment_width
    return "\n".join(parts)


def render_work_ledger(payload: dict[str, Any], username: str) -> str:
    current = payload["work_mix"]["current"]
    previous = payload["work_mix"]["previous"]
    shipping = payload["shipping_pulse"]["current"]
    shipping_previous = payload["shipping_pulse"]["previous"]
    total = sum(current.values())
    shares = percentage_shares(current)

    mix_rows = (
        ("commit_contributions", "COMMITS", "green"),
        ("pull_requests_opened", "PRS OPENED", "blue"),
        ("issues_opened", "ISSUES OPENED", "orange"),
        ("reviews_submitted", "REVIEW CONTRIBUTIONS", ""),
    )
    rows: list[str] = []
    for index, (key, label, color_class) in enumerate(mix_rows):
        y = 187 + index * 40
        share = shares[key]
        swatch_class = color_class or "surface"
        value_class = f" {color_class}" if color_class else ""
        rows.extend(
            [
                f'  <circle class="{swatch_class}" cx="33" cy="{y - 4}" r="4" />',
                f'  <text class="label mono" x="46" y="{y}">{label}</text>',
                f'  <text class="value{value_class}" x="303" y="{y}" text-anchor="end">{current[key]}</text>',
                f'  <text class="body mono" x="361" y="{y}" text-anchor="end">{share}%</text>',
                f'  <text class="small mono" x="544" y="{y}" text-anchor="end">{delta_label(current[key], previous[key])}</text>',
            ]
        )
        if index < len(mix_rows) - 1:
            rows.append(f'  <line class="divider" x1="28" y1="{y + 15}" x2="544" y2="{y + 15}" />')

    metric_specs = (
        ("pull_requests_merged", "MERGED PRS", 594, 157, "green"),
        ("authored_issues_closed", "AUTHORED ISSUES", 731, 157, "blue"),
        ("repositories_with_commits", "REPOS WITH COMMITS", 594, 267, "orange"),
        ("active_days", "ACTIVE DAYS", 731, 267, ""),
    )
    metrics: list[str] = []
    for key, label, x, y, color_class in metric_specs:
        value_class = f" {color_class}" if color_class else ""
        metrics.extend(
            [
                f'  <text class="big-value{value_class}" x="{x}" y="{y}">{shipping[key]}</text>',
                f'  <text class="label mono" x="{x}" y="{y + 21}">{label}</text>',
                f'  <text class="small mono" x="{x}" y="{y + 50}">{delta_label(shipping[key], shipping_previous[key])}</text>',
            ]
        )
    # Clarify the longer label without shrinking the whole metric system.
    metrics.append('  <text class="small mono" x="731" y="190">CLOSED IN WINDOW</text>')
    metrics.append('  <text class="small mono" x="731" y="300">PUBLIC CALENDAR</text>')

    content = f"""  <text class="title mono" x="28" y="38">{escape(username)}</text>
  <text class="eyebrow mono" x="127" y="34">/ WORK LEDGER</text>
  <text class="subtitle" x="28" y="61">What the work contains, and what moved to done.</text>
  <text class="eyebrow mono" x="832" y="34" text-anchor="end">90-DAY SNAPSHOT</text>
  <text class="subtitle mono" x="832" y="58" text-anchor="end">AS OF {display_date(payload['generated_on'])}</text>
  <line class="divider" x1="1" y1="78" x2="859" y2="78" />

  <text class="section-title mono" x="28" y="105">WORK MIX</text>
  <text class="small mono" x="544" y="105" text-anchor="end">CURRENT 90 DAYS / COMPARED WITH PRIOR 90 DAYS</text>
{render_composition_rail(list(current.items()))}
  <text class="label mono" x="46" y="159">CONTRIBUTION TYPE</text>
  <text class="label mono" x="303" y="159" text-anchor="end">COUNT</text>
  <text class="label mono" x="361" y="159" text-anchor="end">MIX</text>
  <text class="label mono" x="544" y="159" text-anchor="end">CHANGE</text>
{chr(10).join(rows)}

  <line class="divider" x1="570" y1="96" x2="570" y2="331" />
  <text class="section-title mono" x="594" y="105">SHIPPING PULSE</text>
  <text class="small mono" x="832" y="105" text-anchor="end">COMPLETION + BREADTH</text>
  <line class="divider" x1="712" y1="122" x2="712" y2="321" />
  <line class="divider" x1="594" y1="220" x2="832" y2="220" />
{chr(10).join(metrics)}

  <line class="divider" x1="1" y1="332" x2="859" y2="332" />
  <text class="small mono" x="28" y="354">AGGREGATED ACTIVITY / REPOSITORY NAMES AND WORK-ITEM DETAILS OMITTED</text>
  <text class="small mono" x="832" y="354" text-anchor="end">COUNTS FOLLOW GITHUB'S CONTRIBUTION DEFINITIONS</text>"""

    return svg_shell(
        370,
        f"{username} work ledger",
        (
            "An anonymous 90-day summary of commit, pull request, issue and review "
            "contributions, plus merged pull requests, authored issues closed, "
            "repositories with commits and active days."
        ),
        content,
    )


def render_operating_context(profile: dict[str, Any]) -> str:
    current_focus = profile["current_focus"]
    tech_footprint = profile["tech_footprint"]
    if len(current_focus) != 3 or len(tech_footprint) != 4:
        raise ValueError("Operating Context expects 3 focus rows and 4 technology rows")

    focus_rows: list[str] = []
    for index, row in enumerate(current_focus):
        y = 153 + index * 61
        focus_rows.extend(
            [
                f'  <text class="label mono" x="28" y="{y - 19}">{escape(str(row["label"]))}</text>',
                f'  <text class="value" x="28" y="{y + 5}">{escape(str(row["value"]))}</text>',
            ]
        )
        if index < len(current_focus) - 1:
            focus_rows.append(f'  <line class="divider" x1="28" y1="{y + 21}" x2="402" y2="{y + 21}" />')

    tech_rows: list[str] = []
    for index, row in enumerate(tech_footprint):
        y = 144 + index * 44
        tech_rows.extend(
            [
                f'  <text class="label mono" x="458" y="{y}">{escape(str(row["label"]))}</text>',
                f'  <text class="value" x="832" y="{y}" text-anchor="end">{escape(str(row["value"]))}</text>',
            ]
        )
        if index < len(tech_footprint) - 1:
            tech_rows.append(f'  <line class="divider" x1="458" y1="{y + 15}" x2="832" y2="{y + 15}" />')

    identity = f'{profile["role"]} @ {profile["company"]} / {profile["location"]}'
    content = f"""  <text class="title mono" x="28" y="38">{escape(str(profile['username']))}</text>
  <text class="eyebrow mono" x="127" y="34">/ OPERATING CONTEXT</text>
  <text class="subtitle" x="28" y="61">{escape(identity)}</text>
  <text class="eyebrow mono" x="832" y="34" text-anchor="end">NOW / CAPABILITIES</text>
  <text class="subtitle mono" x="832" y="58" text-anchor="end">A READABLE MAP, NOT A LOGO WALL</text>
  <line class="divider" x1="1" y1="78" x2="859" y2="78" />

  <text class="section-title mono" x="28" y="107">CURRENT FOCUS</text>
{chr(10).join(focus_rows)}

  <line class="divider" x1="430" y1="96" x2="430" y2="296" />
  <text class="section-title mono" x="458" y="107">TECH FOOTPRINT</text>
{chr(10).join(tech_rows)}

  <line class="divider" x1="1" y1="297" x2="859" y2="297" />
  <text class="small mono" x="28" y="317">FOCUS DESCRIBES THE WORK / TOOLS DESCRIBE THE APPROACH</text>
  <text class="small mono" x="832" y="317" text-anchor="end">EDITABLE IN PROFILE.JSON</text>"""

    return svg_shell(
        330,
        f"{profile['username']} operating context",
        (
            f"{profile['username']}'s current engineering focus and technical footprint, "
            "including backend, spatial data, automation and AI-assisted workflows."
        ),
        content,
    )


def main() -> None:
    insights = load_json(INSIGHTS_PATH)
    profile = load_json(PROFILE_PATH)
    validate_insights(insights)

    work_ledger = render_work_ledger(insights, str(profile["username"]))
    operating_context = render_operating_context(profile)
    WORK_LEDGER_PATH.write_text(work_ledger, encoding="utf-8")
    OPERATING_CONTEXT_PATH.write_text(operating_context, encoding="utf-8")
    print(
        f"Wrote {WORK_LEDGER_PATH.name} and {OPERATING_CONTEXT_PATH.name} "
        f"from privacy-safe aggregate data."
    )


if __name__ == "__main__":
    main()
