"""
Master Reddit poster - posts Viator tours daily to all subreddits.
Rotates through tours by day-of-year so posts don't repeat.
"""
import requests, time, os, sys, json, csv
from datetime import datetime, timezone

REDDIT_ID = "weFtQwJPb1wsdq2IXexp7Q"
REDDIT_SECRET = "a-mqkbBtpHICVo--xQWIAPENM_bSUw"
REDDIT_USER = "Basic-Strain-6922"
REDDIT_PASS = "Nd2354zx!!??"

VIATOR_KEY = "1a72ff9c-67a5-4dc0-9eb8-03deec355c5e"
VIATOR_HEADERS = {
    "exp-api-key": VIATOR_KEY,
    "Accept": "application/json;version=2.0",
    "Accept-Language": "en-US",
    "Content-Type": "application/json"
}

# Half Viator / half Trip.com split. Both deep-link direct to the tour and
# track (Viator via target_lander=NONE, Trip.com via Allianceid). GetYourGuide
# is PAUSED (its affiliate links bounce to a concierge page; no bypass param
# found) — re-add ("getyourguide", city, n) tuples if GYG confirms a param.
POSTS = {
    "ThingsToDoInLondonUK": [
        ("viator", "London", 2),
        ("tripcom", "London", 1),
    ],
    "LondonEnglandTours": [
        ("viator", "London", 2),
        ("tripcom", "London", 1),
    ],
    "NewYorkCityTours": [
        ("viator", "New York", 2),
        ("tripcom", "New York", 1),
    ],
    "ExploreNewYork": [
        ("viator", "New York", 2),
        ("tripcom", "New York", 1),
    ],
    "ExploreRome": [
        ("viator", "Rome", 2),
        ("tripcom", "Rome", 1),
    ],
    "ExploreSydneyAU": [
        ("viator", "Sydney", 1),
        ("tripcom", "Sydney", 1),
        ("viator", "Melbourne", 1),
        ("tripcom", "Melbourne", 1),
    ],
    "Explore_SanDiego": [
        ("viator", "San Diego", 2),
        ("tripcom", "San Diego", 1),
    ],
    "ThingsToDoInThailand_": [
        ("viator", "Thailand", 2),
        ("tripcom", "Thailand", 1),
    ],
    "ExploreSouthAfrica": [
        ("viator", "South Africa", 2),
        ("tripcom", "South Africa", 1),
    ],
    "LasVegas_Shows": [
        ("viator", "Las Vegas", 5),
        ("tripcom", "Las Vegas", 5),
    ],
}

def get_token():
    auth = requests.auth.HTTPBasicAuth(REDDIT_ID, REDDIT_SECRET)
    r = requests.post("https://www.reddit.com/api/v1/access_token",
        auth=auth,
        data={"grant_type":"password","username":REDDIT_USER,"password":REDDIT_PASS},
        headers={"User-Agent":"reddit-poster:v1"})
    return r.json()["access_token"]

def post_to_reddit(token, subreddit, title, body):
    headers = {"Authorization": f"bearer {token}", "User-Agent": "reddit-poster:v1"}
    res = requests.post("https://oauth.reddit.com/api/submit",
        headers=headers,
        data={"sr": subreddit, "kind": "self", "title": title, "text": body})
    return res.json().get("success", False)

# Freetext search is fuzzy - verify destination via productUrl path
CITY_URL_MATCH = {
    "London": ["/london/"],
    "New York": ["/new-york"],
    "Rome": ["/rome/"],
    "Sydney": ["/sydney/"],
    "Melbourne": ["/melbourne/"],
    "San Diego": ["/san-diego/"],
    "Thailand": ["bangkok", "phuket", "chiang-mai", "krabi", "pattaya", "koh-samui", "thailand"],
    "South Africa": ["cape-town", "johannesburg", "durban", "kruger", "south-africa", "stellenbosch"],
    "Las Vegas": ["/las-vegas/", "vegas"],
}

def city_match(city, url):
    frags = CITY_URL_MATCH.get(city)
    if not frags:
        return True
    u = url.lower()
    return any(f in u for f in frags)

def fetch_viator(city, count=50, start=1):
    body = {
        "searchTerm": f"{city} tours",
        "currency": "USD",
        "searchTypes": [{"searchType": "PRODUCTS", "pagination": {"start": start, "count": count}}],
        "productSorting": {"sort": "REVIEW_AVG_RATING"}
    }
    r = requests.post("https://api.viator.com/partner/search/freetext",
        headers=VIATOR_HEADERS, json=body, timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("products", {}).get("results", [])

def post_viator(token, subreddit, city, count):
    # Fetch up to 100 tours, rotate by day-of-year so daily posts differ
    tours = fetch_viator(city, 50, 1) + fetch_viator(city, 50, 51)
    tours = [t for t in tours if city_match(city, t.get("productUrl", ""))]
    if not tours:
        print(f"  {subreddit}: 0 tours")
        return 0

    # Prioritize high-converting tours: food, experiences, photo shoots, premium
    import re
    food_re = re.compile(r'food|eat|taste|cook|meal|dining|restaurant|bakery|market|wine|cheese|omakase|wagyu|sushi', re.I)
    exp_re = re.compile(r'photo|shoot|exclusive|vip|premium|opera|concert|theater|spa|private', re.I)

    def tour_priority(t):
        title = t.get("title", "").lower()
        if food_re.search(title):
            return 0  # food = highest priority
        if exp_re.search(title):
            return 1  # experiences = second
        return 2  # generic tours = last

    tours.sort(key=tour_priority)  # Sort food first, then experiences, then generic

    day = datetime.now(timezone.utc).timetuple().tm_yday
    offset = (day * count) % len(tours)
    batch = (tours + tours)[offset:offset + count]

    posted = 0
    for t in batch:
        title = t.get("title", "")[:200]
        url = t.get("productUrl", "") + "&target_lander=NONE"
        desc = t.get("description", "")
        if isinstance(desc, dict):
            desc = desc.get("snippet", "") or desc.get("overview", "")
        desc = (desc or "")[:200].strip()
        rating = t.get("reviews", {}).get("combinedAverageRating", "")
        review_count = t.get("reviews", {}).get("totalReviews", "")
        price = t.get("pricing", {}).get("summary", {}).get("fromPrice", "")
        currency = t.get("pricing", {}).get("currency", "USD")

        rating_line = f"**Rating:** {rating}/5 ({review_count} reviews)  \n" if rating else ""
        price_line = f"**Price:** From {currency} {price}  \n" if price else ""
        desc_line = f"\n{desc}\n" if desc else ""

        body = f"""{rating_line}{price_line}{desc_line}
**[Book on Viator →]({url})**

---
*Affiliate link — we may earn a small commission.*"""

        if post_to_reddit(token, subreddit, title, body):
            posted += 1
            print(f"  + {title[:50]}")
            time.sleep(3)

    print(f"  {subreddit} ({city}): {posted}/{count} posted\n")
    return posted

# GetYourGuide poster — reads CSVs scraped locally by scrape_getyourguide.py
# (GYG blocks headless, so scraping runs on Nick's PC; CSVs are committed to the
#  repo and this poster reads them in GitHub Actions). Affiliate: partner VF7NIT2.
GYG_PARTNER_ID = "VF7NIT2"

def _gyg_csv_path(city):
    fname = f"getyourguide_{city.lower().replace(' ', '_')}.csv"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)

def load_getyourguide(city):
    path = _gyg_csv_path(city)
    if not os.path.exists(path):
        return []
    tours = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            url = (row.get("url") or "").strip()
            if title and url:
                tours.append({
                    "title": title,
                    "url": url,
                    "image": (row.get("image_url") or "").strip(),
                    "price": (row.get("price") or "").strip(),
                    "rating": (row.get("rating") or "").strip(),
                    "reviews": (row.get("reviews") or "").strip(),
                    "duration": (row.get("duration") or "").strip(),
                })
    return tours

def post_getyourguide(token, subreddit, city, count):
    tours = load_getyourguide(city)
    if not tours:
        print(f"  {subreddit} ({city}): 0 GetYourGuide tours (no CSV yet)")
        return 0

    # CSV is already sorted food/experience first. Rotate by day-of-year so
    # daily posts differ but high-converters still surface regularly.
    day = datetime.now(timezone.utc).timetuple().tm_yday
    offset = (day * count) % len(tours)
    batch = (tours + tours)[offset:offset + count]

    posted = 0
    for t in batch:
        title = t["title"][:280]
        url = t["url"]
        # Ensure affiliate params present
        if "partner_id" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}partner_id={GYG_PARTNER_ID}&utm_medium=online_publisher"

        rating_line = ""
        if t.get("rating"):
            rev = f" ({t['reviews']} reviews)" if t.get("reviews") else ""
            rating_line = f"**Rating:** {t['rating']}/5{rev}  \n"
        price_line = f"**Price:** From {t['price']}  \n" if t.get("price") else ""
        dur_line = f"**Duration:** {t['duration']}  \n" if t.get("duration") else ""
        img_line = f"[View tour photo]({t['image']})\n\n" if t.get("image") else ""
        body = f"""{rating_line}{price_line}{dur_line}{img_line}**[Book on GetYourGuide →]({url})**

---
*Affiliate link — we may earn a small commission at no extra cost to you.*"""

        if post_to_reddit(token, subreddit, title, body):
            posted += 1
            print(f"  + {title[:50]}")
            time.sleep(3)

    print(f"  {subreddit} ({city}): {posted}/{count} GetYourGuide posted\n")
    return posted

# Trip.com poster — reads CSVs scraped locally by scrape_tripcom.py.
# Links deep-link direct to the tour and carry Allianceid tracking (verified).
TRIP_ALLIANCE_ID = "8675451"

def load_tripcom(city):
    fname = f"tripcom_{city.lower().replace(' ', '_')}.csv"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    if not os.path.exists(path):
        return []
    tours = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = (row.get("title") or "").strip()
            url = (row.get("url") or "").strip()
            if title and url:
                tours.append({"title": title, "url": url,
                              "image": (row.get("image_url") or "").strip()})
    return tours

def post_tripcom(token, subreddit, city, count):
    tours = load_tripcom(city)
    if not tours:
        print(f"  {subreddit} ({city}): 0 Trip.com tours (no CSV yet)")
        return 0

    day = datetime.now(timezone.utc).timetuple().tm_yday
    offset = (day * count) % len(tours)
    batch = (tours + tours)[offset:offset + count]

    posted = 0
    for t in batch:
        title = t["title"][:280]
        url = t["url"]
        if "Allianceid" not in url:
            url += ("&" if "?" in url else "?") + f"Allianceid={TRIP_ALLIANCE_ID}"
        img_line = f"[View tour photo]({t['image']})\n\n" if t.get("image") else ""
        body = f"""{img_line}**[Book on Trip.com →]({url})**

---
*Affiliate link — we may earn a small commission at no extra cost to you.*"""

        if post_to_reddit(token, subreddit, title, body):
            posted += 1
            print(f"  + {title[:50]}")
            time.sleep(3)

    print(f"  {subreddit} ({city}): {posted}/{count} Trip.com posted\n")
    return posted

try:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Reddit posts...\n")
    token = get_token()
    total = 0
    for subreddit, tasks in POSTS.items():
        for task in tasks:
            if task[0] == "viator":
                _, city, count = task
                total += post_viator(token, subreddit, city, count)
            elif task[0] == "getyourguide":
                _, city, count = task
                total += post_getyourguide(token, subreddit, city, count)
            elif task[0] == "tripcom":
                _, city, count = task
                total += post_tripcom(token, subreddit, city, count)
    print(f"Done. {total} total posts.")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
