"""
GetYourGuide scraper using undetected-chromedriver (non-headless).
GYG blocks headless mode, so this runs a visible window.
Extracts bookable tours for cities with subreddits and exports to CSV.
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import csv
import time
import re

PARTNER_ID = "VF7NIT2"
UTM = f"partner_id={PARTNER_ID}&utm_medium=online_publisher"

# Verified GetYourGuide city codes (resolved via search)
CITIES = {
    "Rome": "rome-l33",
    "London": "london-l57",
    "Sydney": "sydney-l200",
    "New York": "new-york-city-l59",
    "San Diego": "san-diego-l263",
    "Paris": "paris-l16",
}

# High-converting keywords (food/experiences first per conversion data)
FOOD_RE = re.compile(r'food|eat|tast(e|ing)|cook|wine|cheese|pasta|pizza|dinner|lunch|brunch|gelato|market|culinary', re.I)
EXP_RE  = re.compile(r'photo|shoot|exclusive|vip|premium|private|skip.the.line|small.group|sunset|cruise|boat', re.I)


def tour_priority(title):
    if FOOD_RE.search(title):
        return 0
    if EXP_RE.search(title):
        return 1
    return 2


# Junk lines that appear in GYG card text but aren't the title
_JUNK_RE = re.compile(
    r'^(booked\s+\d+\s+times|top rated|bestseller|new\b|likely to sell out|'
    r'free cancellation|from$|\$[\d,]+|\(\d[\d,]*\)|[\d.]+$|'
    r'.*\b(hours?|days?|minutes?)\b.*•|.*•.*private option|day trip$)',
    re.I,
)


def clean_title(raw):
    """GYG card text is multiline (badge/title/duration/rating/price).
    Pick the real tour title line."""
    lines = [l.strip() for l in (raw or "").split("\n") if l.strip()]
    candidates = [l for l in lines if not _JUNK_RE.match(l)]
    if not candidates:
        return ""
    # Prefer a line with a "City:" style prefix, else the longest candidate
    for l in candidates:
        if re.match(r'^[A-Z][a-zA-Z .]+:\s', l):
            return l
    return max(candidates, key=len)


def scrape_getyourguide(driver, city_name):
    city_slug = CITIES.get(city_name, city_name.lower())
    base_url = f"https://www.getyourguide.com/{city_slug}/"
    print(f"[*] Loading {city_name} ({base_url})...")

    driver.get(base_url)
    time.sleep(4)

    # Aggressively scroll to lazy-load ALL tours (GYG loads ~40 at a time).
    # Keep scrolling until the tour-link count stops growing.
    last_count = 0
    stable_rounds = 0
    max_rounds = 80
    for _ in range(max_rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.4)
        # Click a "Show more" / "Load more" button if present
        try:
            for btn in driver.find_elements(By.CSS_SELECTOR, "button"):
                label = (btn.text or "").lower()
                if "show more" in label or "load more" in label:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.4)
                    break
        except Exception:
            pass

        count = len(driver.find_elements(By.CSS_SELECTOR, "a[href*='-t']"))
        if count <= last_count:
            stable_rounds += 1
            if stable_rounds >= 3:  # no growth 3 rounds in a row -> done
                break
        else:
            stable_rounds = 0
        last_count = count

    # Tour links are relative: /<city>-l<id>/<slug>-t<tourid>/?...
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='-t']")
    seen_ids = set()
    tours = []

    for a in anchors:
        try:
            href = a.get_attribute("href") or ""
            m = re.search(r'-t(\d+)/', href)
            if not m:
                continue
            tour_id = m.group(1)
            if tour_id in seen_ids:
                continue

            # Title: clean the multiline card text, fallbacks to aria-label / slug
            title = clean_title(a.text)
            if not title:
                title = (a.get_attribute("aria-label") or "").strip()
            if not title:
                slug_m = re.search(r'/[a-z0-9-]+-l\d+/(.+?)-t\d+/', href)
                title = slug_m.group(1).replace("-", " ").title() if slug_m else ""
            if not title or len(title) < 5:
                continue

            # Build clean affiliate URL (strip ranking_uuid/q noise, keep base path)
            base = href.split("?")[0]
            if not base.startswith("http"):
                base = "https://www.getyourguide.com" + base
            url = f"{base}?{UTM}"

            # Image (best-effort)
            image = ""
            try:
                img = a.find_element(By.TAG_NAME, "img")
                image = img.get_attribute("src") or img.get_attribute("data-src") or ""
            except Exception:
                pass

            seen_ids.add(tour_id)
            tours.append({"title": title[:200], "url": url, "image": image})
        except Exception:
            continue

    # Sort high-converters first
    tours.sort(key=lambda t: tour_priority(t["title"]))
    print(f"[+] {city_name}: extracted {len(tours)} unique tours")
    return tours


def save_to_csv(city_name, tours):
    filename = f"getyourguide_{city_name.lower().replace(' ', '_')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "url", "city", "image_url", "description"])
        writer.writeheader()
        for t in tours:
            writer.writerow({
                "title": t["title"],
                "url": t["url"],
                "city": city_name,
                "image_url": t["image"],
                "description": "",
            })
    print(f"[OK] Saved {len(tours)} tours -> {filename}\n")


def main():
    import sys
    cities = sys.argv[1:] if len(sys.argv) > 1 else ["Rome", "London", "Sydney"]
    driver = uc.Chrome(headless=False)
    try:
        for city in cities:
            print(f"\n{'='*50}\n{city.upper()}\n{'='*50}")
            tours = scrape_getyourguide(driver, city)
            if tours:
                save_to_csv(city, tours)
            time.sleep(2)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    print("[+] Done.")


if __name__ == "__main__":
    main()
