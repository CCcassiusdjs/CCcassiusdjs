#!/usr/bin/env python3
"""Reproduce GitHub's native "Activity overview" radar as an embeddable SVG.

The real widget lives on the profile page and cannot be embedded in a README,
so this queries the same underlying data — `viewer.contributionsCollection` —
and draws it. Authenticating as the user is what makes private repositories and
organization work count: the collection already folds them into the totals.

One panel is drawn per scope. Organization scopes come from the organizationID
filter; the personal panel is whatever is left after subtracting them, so a new
organization membership is picked up without editing this file.

Requires GH_TOKEN with the `repo` and `read:org` scopes.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any, NamedTuple

API = "https://api.github.com/graphql"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
OUT_DIR = pathlib.Path(os.environ.get("OUT_DIR", "assets"))

# Axis order and placement mirror the native widget: code review on top,
# then clockwise. Keep them in this order — the geometry below depends on it.
AXES = ("Code review", "Issues", "Pull requests", "Commits")

FIELDS = {
    "Commits": "totalCommitContributions",
    "Pull requests": "totalPullRequestContributions",
    "Issues": "totalIssueContributions",
    "Code review": "totalPullRequestReviewContributions",
}


class Theme(NamedTuple):
    name: str
    background: str
    axis: str
    text: str
    muted: str
    accent: str
    fill: str


THEMES = (
    Theme("dark", "#0D1117", "#2EA043", "#E6EDF3", "#8B949E", "#3FB950", "#3FB95033"),
    Theme("light", "#FFFFFF", "#2DA44E", "#1F2328", "#656D76", "#1A7F37", "#1A7F3722"),
)


class Scope(NamedTuple):
    label: str
    totals: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.totals.values())


def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "cccassiusdjs-profile",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: dict[str, Any] = json.load(response)
    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


def windows(created: dt.datetime) -> list[tuple[str, str]]:
    """GitHub caps a contributions query at one year, so walk year by year."""
    spans: list[tuple[str, str]] = []
    now = dt.datetime.now(dt.timezone.utc)
    start = created
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        spans.append((start.isoformat().replace("+00:00", "Z"),
                      end.isoformat().replace("+00:00", "Z")))
        start = end
    return spans


def collect(spans: list[tuple[str, str]], organization_id: str | None) -> dict[str, int]:
    totals = {axis: 0 for axis in AXES}
    query = """
    query($from: DateTime!, $to: DateTime!, $org: ID) {
      viewer {
        contributionsCollection(from: $from, to: $to, organizationID: $org) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
        }
      }
    }
    """
    for start, end in spans:
        data = graphql(query, {"from": start, "to": end, "org": organization_id})
        collection = data["viewer"]["contributionsCollection"]
        for axis, field in FIELDS.items():
            totals[axis] += collection[field]
    return totals


def gather() -> list[Scope]:
    profile = graphql("""
    {
      viewer {
        createdAt
        organizations(first: 20) { nodes { id login } }
      }
    }
    """)["viewer"]

    created = dt.datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
    spans = windows(created)

    overall = collect(spans, None)
    scopes: list[Scope] = []
    remainder = dict(overall)

    for org in profile["organizations"]["nodes"]:
        totals = collect(spans, org["id"])
        if sum(totals.values()) == 0:
            continue
        scopes.append(Scope(org["login"], totals))
        for axis in AXES:
            remainder[axis] -= totals[axis]

    # Subtraction can only go negative if an organization double-counts, which
    # would make the panel a lie. Clamp and keep the personal panel honest.
    personal = {axis: max(0, remainder[axis]) for axis in AXES}
    scopes.append(Scope("personal", personal))
    return scopes


# --- drawing -----------------------------------------------------------------

PANEL_W, PANEL_H = 380, 300
RADIUS = 92
PAD = 16

# Unit vectors, in AXES order: up, right, down, left.
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))
LABEL_ANCHOR = ("middle", "start", "middle", "end")
LABEL_OFFSET = ((0, -RADIUS - 18), (RADIUS + 12, 5), (0, RADIUS + 28), (-RADIUS - 12, 5))


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def panel(scope: Scope, theme: Theme, offset_x: int) -> str:
    cx, cy = offset_x + PANEL_W // 2, PANEL_H // 2 + 6
    parts: list[str] = []

    parts.append(
        f'<text x="{cx}" y="26" text-anchor="middle" fill="{theme.text}" '
        f'font-size="14" font-weight="600">{escape(scope.label)}</text>'
    )

    for (dx, dy) in DIRECTIONS:
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cx + dx * RADIUS}" y2="{cy + dy * RADIUS}" '
            f'stroke="{theme.axis}" stroke-width="1.6"/>'
        )

    for axis, (ox, oy), anchor in zip(AXES, LABEL_OFFSET, LABEL_ANCHOR):
        parts.append(
            f'<text x="{cx + ox}" y="{cy + oy}" text-anchor="{anchor}" '
            f'fill="{theme.muted}" font-size="12">{axis}</text>'
        )

    if scope.total == 0:
        parts.append(
            f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="{theme.muted}" '
            f'font-size="12">No activity recorded</text>'
        )
        return "\n".join(parts)

    points: list[tuple[float, float]] = []
    for axis, (dx, dy) in zip(AXES, DIRECTIONS):
        share = scope.totals[axis] / scope.total
        points.append((cx + dx * RADIUS * share, cy + dy * RADIUS * share))

    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    parts.append(
        f'<polygon points="{polygon}" fill="{theme.fill}" stroke="{theme.accent}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
    )

    for (x, y), axis in zip(points, AXES):
        if scope.totals[axis]:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{theme.accent}"/>'
            )

    dominant = max(AXES, key=lambda a: scope.totals[a])
    share = scope.totals[dominant] / scope.total
    index = AXES.index(dominant)
    lx = cx + LABEL_OFFSET[index][0]
    ly = cy + LABEL_OFFSET[index][1] + (16 if DIRECTIONS[index][1] >= 0 else -16)
    parts.append(
        f'<text x="{lx}" y="{ly}" text-anchor="{LABEL_ANCHOR[index]}" '
        f'fill="{theme.accent}" font-size="12" font-weight="600">'
        f'{share * 100:.0f}%</text>'
    )

    summary = " · ".join(
        f"{scope.totals[axis]} {noun if scope.totals[axis] == 1 else noun + 's'}"
        for axis, noun in (
            ("Commits", "commit"),
            ("Pull requests", "pull request"),
            ("Issues", "issue"),
            ("Code review", "code review"),
        )
    )
    parts.append(
        f'<text x="{cx}" y="{PANEL_H - 8}" text-anchor="middle" fill="{theme.muted}" '
        f'font-size="11">{escape(summary)}</text>'
    )
    return "\n".join(parts)


def render(scopes: list[Scope], theme: Theme) -> str:
    width = PANEL_W * len(scopes) + PAD * 2
    height = PANEL_H + PAD
    panels = "\n".join(
        panel(scope, theme, PAD + PANEL_W * i) for i, scope in enumerate(scopes)
    )
    labels = ", ".join(scope.label for scope in scopes)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" \
viewBox="0 0 {width} {height}" role="img" aria-label="Activity overview for {escape(labels)}">
  <title>Activity overview — {escape(labels)}</title>
  <rect width="{width}" height="{height}" rx="8" fill="{theme.background}"/>
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif">
{panels}
  </g>
</svg>
"""


def main() -> int:
    if not TOKEN:
        print("GH_TOKEN or GITHUB_TOKEN is required", file=sys.stderr)
        return 1

    try:
        scopes = gather()
    except (urllib.error.URLError, RuntimeError, KeyError, TimeoutError) as error:
        print(f"contribution query failed: {error}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        target = OUT_DIR / f"activity-overview-{theme.name}.svg"
        target.write_text(render(scopes, theme), encoding="utf-8")
        print(f"wrote {target}")

    for scope in scopes:
        print(f"  {scope.label:16s} total={scope.total:5d}  {scope.totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
