"""Backfill og_image for recent approved articles by fetching their URLs."""
import psycopg2
import urllib.request
import re
import sys
sys.path.insert(0, "/app")
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute("""
    SELECT id, url FROM articles
    WHERE status = 'approved'
      AND scraped_at >= NOW() - INTERVAL '2 days'
      AND (og_image IS NULL OR og_image = '')
    ORDER BY scraped_at DESC
    LIMIT 40
""")
rows = cur.fetchall()
print(f"Found {len(rows)} articles to process")

updated = 0
for article_id, url in rows:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read(15000).decode("utf-8", errors="ignore")
        pat1 = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
        pat2 = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
        match = re.search(pat1, html, re.IGNORECASE) or re.search(pat2, html, re.IGNORECASE)
        if match:
            og_url = match.group(1)
            cur.execute("UPDATE articles SET og_image = %s WHERE id = %s", (og_url, article_id))
            conn.commit()
            updated += 1
            print(f"  [{article_id}] OK: {og_url[:80]}")
        else:
            print(f"  [{article_id}] No og:image found")
    except Exception as e:
        print(f"  [{article_id}] SKIP: {str(e)[:60]}")

print(f"\nDone: {updated}/{len(rows)} articles updated with OG images")
cur.close()
conn.close()
