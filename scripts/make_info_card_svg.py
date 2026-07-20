"""Generate the animated neofetch-style profile information card."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "profile.json"
OUTPUT_PATH = ROOT / "info-card.svg"

WIDTH = 500
HEIGHT = 360


def main() -> None:
    profile = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    username = str(profile["username"])
    rows = [
        ("role", profile["role"], "#58a6ff"),
        ("company", profile["company"], "#7ee787"),
        ("base", profile["location"], "#d2a8ff"),
        ("focus", profile["focus"], "#f2cc60"),
        ("stack", profile["stack"], "#58a6ff"),
        ("data", profile["data"], "#7ee787"),
        ("tools", profile["tools"], "#d2a8ff"),
        ("status", profile["status"], "#f2cc60"),
    ]

    row_groups: list[str] = []
    for index, (key, value, color) in enumerate(rows):
        y = 92 + index * 31
        begin = 0.22 + index * 0.13
        row_groups.append(
            f"""  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1"
      begin="{begin:.2f}s" dur=".28s" fill="freeze" />
    <animateTransform attributeName="transform" type="translate"
      from="0 7" to="0 0" begin="{begin:.2f}s" dur=".28s" fill="freeze" />
    <text class="key" x="28" y="{y}">{escape(str(key))}</text>
    <text class="separator" x="101" y="{y}">:</text>
    <text x="119" y="{y}" fill="{color}">{escape(str(value))}</text>
  </g>"""
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
  viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title description">
  <title id="title">{escape(username)} profile information</title>
  <desc id="description">
    {escape(str(profile["role"]))} at {escape(str(profile["company"]))},
    based in {escape(str(profile["location"]))}. Focused on
    {escape(str(profile["focus"]))}.
  </desc>
  <style>
    text {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
        "Liberation Mono", "Courier New", monospace;
      font-size: 12px;
    }}
    .heading {{ fill: #f0f6fc; font-size: 14px; font-weight: 600; }}
    .key {{ fill: #8b949e; }}
    .separator {{ fill: #484f58; }}
    @media (prefers-reduced-motion: reduce) {{
      g {{ opacity: 1; transform: none; }}
    }}
  </style>

  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14"
    fill="#0d1117" stroke="#30363d" />
  <circle cx="19" cy="20" r="4" fill="#ff7b72" />
  <circle cx="32" cy="20" r="4" fill="#d29922" />
  <circle cx="45" cy="20" r="4" fill="#3fb950" />
  <text class="heading" x="64" y="25">
    <tspan fill="#7ee787">{escape(username)}</tspan><tspan fill="#8b949e">@github</tspan>
    <tspan fill="#58a6ff"> ~ $ whoami</tspan>
  </text>
  <line x1="1" y1="40" x2="{WIDTH - 1}" y2="40" stroke="#21262d" />

  <text x="28" y="61" fill="#484f58">---------------------------------------------</text>

{chr(10).join(row_groups)}

  <g opacity=".3" aria-hidden="true">
    <path d="M420 270 h34 v34 h-34 z M437 253 v68 M403 287 h68"
      fill="none" stroke="#238636" />
    <circle cx="437" cy="287" r="24" fill="none" stroke="#1f6feb" />
    <circle cx="437" cy="287" r="4" fill="#7ee787" />
  </g>
</svg>
"""
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.name}.")


if __name__ == "__main__":
    main()
