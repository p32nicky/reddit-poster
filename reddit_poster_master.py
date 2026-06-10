"""
Master Reddit poster - posts tours daily to all subreddits
"""
import requests, time, os, sys, json

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

HEADOUT_KEY = "pk_Z.4RWaALZWs5FeVEr9f8t.FOLxzkMCz15PzpssWYtwM~"
HEADOUT_HEADERS = {
    "Headout-Auth": HEADOUT_KEY
}

POSTS = {
    "NewYorkCityTours": [
        ("viator", "New York", 3),
    ],
    "LondonEnglandTours": [
        ("viator", "London", 3),
    ],
    "ExploreRome": [
        ("viator", "Rome", 3),
    ],
    "ThingsToDoInThailand_": [
        ("viator", "Thailand", 3),
    ],
    "ExploreSouthAfrica": [
        ("viator", "South Africa", 3),
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

def fetch_viator(city):
    body = {
        "searchTerm": f"{city} tours",
        "currency": "USD",
        "searchTypes": [{"searchType": "PRODUCTS", "pagination": {"start": 1, "count": 50}}],
        "productSorting": {"sort": "REVIEW_AVG_RATING"}
    }
    r = requests.post("https://api.viator.com/partner/search/freetext",
        headers=VIATOR_HEADERS, json=body, timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("products", {}).get("results", [])

def fetch_headout(city_code):
    r = requests.get(f"https://www.headout.com/api/public/v2/products?cityCode={city_code}&limit=50",
        headers=HEADOUT_HEADERS, timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("products", [])

def post_viator(token, subreddit, city, count):
    tours = fetch_viator(city)
    if not tours:
        print(f"  {subreddit}: 0 tours")
        return 0

    posted = 0
    for t in tours[:count]:
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
            print(f"  ✓ {title[:50]}")
            time.sleep(3)

    print(f"  {subreddit}: {posted}/{count} posted\n")
    return posted

def post_headout(token, subreddit, city_code, count):
    tours = fetch_headout(city_code)
    if not tours:
        return 0

    posted = 0
    for t in tours[:count]:
        title = t.get("name", "")[:200]
        product_code = t.get("productCode", "")
        url = f"https://www.headout.com/experiences/{product_code}/?refId={HEADOUT_KEY}"
        desc = t.get("description", "")[:200].strip()
        rating = t.get("rating", {}).get("average", "") if isinstance(t.get("rating"), dict) else ""
        price = t.get("pricing", {}).get("minPrice", "")

        rating_line = f"**Rating:** {rating}/5  \n" if rating else ""
        price_line = f"**Price:** From {price}  \n" if price else ""
        desc_line = f"\n{desc}\n" if desc else ""

        body = f"""{rating_line}{price_line}{desc_line}
**[Book on Headout →]({url})**

---
*Affiliate link — we may earn a small commission.*"""

        if post_to_reddit(token, subreddit, title, body):
            posted += 1
            print(f"  ✓ {title[:50]}")
            time.sleep(3)

    print(f"  {subreddit}: {posted}/{count} posted\n")
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
            elif task[0] == "headout":
                _, city_code, count = task
                total += post_headout(token, subreddit, city_code, count)
    print(f"✅ Done. {total} total posts.")
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
