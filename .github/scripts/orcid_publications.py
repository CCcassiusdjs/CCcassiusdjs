#!/usr/bin/env python3
"""Render the ORCID works of a researcher into the README.

ORCID publishes no RSS or Atom feed, so this reads the public v3.0 REST API
directly and rewrites the block delimited by ORCID-LIST:START / ORCID-LIST:END.
An empty ORCID record leaves the placeholder sentence untouched.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

Json = dict[str, Any]

ORCID_ID = os.environ.get("ORCID_ID", "0000-0001-6803-5638")
README = os.environ.get("README_PATH", "README.md")
API = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"

START = "<!-- ORCID-LIST:START -->"
END = "<!-- ORCID-LIST:END -->"

PLACEHOLDER = (
    "_No works registered on ORCID yet. Peer-reviewed output will appear here "
    "automatically once the record is populated._"
)


def fetch_works() -> list[Json]:
    request = urllib.request.Request(API, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: Json = json.load(response)
    groups: list[Json] = payload.get("group", [])
    return groups


def external_url(summary: Json) -> str | None:
    """Prefer a DOI, fall back to any other external identifier."""
    identifiers = (summary.get("external-ids") or {}).get("external-id") or []
    for wanted in ("doi", "handle", "uri"):
        for identifier in identifiers:
            if identifier.get("external-id-type") != wanted:
                continue
            value = identifier.get("external-id-value")
            if wanted == "doi" and value:
                return f"https://doi.org/{value}"
            url = (identifier.get("external-id-url") or {}).get("value")
            if url:
                return url
    return (summary.get("url") or {}).get("value")


def parse(group: Json) -> Json | None:
    summaries = group.get("work-summary") or []
    if not summaries:
        return None
    summary = summaries[0]

    title = (((summary.get("title") or {}).get("title")) or {}).get("value")
    if not title:
        return None

    year = ((summary.get("publication-date") or {}).get("year") or {}).get("value")
    venue = (summary.get("journal-title") or {}).get("value")

    return {
        "title": title.strip(),
        "year": year,
        "venue": venue.strip() if venue else None,
        "url": external_url(summary),
        "type": (summary.get("type") or "").replace("-", " ").lower(),
    }


def render(works: list[Json]) -> str:
    if not works:
        return PLACEHOLDER

    works.sort(key=lambda w: (w["year"] or "0000"), reverse=True)

    lines = []
    for work in works:
        title = f"[{work['title']}]({work['url']})" if work["url"] else work["title"]
        details = [part for part in (work["venue"], work["year"]) if part]
        suffix = f" — {', '.join(details)}" if details else ""
        lines.append(f"- **{title}**{suffix}")
    return "\n".join(lines)


def main() -> int:
    try:
        groups = fetch_works()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"ORCID request failed: {error}", file=sys.stderr)
        return 1

    works = [work for work in (parse(group) for group in groups) if work]
    body = render(works)

    with open(README, encoding="utf-8") as handle:
        content = handle.read()

    pattern = re.compile(
        f"{re.escape(START)}.*?{re.escape(END)}",
        re.DOTALL,
    )
    if not pattern.search(content):
        print(f"markers {START} / {END} not found in {README}", file=sys.stderr)
        return 1

    replacement = f"{START}\n{body}\n{END}"
    updated = pattern.sub(lambda _: replacement, content)

    if updated == content:
        print("README already current")
        return 0

    with open(README, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print(f"README updated with {len(works)} work(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
