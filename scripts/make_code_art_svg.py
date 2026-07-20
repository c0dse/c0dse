"""Generate the animated terminal artwork shown beside the profile card."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "profile.json"
OUTPUT_PATH = ROOT / "code-art.svg"

WIDTH = 350
HEIGHT = 360


def main() -> None:
    profile = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    username = str(profile["username"])
    location = str(profile["location"]).upper()

    lines = [
        ("> locate --user", "#7ee787", 11),
        (username, "#58a6ff", 20),
        (location, "#8b949e", 10),
        ("", "#c9d1d9", 10),
        ("", "#c9d1d9", 10),
        ("", "#c9d1d9", 10),
        ("", "#c9d1d9", 10),
        ("", "#c9d1d9", 10),
        ("[backend] [web] [geo]", "#d2a8ff", 10),
        ("> systems online", "#7ee787", 11),
    ]

    baseline = 78
    line_height = 21
    clip_defs: list[str] = []
    text_rows: list[str] = []

    for index, (content, color, font_size) in enumerate(lines):
        y = baseline + index * line_height
        duration = max(0.16, min(0.55, len(content) * 0.018))
        begin = 0.18 + index * 0.15
        clip_defs.append(
            f'    <clipPath id="row-{index}"><rect x="24" y="{y - 16}" '
            f'width="0" height="22"><animate attributeName="width" from="0" '
            f'to="302" begin="{begin:.2f}s" dur="{duration:.2f}s" '
            'fill="freeze" /></rect></clipPath>'
        )
        if content:
            text_rows.append(
                f'  <text x="27" y="{y}" fill="{color}" font-size="{font_size}" '
                'xml:space="preserve" '
                f'clip-path="url(#row-{index})">{escape(content)}</text>'
            )

    glyphs = [
        ("C", ["11111", "10000", "10000", "10000", "11111"], "#f0f6fc"),
        ("0", ["01110", "10001", "10011", "10101", "01110"], "#58a6ff"),
        ("D", ["11110", "10001", "10001", "10001", "11110"], "#f0f6fc"),
        ("S", ["11111", "10000", "11111", "00001", "11111"], "#7ee787"),
        ("E", ["11111", "10000", "11110", "10000", "11111"], "#f0f6fc"),
    ]
    logo_rows: list[str] = []
    for row in range(5):
        pixels: list[str] = []
        for glyph_index, (_, pattern, color) in enumerate(glyphs):
            for column, enabled in enumerate(pattern[row]):
                if enabled == "1":
                    x = 27 + glyph_index * 55 + column * 10
                    y = 157 + row * 10
                    pixels.append(
                        f'<rect x="{x}" y="{y}" width="7" height="7" '
                        f'rx="1.5" fill="{color}" />'
                    )
        begin = 0.76 + row * 0.11
        logo_rows.append(
            f'  <g opacity="0">{"".join(pixels)}'
            f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{begin:.2f}s" dur=".18s" fill="freeze" /></g>'
        )

    final_y = baseline + len(lines) * line_height + 1
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
  viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title description">
  <title id="title">Animated c0dse terminal artwork</title>
  <desc id="description">
    A terminal locates c0dse in Wageningen and prints the username in block letters.
  </desc>
  <defs>
{chr(10).join(clip_defs)}
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#58a6ff" />
      <stop offset="1" stop-color="#7ee787" />
    </linearGradient>
  </defs>
  <style>
    text {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
        "Liberation Mono", "Courier New", monospace;
    }}
    .grid {{ stroke: #161b22; stroke-width: 1; }}
  </style>

  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14"
    fill="#0d1117" stroke="#30363d" />
  <path d="M14 1 H336 Q349 1 349 14 V58" fill="none"
    stroke="url(#edge)" stroke-width="1.5" opacity=".8" />

  <circle cx="19" cy="20" r="4" fill="#ff7b72" />
  <circle cx="32" cy="20" r="4" fill="#d29922" />
  <circle cx="45" cy="20" r="4" fill="#3fb950" />
  <text x="64" y="25" fill="#8b949e" font-size="11">geo-terminal</text>
  <line x1="1" y1="40" x2="349" y2="40" stroke="#21262d" />

  <g opacity=".32" aria-hidden="true">
    <path class="grid" d="M264 49 V340 M292 49 V340 M320 49 V340" />
    <path class="grid" d="M250 70 H339 M250 98 H339 M250 126 H339" />
    <circle cx="294" cy="98" r="22" fill="none" stroke="#1f6feb" opacity=".45" />
    <path d="M294 68 V128 M264 98 H324" stroke="#238636" opacity=".6" />
  </g>

{chr(10).join(logo_rows)}

{chr(10).join(text_rows)}

  <rect x="27" y="{final_y - 12}" width="8" height="14" rx="1" fill="#7ee787">
    <animate attributeName="opacity" values="1;0;1;0;1"
      begin="2.1s" dur="1.1s" fill="freeze" />
  </rect>
</svg>
"""
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.name}.")


if __name__ == "__main__":
    main()
