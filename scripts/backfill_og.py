"""Backfill og_image for recent articles by fetching their URLs.

Runs as a post-scrape step to fill in OG images for articles that:
1. Were scraped recently (configurable window)
2. Don't already have an og_image
3. Prioritizes approved/high-score articles first

Usage:
  python backfill_og.py           # Default: 3-day window, 200 articles
  python backfill_og.py --days 7  # 7-day window
  python backfill_og.py --limit 500  # Process up to 500 articles
"""
import psycopg2
import urllib.request
import re
import sys
import argparse
import time
sys.path.insert(0, "/app")
from config import DB_CONFIG

parser = argparse.ArgumentParser(description='Backfill OG images for articles')
parser.add_argument('--days', type=int, default=3, help='Look back N days (default: 3)')
parser.add_argument('--limit', type=int, default=200, help='Max articles to process (default: 200)')
args = parser.parse_args()

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Prioritize: approved first (by score desc), then pending (by score desc)
cur.execute("""
    SELECT id, url FROM articles
    WHERE scraped_at >= NOW() - INTERVAL '%s days'
      AND (og_image IS NULL OR og_image = '')
    ORDER BY
      CASE WHEN status = 'approved' THEN 0 ELSE 1 END,
      auto_approval_score DESC NULLS LAST
    LIMIT %s
""", (args.days, args.limit))
rows = cur.fetchall()
print(f"Found {len(rows)} articles to process (window: {args.days} days, limit: {args.limit})")

updated = 0
skipped = 0
failed = 0

for i, (article_id, url) in enumerate(rows):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GeoMemoBot/1.0)"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            # Read more bytes to catch OG tags that appear deeper in HTML
            html = resp.read(25000).decode("utf-8", errors="ignore")

        # Try both meta tag orderings
        pat1 = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
        pat2 = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
        # Also try twitter:image as fallback
        pat3 = r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']'
        pat4 = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'

        match = (re.search(pat1, html, re.IGNORECASE)
                 or re.search(pat2, html, re.IGNORECASE)
                 or re.search(pat3, html, re.IGNORECASE)
                 or re.search(pat4, html, re.IGNORECASE))

        if match:
            og_url = match.group(1).strip()
            if og_url.startswith('http'):
                cur.execute("UPDATE articles SET og_image = %s WHERE id = %s", (og_url, article_id))
                conn.commit()
                updated += 1
                if updated <= 20 or updated % 25 == 0:
                    print(f"  [{article_id}] OK: {og_url[:80]}")
            else:
                skipped += 1
        else:
            skipped += 1

        # Brief pause every 50 requests to be polite
        if (i + 1) % 50 == 0:
            print(f"  ... processed {i + 1}/{len(rows)} (updated: {updated})")
            time.sleep(1)

    except Exception as e:
        failed += 1
        if failed <= 10:
            print(f"  [{article_id}] SKIP: {str(e)[:60]}")

print(f"\nDone: {updated} updated | {skipped} no image | {failed} failed | {len(rows)} total")
cur.close()
conn.close()
