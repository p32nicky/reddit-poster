"""
Import all Substack articles (nickmdavies.substack.com) into londonadventurehub tours DB.
Each becomes a full article page on the site for SEO.
Usage: python import_substack.py
"""
import re, time, sys
import requests
import psycopg2
from datetime import datetime, timezone

DATABASE_URL = "postgresql://neondb_owner:npg_Nq8ZoKMlD1nt@ep-green-sound-angzcs1z-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
PUB = "nickmdavies.substack.com"
H = {"User-Agent": "Mozilla/5.0"}

sys.stdout.reconfigure(encoding="utf-8")

def fetch_archive():
    posts, offset = [], 0
    while True:
        r = requests.get(f"https://{PUB}/api/v1/archive?sort=new&limit=50&offset={offset}", headers=H, timeout=20)
        batch = r.json()
        if not batch:
            break
        posts += batch
        offset += len(batch)
    return posts

def fetch_full(slug):
    r = requests.get(f"https://{PUB}/api/v1/posts/{slug}", headers=H, timeout=20)
    if r.status_code != 200:
        return None
    return r.json()

def extract_link(body_html):
    m = re.search(r'href="(https://www\.headout\.com/[^"]+)"', body_html)
    if m:
        return m.group(1)
    m = re.search(r'href="(https://www\.viator\.com/[^"]+)"', body_html)
    if m:
        return m.group(1)
    return ""

def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT slug FROM tours")
    existing = {r[0] for r in cur.fetchall()}
    print(f"Existing tours in DB: {len(existing)}")

    posts = fetch_archive()
    print(f"Substack posts found: {len(posts)}")

    added = skipped = failed = 0
    for i, p in enumerate(posts, 1):
        slug = p.get("slug", "")
        if not slug or slug in existing:
            skipped += 1
            continue
        full = fetch_full(slug)
        if not full:
            failed += 1
            continue
        title = (full.get("title") or "")[:300]
        subtitle = (full.get("subtitle") or "")[:500]
        body = full.get("body_html") or ""
        cover = full.get("cover_image") or ""
        link = extract_link(body)
        if not body or not title:
            failed += 1
            continue
        pub_date = (full.get("post_date") or "")[:10]
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur.execute("""
                INSERT INTO tours (title, slug, image_url, description, link, keywords, publish_date, first_seen_at, article_text)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (slug) DO NOTHING
            """, (title, slug, cover, subtitle, link or "https://www.headout.com/london",
                  "London, tours, things to do in London", pub_date, now, body))
            added += 1
            if added % 25 == 0:
                print(f"  [{i}/{len(posts)}] added {added}...")
        except Exception as e:
            failed += 1
            print(f"  FAIL {slug}: {e}")
        time.sleep(0.3)

    cur.execute("SELECT COUNT(*) FROM tours")
    total = cur.fetchone()[0]
    conn.close()
    print(f"\nDone. Added {added}, skipped {skipped}, failed {failed}. Total tours now: {total}")

if __name__ == "__main__":
    main()
