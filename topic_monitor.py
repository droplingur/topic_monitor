"""
Topic Monitor
=============
Pull web and news sources for a topic using the You.com Web Search API.

The grounding pattern is:
    question -> search API -> source records -> saved evidence -> answer

The API finds candidate sources. A later AI answer should use the saved
title, URL, summary, and article text as evidence, and keep those citations.

Edit TOPIC below, then run:
  python topic_monitor.py

Or override it from the command line:
  python topic_monitor.py --topic "AI music discovery"
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "topic_data"
YOU_SEARCH_URL = "https://ydc-index.io/v1/search"

# Edit this topic when you want to pull data for a new subject.
TOPIC = "Otters living in Switzerland"

# Search settings. These become fields in the API request below.
RESULT_COUNT = 2
FRESHNESS = None  # Examples: "day", "week", "month", "year", "2026-01-01to2026-10-01"
COUNTRY = "CH"
LANGUAGE = "en"
RESTRICTED_DOMAINS = []  # Strict allowlist, for example ["reuters.com"]
EXTRACTION_MODE = "full_page"  # None, "highlights", or "full_page"


load_dotenv(PROJECT_DIR / ".env")


def slugify(text):
    """Create a filename-safe slug from a topic."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug or "topic"


def get_api_key():
    """Read the API key without putting a secret in the source code."""
    api_key = os.getenv("YDC_API_KEY") or os.getenv("YOU_API_KEY")
    if api_key:
        return api_key

    raise RuntimeError(f"Add YDC_API_KEY=... to {PROJECT_DIR / '.env'}")


def search_topic(
    topic,
    count=RESULT_COUNT,
    freshness=FRESHNESS,
    country=COUNTRY,
    language=LANGUAGE,
    restricted_domains=None,
    extraction_mode=EXTRACTION_MODE,
):
    """Search the web and return You.com's raw JSON response."""
    # Keep the request as data so students can see which search choices are
    # being sent without having to rewrite the HTTP call.
    payload = {
        "query": topic,
        "count": count,
        "country": country,
        "language": language,
    }
    if freshness:
        payload["freshness"] = freshness
    if restricted_domains:
        payload["include_domains"] = restricted_domains
    if extraction_mode:
        # Highlights are compact evidence; full_page is more complete but can
        # be slower and more expensive. The raw response is saved below.
        payload["extraction"] = {"extraction_mode": extraction_mode}

    # POST sends settings as JSON. The API key belongs in the header, never in
    # the query or in a checked-in source file.
    request = Request(
        YOU_SEARCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-API-Key": get_api_key(),
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"You.com API error: HTTP {error.code}\n{message}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach You.com API: {error.reason}") from error


def iter_results(data):
    """Convert web/news results into one consistent record shape."""
    results = data.get("results", {})
    for section_name in ("web", "news"):
        for item in results.get(section_name, []):
            contents = item.get("contents") or {}
            article_text = contents.get("markdown") or contents.get("html") or ""
            highlights = contents.get("highlights") or []
            if isinstance(highlights, list):
                article_text = "\n\n".join(highlights) or article_text

            url = item.get("url", "")
            source = urlparse(url).netloc.removeprefix("www.") if url else section_name
            yield {
                "source": source,
                "url": url,
                "title": item.get("title", "Untitled"),
                "short_summary": item.get("description", ""),
                "article_text": article_text,
                "published_date": (
                    item.get("published_time")
                    or item.get("published_date")
                    or item.get("page_age")
                    or item.get("date")
                    or ""
                ),
                "section": section_name,
            }


EXPORT_FIELDS = (
    "source",
    "url",
    "title",
    "short_summary",
    "article_text",
    "published_date",
    "extracted_date",
)


def save_results(topic, data):
    """Save source evidence in formats students can inspect or reuse."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    extracted_at = datetime.now(timezone.utc).isoformat()
    date_output_dir = OUTPUT_DIR / extracted_at[:10]
    date_output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for result in iter_results(data):
        # This timestamp records when we retrieved the evidence, not when the
        # article was published.
        record = {field: result.get(field, "") for field in EXPORT_FIELDS}
        record["extracted_date"] = extracted_at
        records.append(record)

    base_path = date_output_dir / f"{slugify(topic)}_{timestamp}"
    json_path = base_path.with_suffix(".json")
    csv_path = base_path.with_suffix(".csv")

    json_data = {
        "topic": topic,
        "extracted_date": extracted_at,
        "results": records,
    }
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(records)

    return json_path, csv_path, records


def print_results(topic, data, json_path, csv_path, records):
    """Print a compact terminal summary of the pulled data."""
    metadata = data.get("metadata", {})
    print("=" * 60)
    print(f"Topic: {topic}")
    print(f"Results: {len(records)}")
    if metadata.get("search_uuid"):
        print(f"Search UUID: {metadata['search_uuid']}")
    print(f"Saved JSON: {json_path}")
    print(f"Saved CSV: {csv_path}")
    print("=" * 60)

    for index, result in enumerate(records, start=1):
        print(f"\n{index}. {result['title']}")
        print(f"   Source: {result['source']}")
        print(f"   URL: {result['url']}")
        print(f"   Summary: {result['short_summary']}")


def parse_args():
    """Expose the main search controls for terminal use as well as the UI."""
    parser = argparse.ArgumentParser(description="Pull topic data from the You.com Web Search API")
    parser.add_argument("--topic", default=TOPIC, help="Topic to search for")
    parser.add_argument("--count", type=int, default=RESULT_COUNT, help="Results per section, 1-100")
    parser.add_argument(
        "--freshness",
        default=FRESHNESS,
        help='Optional freshness: "day", "week", "month", "year", or YYYY-MM-DDtoYYYY-MM-DD',
    )
    parser.add_argument("--language", default=LANGUAGE, help="Result language, for example en or de")
    parser.add_argument(
        "--domains",
        default=",".join(RESTRICTED_DOMAINS),
        help="Comma-separated domain allowlist, for example reuters.com,apnews.com",
    )
    parser.add_argument(
        "--extraction-mode",
        choices=("highlights", "full_page"),
        default=EXTRACTION_MODE,
        help="How much page text to request from the search API",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    restricted_domains = [domain.strip() for domain in args.domains.split(",") if domain.strip()]
    try:
        data = search_topic(
            args.topic,
            count=args.count,
            freshness=args.freshness,
            language=args.language,
            restricted_domains=restricted_domains,
            extraction_mode=args.extraction_mode,
        )
        json_path, csv_path, records = save_results(args.topic, data)
        print_results(args.topic, data, json_path, csv_path, records)
    except RuntimeError as error:
        print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
