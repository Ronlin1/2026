#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTH_PATTERN = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
MONTH_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

DEFAULT_FEEDS = [
    "https://opportunitydesk.org/feed/",
    "https://www.opportunitiesforafricans.com/feed/",
    "https://www.afterschoolafrica.com/feed/",
    "https://scholarshipscorner.website/feed/",
    "https://www2.fundsforngos.org/feed/",
]

OPPORTUNITY_KEYWORDS = {
    "accelerator",
    "award",
    "challenge",
    "competition",
    "conference",
    "fellowship",
    "grant",
    "grants",
    "hackathon",
    "internship",
    "program",
    "residency",
    "scholarship",
    "summit",
}

DEADLINE_WORDS = re.compile(
    r"\b(deadline|closing date|applications? close|apply by|submit by|due by|ends on|closes on)\b",
    re.IGNORECASE,
)

REQUEST_HEADERS = {
    "User-Agent": "Ronlin1-2026-opportunity-agent/1.0 (+https://github.com/Ronlin1/2026)"
}


@dataclass(frozen=True)
class Opportunity:
    title: str
    url: str
    deadline: date
    source: str


@dataclass(frozen=True)
class FeedItem:
    title: str
    url: str
    summary: str
    source: str


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_from_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return normalize_space(html.unescape(value))


def month_number(value: str) -> int | None:
    normalized = value.lower().replace(".", "")
    return MONTH_TO_NUMBER.get(normalized)


def safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_first_date(text: str) -> date | None:
    month_first = re.compile(
        rf"\b({MONTH_PATTERN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(20\d{{2}})\b",
        re.IGNORECASE,
    )
    day_first = re.compile(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_PATTERN})\.?(?:,)?\s+(20\d{{2}})\b",
        re.IGNORECASE,
    )
    iso_date = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")

    for match in month_first.finditer(text):
        month = month_number(match.group(1))
        if month:
            parsed = safe_date(int(match.group(3)), month, int(match.group(2)))
            if parsed:
                return parsed

    for match in day_first.finditer(text):
        month = month_number(match.group(2))
        if month:
            parsed = safe_date(int(match.group(3)), month, int(match.group(1)))
            if parsed:
                return parsed

    for match in iso_date.finditer(text):
        parsed = safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed:
            return parsed

    return None


def extract_deadline_date(text: str) -> date | None:
    clean_text = text_from_html(text)

    for match in DEADLINE_WORDS.finditer(clean_text):
        window = clean_text[match.start() : match.end() + 180]
        parsed = find_first_date(window)
        if parsed:
            return parsed

    return find_first_date(clean_text)


def display_deadline(deadline: date, buffer_days: int) -> date:
    return deadline - timedelta(days=buffer_days)


def listed_deadline(deadline: date, today: date | None = None, buffer_days: int = 3) -> date:
    buffered = display_deadline(deadline, buffer_days)
    if today is None:
        return buffered
    return max(buffered, today)


def clean_title(title: str) -> str:
    title = text_from_html(title)
    title = re.sub(r"\s+[-|]\s+(Opportunity Desk|Opportunities For Africans|Youth Opportunities).*", "", title, flags=re.I)
    title = re.sub(r"(?i)^applications?\s+(are\s+)?open\s+(for|to)\s+", "", title)
    title = re.sub(r"(?i)^apply\s+(now\s+)?(for|to)\s+", "", title)
    title = re.sub(r"(?i)^call\s+for\s+applications?:?\s*", "", title)
    title = normalize_space(title).strip(" -:")
    title = title.replace("((", "(")

    if len(title) > 80:
        title = re.sub(r"\s*\([^)]*(?:\)|$)", "", title)
        title = re.sub(r"(?i)(\b20\d{2}(?:[–-]20\d{2})?)\s+for\b.*$", r"\1", title)
        title = normalize_space(title).strip(" -:")

    if len(title) > 110:
        title = title[:107].rstrip(" -,.;:") + "..."

    return title


def clean_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept_query = [
        (key, value)
        for key, value in query
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(kept_query),
            "",
        )
    ).rstrip(").,")


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(clean_url(url))
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    query = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)))
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def normalize_title(title: str) -> str:
    title = clean_title(title).lower()
    title = re.sub(r"\b20\d{2}\b", " ", title)
    title = re.sub(r"^(the|a|an)\s+", "", title)
    return re.sub(r"[^a-z0-9]+", " ", title).strip()


def format_opportunity_line(
    opportunity: Opportunity,
    buffer_days: int = 3,
    today: date | None = None,
) -> str:
    listed_date = listed_deadline(opportunity.deadline, today=today, buffer_days=buffer_days)
    month = MONTHS[listed_date.month - 1]
    return f"- [ ] {clean_title(opportunity.title)} {clean_url(opportunity.url)} {month} {listed_date.day}"


def existing_urls(readme: str) -> set[str]:
    urls = re.findall(r"https?://[^\s)>\]]+", readme)
    return {normalize_url(url) for url in urls}


def existing_titles(readme: str) -> set[str]:
    titles = set()
    for line in readme.splitlines():
        match = re.match(r"^- \[[ xX]\]\s+(.+?)\s+https?://", line)
        if match:
            title = normalize_title(match.group(1))
            if title:
                titles.add(title)
    return titles


def is_duplicate(readme: str, opportunity: Opportunity, seen_urls: set[str], seen_titles: set[str]) -> bool:
    url = normalize_url(opportunity.url)
    title = normalize_title(opportunity.title)
    return url in seen_urls or bool(title and title in seen_titles)


def month_section_pattern(month: str) -> re.Pattern[str]:
    return re.compile(
        rf"<details open>\s*\n\s*<summary><h2>\s*{re.escape(month)}\s*:sparkles:\s*</h2></summary>.*?</details>",
        re.IGNORECASE | re.DOTALL,
    )


def insert_line_into_section(section: str, line: str) -> str:
    placeholder = re.search(r"(?m)^- \[ \]\s*$", section)
    if placeholder:
        return section[: placeholder.start()] + line + "\n" + section[placeholder.start() :]

    close_index = section.lower().rfind("</details>")
    if close_index == -1:
        return section.rstrip() + "\n" + line + "\n"

    body = section[:close_index].rstrip()
    return body + "\n" + line + "\n\n" + section[close_index:]


def new_month_section(month: str, lines: list[str]) -> str:
    joined_lines = "\n".join(lines)
    return (
        f"<details open>\n"
        f" <summary><h2> {month} :sparkles: </h2></summary>\n"
        f"\n"
        f"{joined_lines}\n\n"
        f"</details>\n\n"
    )


def static_section_start(readme: str) -> int:
    match = re.search(r"(?m)^## .*?(Other Great Repos|Ambassadorships|Offers|Reads)", readme)
    return match.start() if match else len(readme)


def month_sections(readme: str) -> Iterable[re.Match[str]]:
    return re.finditer(
        r"<details open>\s*\n\s*<summary><h2>\s*([A-Z]{3})\s*:sparkles:\s*</h2></summary>.*?</details>\s*",
        readme,
        re.IGNORECASE | re.DOTALL,
    )


def missing_month_insertion_index(readme: str, month: str) -> int:
    target_index = MONTHS.index(month)
    fallback_index = static_section_start(readme)
    last_prior_end: int | None = None

    for match in month_sections(readme):
        existing_month = match.group(1).upper()
        if existing_month not in MONTHS:
            continue

        existing_index = MONTHS.index(existing_month)
        if existing_index > target_index:
            return match.start()
        if existing_index < target_index:
            last_prior_end = match.end()

    if last_prior_end is not None and last_prior_end <= fallback_index:
        return last_prior_end

    return fallback_index


def insert_line_for_month(readme: str, month: str, line: str) -> str:
    pattern = month_section_pattern(month)
    match = pattern.search(readme)
    if match:
        section = match.group(0)
        updated_section = insert_line_into_section(section, line)
        return readme[: match.start()] + updated_section + readme[match.end() :]

    insertion_index = missing_month_insertion_index(readme, month)
    section = new_month_section(month, [line])
    prefix = readme[:insertion_index].rstrip() + "\n\n"
    suffix = readme[insertion_index:].lstrip("\n")
    return prefix + section + suffix


def insert_opportunities(
    readme: str,
    opportunities: Iterable[Opportunity],
    today: date | None = None,
    buffer_days: int = 3,
    max_items: int | None = None,
) -> tuple[str, list[Opportunity]]:
    today = today or date.today()
    updated = readme
    added: list[Opportunity] = []
    seen_urls = existing_urls(readme)
    seen_titles = existing_titles(readme)

    for opportunity in opportunities:
        if max_items is not None and len(added) >= max_items:
            break

        if opportunity.deadline <= today:
            continue
        if is_duplicate(updated, opportunity, seen_urls, seen_titles):
            continue

        listed_date = listed_deadline(opportunity.deadline, today=today, buffer_days=buffer_days)
        line = format_opportunity_line(opportunity, buffer_days=buffer_days, today=today)
        month = MONTHS[listed_date.month - 1]
        updated = insert_line_for_month(updated, month, line)
        added.append(opportunity)
        seen_urls.add(normalize_url(opportunity.url))
        seen_titles.add(normalize_title(opportunity.title))

    return updated, added


def looks_like_opportunity(text: str) -> bool:
    normalized = text.lower()
    return any(re.search(rf"\b{re.escape(keyword)}s?\b", normalized) for keyword in OPPORTUNITY_KEYWORDS)


def has_stale_title_year(title: str, target_year: int = 2026) -> bool:
    years = {int(year) for year in re.findall(r"\b20\d{2}\b", title)}
    return bool(years and target_year not in years and min(years) < target_year)


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_feed_items(feed_text: str, source_url: str) -> list[FeedItem]:
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError:
        return []

    items: list[FeedItem] = []

    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        summary = item.findtext("description") or ""
        content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
        if title and link:
            items.append(FeedItem(title=title, url=link, summary=summary + " " + content, source=source_url))

    atom_namespace = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f".//{atom_namespace}entry"):
        title = entry.findtext(f"{atom_namespace}title") or ""
        summary = entry.findtext(f"{atom_namespace}summary") or entry.findtext(f"{atom_namespace}content") or ""
        link = ""
        for link_node in entry.findall(f"{atom_namespace}link"):
            href = link_node.attrib.get("href")
            if href:
                link = href
                break
        if title and link:
            items.append(FeedItem(title=title, url=link, summary=summary, source=source_url))

    return items


def collect_feed_items(feed_urls: Iterable[str]) -> list[FeedItem]:
    items: list[FeedItem] = []
    for feed_url in feed_urls:
        try:
            feed_text = fetch_text(feed_url)
            items.extend(parse_feed_items(feed_text, feed_url))
        except (TimeoutError, urllib.error.URLError, UnicodeError, OSError) as exc:
            print(f"warning: failed to fetch {feed_url}: {exc}", file=sys.stderr)
    return items


def opportunity_from_item(item: FeedItem, today: date, page_fetch_allowed: bool) -> Opportunity | None:
    combined_text = f"{item.title} {item.summary}"
    if not looks_like_opportunity(combined_text):
        return None
    if has_stale_title_year(item.title):
        return None

    deadline = extract_deadline_date(combined_text)
    if deadline is None and page_fetch_allowed:
        try:
            page_text = fetch_text(item.url)
            deadline = extract_deadline_date(page_text)
            time.sleep(0.4)
        except (TimeoutError, urllib.error.URLError, UnicodeError, OSError) as exc:
            print(f"warning: failed to inspect {item.url}: {exc}", file=sys.stderr)

    if deadline is None or deadline.year != 2026:
        return None

    if deadline <= today:
        return None

    return Opportunity(
        title=clean_title(item.title),
        url=clean_url(item.url),
        deadline=deadline,
        source=item.source,
    )


def collect_opportunities(
    feed_urls: Iterable[str],
    today: date,
    max_page_fetches: int = 20,
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    seen: set[tuple[str, str]] = set()
    page_fetches = 0

    for item in collect_feed_items(feed_urls):
        page_allowed = page_fetches < max_page_fetches
        opportunity = opportunity_from_item(item, today=today, page_fetch_allowed=page_allowed)
        if opportunity is None:
            if page_allowed and looks_like_opportunity(f"{item.title} {item.summary}"):
                page_fetches += 1
            continue

        key = (normalize_url(opportunity.url), normalize_title(opportunity.title))
        if key in seen:
            continue

        seen.add(key)
        opportunities.append(opportunity)

    return sorted(opportunities, key=lambda opp: (listed_deadline(opp.deadline, today, 3), normalize_title(opp.title)))


def parse_today(value: str | None) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add one or two new opportunities to README.md.")
    parser.add_argument("--readme", default="README.md", help="Path to README.md")
    parser.add_argument("--max-items", type=int, default=int(os.getenv("MAX_ITEMS", "5")))
    parser.add_argument("--buffer-days", type=int, default=3)
    parser.add_argument("--today", help="Override today's date as YYYY-MM-DD for tests or manual runs")
    parser.add_argument("--feed", action="append", dest="feeds", help="Extra or replacement feed URL")
    parser.add_argument("--dry-run", action="store_true", help="Print planned additions without writing README.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    today = parse_today(args.today)
    readme_path = Path(args.readme)
    readme = readme_path.read_text(encoding="utf-8")
    feed_urls = args.feeds or DEFAULT_FEEDS

    candidates = collect_opportunities(feed_urls, today=today)
    updated, added = insert_opportunities(
        readme,
        candidates,
        today=today,
        buffer_days=args.buffer_days,
        max_items=max(args.max_items, 0),
    )

    if not added:
        print("No new credible opportunities found.")
        return 0

    for opportunity in added:
        listed_date = listed_deadline(opportunity.deadline, today=today, buffer_days=args.buffer_days)
        print(
            f"Add: {clean_title(opportunity.title)} "
            f"({listed_date:%b} {listed_date.day}, {listed_date.year}) {clean_url(opportunity.url)}"
        )

    if not args.dry_run:
        readme_path.write_text(updated, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
