"""
Master Reddit poster - runs all platforms across all subreddits
Upload to PythonAnywhere and set as scheduled task
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
        ("viator", "New York", 3),
        ("byfood", "ny_tours", "tours", "New York", 2),
    ],
    "LondonEnglandTours": [
        ("viator", "London", 3),
        ("byfood", "uk_tours", "tours", "London", 2),
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
            time.sleep(3)

    print(f"  {subreddit} (Viator {city}): {posted}/{count}")
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

    print(f"Done. {total} posts.")
except Exception as e:
    print(f"ERROR: {e}")
