"""
Master Reddit poster - posts Viator tours daily to all subreddits.
Rotates through tours by day-of-year so posts don't repeat.
"""
import requests, time, os, sys, json
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

POSTS = {
    "ThingsToDoInLondonUK": [
        ("viator", "London", 3),
    ],
    "LondonEnglandTours": [
        ("viator", "London", 3),
    ],
    "NewYorkCityTours": [
        ("viator", "New York", 3),
    ],
    "ExploreNewYork": [
        ("viator", "New York", 3),
    ],
    "ExploreRome": [
        ("viator", "Rome", 3),
    ],
    "ExploreSydneyAU": [
        ("viator", "Sydney", 2),
        ("viator", "Melbourne", 2),
    ],
    "Explore_SanDiego": [
        ("viator", "San Diego", 3),
    ],
    "ThingsToDoInThailand_": [
        ("viator", "Thailand", 3),
    ],
    "ExploreSouthAfrica": [
        ("viator", "South Africa", 3),
    ],
    "LasVegas_Shows": [
        ("viator", "Las Vegas", 3),
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

try:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Reddit posts...\n")
    token = get_token()
    total = 0
    for subreddit, tasks in POSTS.items():
        for task in tasks:
            if task[0] == "viator":
                _, city, count = task
                total += post_viator(token, subreddit, city, count)
    print(f"Done. {total} total posts.")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
