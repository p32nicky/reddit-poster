"""
Trip.com things-to-do scraper (undetected-chromedriver, non-headless).
Extracts BOOKABLE activity links (/things-to-do/detail/{id}/) — verified to
deep-link to the tour AND keep affiliate tracking (Allianceid=8675451).

Usage:
  python scrape_tripcom.py <City> [max]
  default city = Rome, default max = 50 (test batch)
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import csv, time, re, sys

ALLIANCE = "8675451"
SID = "319479553"

# Trip.com's keyword listing returns correctly city-filtered bookable tours —
# no per-city searchkey needed. Country subreddits use their tourist-hub city.
def listing_url(keyword):
    return f"https://www.trip.com/things-to-do/list?keyword={keyword.replace(' ', '%20')}"

KEYWORD = {  # POSTS-dict city -> Trip.com search keyword (default: the city name)
    "Thailand": "Bangkok",
    "South Africa": "Cape Town",
}

# Skip generic travel add-ons that show up in keyword results (not tours)
JUNK_RE = re.compile(r'\b(esim|sim card|rail pass|eurail|britrail|jr pass|wifi|data plan|airport transfer|pocket wifi)\b', re.I)

FOOD_RE = re.compile(r'food|eat|tast|cook|wine|cheese|pasta|pizza|dinner|lunch|gelato|culinary|market', re.I)
EXP_RE  = re.compile(r'photo|exclusive|vip|premium|private|skip.the.line|small.group|sunset|cruise|cabaret|show', re.I)

def priority(t):
    if FOOD_RE.search(t): return 0
    if EXP_RE.search(t): return 1
    return 2

def scrape(driver, city, base_url, cap):
    print(f"[*] Loading {city}: {base_url}")
    driver.get(base_url)
    time.sleep(5)
    print(f"    page title: {driver.title[:70]}")

    # Scroll to lazy-load. Be patient through lazy-load pauses: only stop once
    # the count has held steady for several consecutive rounds (or hit the cap).
    last = 0
    stable = 0
    for i in range(80):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.6)
        # nudge up-then-down to retrigger lazy observers that paused
        if stable >= 2:
            driver.execute_script("window.scrollBy(0, -400);")
            time.sleep(0.6)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
        n = len(driver.find_elements(By.CSS_SELECTOR, "a[href*='/things-to-do/detail/']"))
        if n >= cap:
            break
        if n == last:
            stable += 1
            if stable >= 6:   # no growth for 6 rounds -> genuinely exhausted
                break
        else:
            stable = 0
        last = n

    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/things-to-do/detail/']")
    print(f"    found {len(anchors)} detail anchors")

    seen = set(); tours = []
    for a in anchors:
        try:
            href = a.get_attribute("href") or ""
            m = re.search(r'/things-to-do/detail/(\d+)', href)
            if not m: continue
            tid = m.group(1)
            if tid in seen: continue

            title = (a.text or "").strip().split("\n")[0]
            if not title:
                title = (a.get_attribute("aria-label") or "").strip()
            if not title or len(title) < 5: continue
            if JUNK_RE.search(title): continue  # skip eSIM/rail-pass/etc.

            # Image lives in the card <li> ancestor, not inside the anchor.
            # Climb up while the ancestor still wraps exactly THIS one tour
            # (detail_links == 1); grab the first Trip.com CDN image there.
            image = ""
            node = a
            for _ in range(6):
                try:
                    node = node.find_element(By.XPATH, "./..")
                except Exception:
                    break
                if len(node.find_elements(By.CSS_SELECTOR, "a[href*='/things-to-do/detail/']")) != 1:
                    break  # crossed into a multi-card container
                for im in node.find_elements(By.TAG_NAME, "img"):
                    s = im.get_attribute("src") or im.get_attribute("data-src") or ""
                    if "tripcdn" in s or "ctrip" in s:
                        image = s
                        break
                if image:
                    break

            base = href.split("?")[0].rstrip("/")
            url = f"{base}/?Allianceid={ALLIANCE}&SID={SID}"
            seen.add(tid)
            tours.append({"title": title[:200], "url": url, "image": image})
            if len(tours) >= cap: break
        except Exception:
            continue

    tours.sort(key=lambda t: priority(t["title"]))
    print(f"[+] {city}: {len(tours)} bookable tours extracted")
    return tours

def save(city, tours):
    fn = f"tripcom_{city.lower().replace(' ','_')}.csv"
    with open(fn, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title","url","city","image_url"])
        w.writeheader()
        for t in tours:
            w.writerow({"title":t["title"],"url":t["url"],"city":city,"image_url":t["image"]})
    print(f"[OK] saved {len(tours)} -> {fn}")

def _safe(s):
    return (s or "").encode("ascii", "replace").decode("ascii")

def main():
    # Args: city names (POSTS keys). Optional last numeric arg = per-city cap.
    args = sys.argv[1:]
    cap = 50
    if args and args[-1].isdigit():
        cap = int(args[-1]); args = args[:-1]
    cities = args or ["Rome"]

    d = uc.Chrome(headless=False)
    try:
        for city in cities:
            keyword = KEYWORD.get(city, city)
            print(f"\n{'='*50}\n{city.upper()}  (keyword: {keyword})\n{'='*50}")
            tours = scrape(d, city, listing_url(keyword), cap)
            if tours:
                save(city, tours)
                for t in tours[:5]:
                    print("   ", _safe(t["title"][:55]))
    finally:
        try: d.quit()
        except Exception: pass

if __name__ == "__main__":
    main()
