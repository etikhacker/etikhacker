#!/usr/bin/env python3
"""Generate self-hosted GitHub profile SVG cards from the GitHub API.

Uses only Python's standard library and the GitHub Actions GITHUB_TOKEN.
The SVGs are published with the contribution snake to the output branch.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import date, timedelta, timezone, datetime
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_PROFILE_USER", "etikhacker")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "Shell": "#89e051",
}
BG, BORDER, TEXT, MUTED, ACCENT = "#0d1117", "#30363d", "#e6edf3", "#8b949e", "#58a6ff"


def github(path: str, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "etikhacker-profile-assets",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(API + path, headers=headers, data=data, method="POST" if data else "GET")
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def public_repositories() -> list[dict]:
    result: list[dict] = []
    page = 1
    while True:
        response = github(
            f"/users/{quote(USERNAME, safe='')}/repos?type=owner&per_page=100&page={page}"
        )
        if not isinstance(response, list):
            raise ValueError("GitHub returned an invalid repositories response")
        result.extend(repo for repo in response if not repo.get("private"))
        if len(response) < 100:
            break
        page += 1
        if page > 20:
            raise ValueError("Repository pagination limit exceeded")
    return result


def language_bytes(repositories: list[dict]) -> Counter:
    counts: Counter = Counter()
    for repo in repositories:
        if repo.get("fork"):
            continue
        owner = quote(repo["owner"]["login"], safe="")
        name = quote(repo["name"], safe="")
        try:
            data = github(f"/repos/{owner}/{name}/languages")
            if isinstance(data, dict):
                counts.update({key: int(val) for key, val in data.items() if int(val) > 0})
        except (HTTPError, URLError, ValueError, KeyError) as exc:
            print(f"Warning: skipped language data for {repo['name']}: {exc}", file=sys.stderr)
    return counts


def contribution_metrics() -> tuple[int, int] | None:
    """12-month contribution total and current consecutive-day streak."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """
    try:
        data = github("/graphql", {"query": query, "variables": {"login": USERNAME}})
        if not isinstance(data, dict) or data.get("errors"):
            raise ValueError(f"GraphQL errors: {data.get('errors') if isinstance(data, dict) else data}")
        calendar = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        counts = {
            date.fromisoformat(day["date"]): int(day["contributionCount"])
            for week in calendar["weeks"]
            for day in week["contributionDays"]
        }
        today = datetime.now(timezone.utc).date()
        cursor = today if counts.get(today, 0) else today - timedelta(days=1)
        streak = 0
        while counts.get(cursor, 0) > 0:
            streak += 1
            cursor -= timedelta(days=1)
        return int(calendar["totalContributions"]), streak
    except (HTTPError, URLError, ValueError, KeyError, TypeError) as exc:
        print(f"Warning: contribution data unavailable: {exc}", file=sys.stderr)
        return None


def label(x: int, y: int, value: str, size: int = 14, color: str = TEXT, weight: int = 400) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="'
        f'-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>'
    )


def svg_card(title: str, subtitle: str, inner: str, height: int = 215) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'viewBox="0 0 600 {height}" width="600" height="{height}">'
        f'<rect x="1" y="1" width="598" height="{height - 2}" rx="14" '
        f'fill="{BG}" stroke="{BORDER}"/>'
        + label(24, 35, title, 20, TEXT, 700)
        + label(24, 56, subtitle, 12, MUTED)
        + f'<path d="M24 69 H576" stroke="{BORDER}"/>'
        + inner
        + '</svg>\n'
    )


def make_overview(repositories: list[dict], metrics: tuple[int, int] | None) -> str:
    contributions = str(metrics[0]) if metrics else "N/A"
    streak = f"{metrics[1]} days" if metrics else "N/A"
    values = [
        ("Contributions (12m)", contributions),
        ("Public repositories", str(len(repositories))),
        ("Total stars", str(sum(int(repo.get("stargazers_count", 0)) for repo in repositories))),
        ("Current streak", streak),
    ]
    out = ""
    for idx, (name, value) in enumerate(values):
        x = 26 + (idx % 2) * 294
        y = 113 + (idx // 2) * 66
        out += label(x, y, value, 28, ACCENT, 700)
        out += label(x, y + 18, name, 12, MUTED)
    out += label(24, 205, "Generated daily from GitHub API • Public account activity", 11, MUTED)
    return svg_card("GitHub overview", f"@{USERNAME}", out, 225)


def make_languages(counts: Counter) -> str:
    total = sum(counts.values())
    out = ""
    if total <= 0:
        out += label(24, 114, "Language breakdown is temporarily unavailable.", 15, MUTED)
    else:
        for idx, (language, value) in enumerate(counts.most_common(5)):
            y = 93 + idx * 27
            pct = value / total * 100
            bar_width = max(2, round(316 * pct / 100))
            color = COLORS.get(language, "#58a6ff")
            out += label(24, y, language[:22], 13, TEXT, 600)
            out += f'<rect x="192" y="{y - 11}" width="316" height="11" rx="5.5" fill="#21262d"/>'
            out += f'<rect x="192" y="{y - 11}" width="{bar_width}" height="11" rx="5.5" fill="{color}"/>'
            out += label(523, y, f"{pct:.1f}%", 12, MUTED)
    out += label(24, 240, "Based on code bytes in public non-fork repositories.", 11, MUTED)
    return svg_card("Top languages", "Public repositories • byte-weighted", out, 257)


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    repositories = public_repositories()
    languages = language_bytes(repositories)
    metrics = contribution_metrics()
    output.mkdir(parents=True, exist_ok=True)
    (output / "github-overview.svg").write_text(
        make_overview(repositories, metrics), encoding="utf-8"
    )
    (output / "github-languages.svg").write_text(
        make_languages(languages), encoding="utf-8"
    )
    print(f"Generated two SVG cards for {len(repositories)} public repositories.")


if __name__ == "__main__":
    main()
