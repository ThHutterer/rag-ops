import sys
import re
import ssl
import feedparser
import requests
from typing import List
from datetime import datetime
from email.utils import parsedate_to_datetime

sys.path.insert(0, ".")
from ragops.authority import compute_authority_score

RSS_FEEDS = [
    "https://rss.arxiv.org/rss/cs.AI",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://rss.orf.at/news.xml",
]

MAX_PER_FEED = 50


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_date(entry, field: str) -> str:
    val = entry.get(field + "_parsed")
    if val:
        try:
            dt = datetime(*val[:6])
            return dt.isoformat() + "Z"
        except Exception:
            pass
    raw = entry.get(field)
    if raw:
        try:
            return parsedate_to_datetime(raw).isoformat()
        except Exception:
            return raw
    return datetime.utcnow().isoformat() + "Z"


def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch a feed, using requests as fallback for SSL issues."""
    try:
        # Try requests first (handles SSL better on macOS)
        resp = requests.get(url, timeout=15, verify=False,
                            headers={"User-Agent": "feedparser/6.0"})
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except Exception:
        # Fall back to feedparser directly
        return feedparser.parse(url)


def fetch_articles(dry_run: bool = False) -> List[dict]:
    """
    Fetches articles from all RSS feeds using feedparser.
    If dry_run=True, returns data without inserting into DB.
    """
    # Suppress SSL warnings from requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    results = []

    for feed_url in RSS_FEEDS:
        print(f"Fetching feed: {feed_url}")
        is_arxiv = "arxiv" in feed_url
        source_type = "arxiv_paper" if is_arxiv else "news_article"
        review_status = "preprint" if is_arxiv else "published"
        authority = compute_authority_score(source_type, review_status)

        try:
            feed = _fetch_feed(feed_url)
        except Exception as e:
            print(f"  Error parsing feed: {e}")
            continue

        count = 0
        for entry in feed.entries[:MAX_PER_FEED]:
            url = entry.get("link", "")
            if not url:
                continue

            title = entry.get("title", "Untitled")
            summary = entry.get("summary") or entry.get("description") or ""
            content = _strip_html(summary)

            author = entry.get("author") or (
                entry.get("author_detail", {}).get("name") if entry.get("author_detail") else None
            )

            created_at = _parse_date(entry, "published")
            last_modified = _parse_date(entry, "updated") or created_at

            row = {
                "title": title,
                "content": content,
                "source_type": source_type,
                "author": author,
                "created_at": created_at,
                "last_modified": last_modified,
                "review_status": review_status,
                "authority_score": authority,
                "url": url,
                "metaculus_question_id": None,
                "metaculus_resolution": None,
                "metaculus_resolution_date": None,
            }
            results.append(row)
            count += 1

        print(f"  Got {count} articles")

    print(f"Total articles fetched: {len(results)}")

    if not dry_run and results:
        from ragops.config import get_supabase
        sb = get_supabase()
        inserted = 0
        for row in results:
            try:
                existing = sb.table("documents").select("id").eq("url", row["url"]).execute()
                if not existing.data:
                    sb.table("documents").insert(row).execute()
                    inserted += 1
            except Exception as e:
                print(f"  Error inserting article '{row.get('title', '')[:40]}': {e}")
        print(f"Inserted {inserted} new articles")

    return results


if __name__ == "__main__":
    articles = fetch_articles()
    print(f"Done. Total: {len(articles)}")
