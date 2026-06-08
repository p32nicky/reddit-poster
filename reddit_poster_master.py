"""
Master Reddit poster - runs all platforms across all subreddits
TEST VERSION - posts 1 per subreddit
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

POSTS = {
    "NewYorkCityTours": [
        ("viator", "New York", 1),
    ],
    "LondonEnglandTours": [
        ("viator", "London", 1),
    ],
    "ExploreRome": [
        ("viator", "Rome", 1),
    ],
    "ThingsToDoInThailand_": [
        ("viator", "Thailand", 1),
    ],
    "ExploreSouthAfrica": [
        ("viator", "South Africa", 1),
    ],
}

def get_token():
    auth = requests.auth.HTTPBasicAuth(REDDIT_ID, REDDIT_SECRET)
    r = requests.post("https://www.reddit.com/api/v1/access_token",
        auth=auth,
        data={"grant_type":"password","username":REDDIT_USER,"password":REDDIT_PASS},
        headers={"User-Agent":"reddit-master-poster:v1"})
    return r.json()["access_token"]

def post_to_reddit(token, subreddit, title, body):
    headers = {"Authorization": f"bearer {token}", "User-Agent": "reddit-master-poster:v1"}
    res = requests.post("https://oauth.reddit.com/api/submit",
        headers=headers,
        data={"sr": subreddit, "kind": "self", "title": title, "text": body})
    data = res.json()
    if data.get("success", False):
        return True
    return False

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

def post_viator(token, subreddit, city, count):
    tours = fetch_viator(city)
    if not tours:
        print(f"  {subreddit}: 0 Viator tours")
        return 0

    posted = 0
    for t in tours[:count]:
        title = t.get("title", "")[:200]
        url = t.get("productUrl", "") + "&target_lander=NONE"
        rating = t.get("reviews", {}).get("combinedAverageRating", "")
        price = t.get("pricing", {}).get("summary", {}).get("fromPrice", "")

        body = f"**[Book on Viator →]({url})**\n\n---\n*Affiliate link*"
        if post_to_reddit(token, subreddit, title, body):
            posted += 1
            print(f"    ✓ {title[:60]}")
            time.sleep(3)

    print(f"  {subreddit}: {posted} posted")
    return posted

# Main
try:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Reddit posts...")
    token = get_token()
    total = 0

    for subreddit, tasks in POSTS.items():
        for task in tasks:
            if task[0] == "viator":
                _, city, count = task
                total += post_viator(token, subreddit, city, count)

    print(f"\n✅ Done. {total} posts.")
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
