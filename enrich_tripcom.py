"""Enrich a tripcom_*.csv with price, rating, reviews, description by fetching
each tour's detail page over plain HTTP (no browser). Adds columns so Reddit /
Substack posts match the Viator layout. Usage: python enrich_tripcom.py <city...>"""
import csv, re, sys, time, html
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def detail_url(u):
    return u.split("?")[0]

def fetch(row):
    try:
        r = requests.get(detail_url(row["url"]), headers=H, timeout=20)
        t = r.text
        price = re.search(r'"price"\s*:\s*"?([\d.]+)', t)
        rating = re.search(r'"commentScore"\s*:\s*"?([\d.]+)', t)
        reviews = re.search(r'"reviewCount"\s*:\s*"?(\d+)', t)
        row["price"] = f"${price.group(1)}" if price else ""
        row["rating"] = rating.group(1) if rating else ""
        row["reviews"] = reviews.group(1) if reviews else ""
        row["description"] = ""   # detail page desc is unreliable (grabs other products)
    except Exception:
        row.setdefault("price", ""); row.setdefault("rating", "")
        row.setdefault("reviews", ""); row.setdefault("description", "")
    return row

def enrich(city):
    fn = f"tripcom_{city.lower().replace(' ','_')}.csv"
    rows = list(csv.DictReader(open(fn, encoding="utf-8")))
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch, r): r for r in rows}
        for f in as_completed(futs):
            done += 1
            if done % 50 == 0:
                print(f"  {city}: {done}/{len(rows)}")
    fields = ["title","url","city","image_url","price","rating","reviews","description"]
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    wp = sum(1 for r in rows if r.get("price"))
    wr = sum(1 for r in rows if r.get("rating"))
    print(f"[OK] {city}: {len(rows)} rows | price {wp} | rating {wr} -> {fn}")

if __name__ == "__main__":
    cities = sys.argv[1:] or ["Rome"]
    for c in cities:
        enrich(c)
