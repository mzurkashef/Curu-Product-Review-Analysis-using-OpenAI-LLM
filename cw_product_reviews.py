# chemist_warehouse_reviews.py
import json
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

HOME = "https://www.chemistwarehouse.com.au/"

# ───────────────────────── Driver ─────────────────────────
def create_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

def js_click(driver, el):
    driver.execute_script("arguments[0].click();", el)

# ───────────────────────── Cookies ─────────────────────────
def close_cookies_if_present(driver):
    wait = WebDriverWait(driver, 8)
    selectors = [
        (By.ID, "onetrust-accept-btn-handler"),
        (By.XPATH, "//button[@id='onetrust-accept-btn-handler' or normalize-space()='CLOSE']"),
        (By.CSS_SELECTOR, "button#onetrust-accept-btn-handler, .onetrust-close-btn-handler"),
    ]
    for by, sel in selectors:
        try:
            btn = wait.until(EC.element_to_be_clickable((by, sel)))
            js_click(driver, btn)
            time.sleep(0.2)
            print("[OK] Cookie popup closed")
            return
        except Exception:
            pass
    print("[INFO] No cookie popup found")

# ───────────────────────── Search ─────────────────────────
def get_visible_search_input(driver):
    wait = WebDriverWait(driver, 12)
    candidates = [
        (By.CSS_SELECTOR, "input[data-cy='global-search-input']"),
        (By.CSS_SELECTOR, "input[aria-label='Search']"),
        (By.XPATH, "//input[@type='search' and not(ancestor::*[contains(@class,'hidden')])]"),
    ]
    for by, sel in candidates:
        try:
            el = wait.until(EC.presence_of_element_located((by, sel)))
            wait.until(EC.visibility_of(el))
            if el.is_displayed() and el.size.get("height", 0) > 0 and el.size.get("width", 0) > 0:
                return el
        except Exception:
            continue
    raise TimeoutError("Search input not found / not visible")

def search_and_submit(driver, query: str):
    driver.execute_script("window.scrollTo(0, 0);")
    box = get_visible_search_input(driver)
    box.clear()
    box.send_keys(query)
    try:
        submit = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Open search'], button[type='submit'][aria-label='Search']")
        js_click(driver, submit)
    except Exception:
        box.send_keys(Keys.ENTER)
    print("[OK] Search submitted")

# ───────────────────────── Results → Nth product ─────────────────────────
def nth_non_sponsored_anchor(driver, n: int):
    items = driver.find_elements(By.XPATH, "//li[.//a[contains(@href,'/buy/')]]")
    clean = []
    for li in items:
        if li.find_elements(By.XPATH, ".//span[contains(.,'Sponsored')]"):
            continue
        try:
            a = li.find_element(By.XPATH, ".//a[contains(@href,'/buy/')]")
            clean.append(a)
        except Exception:
            continue
    return clean[n-1] if len(clean) >= n else None

def click_nth_product(driver, n: int):
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul li")))
    time.sleep(1.0)
    a = nth_non_sponsored_anchor(driver, n)
    if not a:
        raise RuntimeError(f"Could not find product #{n}")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", a)
    time.sleep(0.4)
    js_click(driver, a)
    wait.until(EC.url_contains("/buy/"))
    print(f"[OK] Opened product #{n}: {driver.current_url}")

# ───────────────────────── Reviews accordion ─────────────────────────
def click_reviews_dropdown(driver):
    wait = WebDriverWait(driver, 20)
    driver.execute_script("window.scrollBy(0, 1000);")
    time.sleep(0.8)
    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[.//text()[contains(.,'Reviews')]] | //h3[normalize-space()='Reviews']/parent::div/preceding-sibling::button")
        ))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        time.sleep(0.2)
        js_click(driver, btn)
        time.sleep(1.0)
        print("[OK] Reviews section toggled/opened")
    except Exception:
        print("[INFO] Reviews section may already be open")

# ───────────────────────── Robust star text ─────────────────────────
def extract_stars_text(container) -> str:
    """
    Extracts 'X out of 5 stars' for an individual review card.
    """
    # 1) aria-label / title based
    for xp in [
        ".//*[contains(@aria-label,'out of 5')]",
        ".//*[contains(@title,'out of 5')]",
        ".//span[contains(normalize-space(.), 'out of 5')]",
    ]:
        try:
            el = container.find_element(By.XPATH, xp)
            raw = (el.get_attribute("aria-label") or el.get_attribute("title") or el.text or "").strip()
            m = re.search(r'(\d+(?:\.\d+)?)\s*out\s*of\s*5', raw, re.I)
            if m:
                return f"{m.group(1)} out of 5 stars"
        except Exception:
            pass

    # 2) count filled SVGs
    try:
        star_wrappers = container.find_elements(
            By.XPATH,
            ".//div[contains(@class,'flex') and contains(@class,'items-center')][.//*[local-name()='svg']]"
        )
        search_roots = star_wrappers if star_wrappers else [container]

        for root in search_roots:
            filled_svgs = root.find_elements(
                By.XPATH,
                ".//*[local-name()='svg' and not(contains(@class,'opacity-20')) and "
                "("
                " contains(@class,'text-amber') or contains(@class,'fill-amber') or "
                " contains(@class,'text-yellow') or contains(@class,'text-cw-yellow') or "
                " contains(@class,'text-cw-amber') or "
                " @fill='currentColor'"
                ")]"
            )
            if filled_svgs:
                n = min(5, max(0, len(filled_svgs)))
                return f"{float(n):.1f} out of 5 stars"
    except Exception:
        pass

    # 3) unicode stars fallback
    try:
        txt = container.text
        if txt:
            count = txt.count("★") or txt.count("⭐")
            if 0 < count <= 5:
                return f"{float(count):.1f} out of 5 stars"
    except Exception:
        pass

    return ""

# ───────────────────────── Review Summary (avg + total + snapshot) ─────────────────────────
def _find_ratings_snapshot_container(driver):
    xpaths = [
        "//span[normalize-space()='Ratings snapshot']/ancestor::div[contains(@class,'flex-col')][1]",
        "//span[contains(.,'Ratings snapshot')]/ancestor::div[contains(@class,'flex-col')][1]",
        "//div[.//span[contains(.,'Ratings snapshot')]][contains(@class,'flex-col')]",
    ]
    for xp in xpaths:
        els = driver.find_elements(By.XPATH, xp)
        if els:
            return els[0]
    return None

def _extract_ratings_snapshot(container):
    dist = {}
    if not container:
        return dist

    rows = container.find_elements(
        By.XPATH,
        ".//button[.//span[contains(.,'star') or contains(.,'stars')]]"
    )
    for row in rows:
        try:
            label_el = row.find_element(By.XPATH, ".//span[contains(.,'star')]")
            label_txt = label_el.text.strip().lower()

            count_txt = ""
            candidates = row.find_elements(By.XPATH, ".//span[contains(@class,'text-right') or contains(@class,'text-black')]")
            for c in candidates[::-1]:
                m = re.search(r'\d[\d,]*', c.text)
                if m:
                    count_txt = m.group(0).replace(",", "")
                    break
            if not count_txt:
                m = re.search(r'\d[\d,]*', row.text)
                if m:
                    count_txt = m.group(0).replace(",", "")

            if '5 star' in label_txt:
                dist['5 star'] = count_txt
            elif '4 star' in label_txt:
                dist['4 star'] = count_txt
            elif '3 star' in label_txt:
                dist['3 star'] = count_txt
            elif '2 star' in label_txt:
                dist['2 star'] = count_txt
            elif '1 star' in label_txt:
                dist['1 star'] = count_txt
        except Exception:
            continue
    return dist

def extract_product_review_summary(driver):
    summary = {"Average reviews": "", "Total Ratings": "", "reviews_per_star": {}}

    try:
        avg = driver.find_element(
            By.XPATH,
            "(//span[contains(@class,'text') and normalize-space()[string(.)!='']][contains(.,'.')])[1]"
        )
        m = re.search(r'\d+(?:\.\d+)?', avg.text)
        if m:
            summary["Average reviews"] = f"{m.group(0)} out of 5"
    except Exception:
        pass

    try:
        total = driver.find_element(By.XPATH, "//span[contains(.,'Reviews') and contains(.,'review')] | //span[contains(.,'Reviews')]")
        m = re.search(r'\d[\d,]*', total.text)
        if m:
            summary["Total Ratings"] = f"{m.group(0).replace(',', '')} Reviews"
    except Exception:
        pass

    container = _find_ratings_snapshot_container(driver)
    summary["reviews_per_star"] = _extract_ratings_snapshot(container)

    return summary

# ───────────────────────── Review cards ─────────────────────────
def review_cards(driver):
    return driver.find_elements(
        By.XPATH,
        "//h6[contains(@class,'headline') and contains(@class,'title')]/ancestor::div[contains(@class,'flex') and contains(@class,'flex-col')][1]"
    )

def parse_review_card(card):
    def safe_text(el):
        try: return el.text.strip()
        except: return ""

    try:
        title = card.find_element(By.XPATH, ".//h6[contains(@class,'headline') and contains(@class,'title')]").text.strip()
    except Exception:
        title = ""

    try:
        name = card.find_element(By.XPATH, ".//span[contains(@class,'text-colour-body-grey')]").text.strip()
    except Exception:
        name = "Anonymous"

    try:
        date = card.find_element(By.XPATH, ".//span[contains(@class,'text-cw-grey-200')]").text.strip()
    except Exception:
        date = ""

    try:
        body = card.find_element(By.XPATH, ".//p[contains(@class,'text-colour-body-grey') and contains(@class,'body')]").text.strip()
    except Exception:
        body = ""

    stars = extract_stars_text(card)

    return {
        "reviewer_name": name,
        "review_stars": stars,
        "review_title": title,
        "review_date": date,
        "review": body,
    }

NEXT_BTN_XPATH = "/html/body/div[1]/div/div/main/div[2]/div/div[2]/section/div/div[2]/div/div/div/div[4]/div/div/button[2]"

def click_next_reviews_page(driver):
    try:
        next_btn = driver.find_element(By.XPATH, NEXT_BTN_XPATH)
        if next_btn.get_attribute("aria-disabled") == "true":
            return False
        js_click(driver, next_btn)
        time.sleep(2)  # wait after click
        return True
    except Exception:
        return False

def collect_reviews(driver, max_reviews=20):
    time.sleep(1.0)
    got, seen = [], set()
    while len(got) < max_reviews:
        for c in review_cards(driver):
            try:
                r = parse_review_card(c)
                key = (r["reviewer_name"], r["review_date"], r["review_title"], r["review"])
                if key not in seen and any(r.values()):
                    seen.add(key)
                    got.append(r)
                    if len(got) >= max_reviews:
                        return got
            except Exception:
                continue
        if not click_next_reviews_page(driver):  # ✅ click next button
            break
    return got


# ───────────────────────── Save JSON ─────────────────────────
def save_reviews_to_json(records, filename_prefix="chemist_warehouse_reviews"):
    name = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(name, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] {name}")
    return name

# ───────────────────────── Main flow ─────────────────────────
def process_nth_product(driver, n: int, results_url: str, max_reviews=5):
    if driver.current_url != results_url:
        driver.get(results_url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul li")))
        time.sleep(0.6)

    print(f"\n=== Processing product #{n} ===")
    click_nth_product(driver, n)
    click_reviews_dropdown(driver)

    summary = extract_product_review_summary(driver)
    reviews = collect_reviews(driver, max_reviews=max_reviews)

    rec = {
        "retailer": "Chemist Warehouse",
        "title": "",
        "link": driver.current_url,
        "Review Summary": summary,
        "Reviewer Details": {f"customer_review_{i+1:03d}": r for i, r in enumerate(reviews)}
    }
    return rec

def main():
    driver = create_driver()
    records = []
    try:
        driver.get(HOME)
        close_cookies_if_present(driver)

        PRODUCT_TYPES = ["cleanser", "toner", "serum", "moisturizer", "sunscreen"]

        for category in PRODUCT_TYPES:
            print(f"\n=== Processing category: {category} ===")
            search_and_submit(driver, category)

            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul li")))
            time.sleep(0.8)
            results_url = driver.current_url

            for i in range(1, 21):  # first 20 products
                try:
                    print(f"\n=== Processing {category} product #{i} ===")
                    rec = process_nth_product(driver, i, results_url, max_reviews=20)
                    rec["category"] = category   # ✅ add category label
                    records.append(rec)

                    # Reset to results page before next product
                    driver.get(results_url)
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul li")))
                    time.sleep(0.6)
                except Exception as e:
                    print(f"[WARN] Skipping {category} product #{i} due to error: {e}")
                    driver.get(results_url)
                    time.sleep(0.6)

        save_reviews_to_json(records)

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
