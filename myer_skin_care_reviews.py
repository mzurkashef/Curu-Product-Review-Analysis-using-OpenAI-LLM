import json
import time
import re
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_SEARCH_URL = "https://www.myer.com.au/search"
CATEGORIES = ["cleanser", "toner", "serum", "moisturizer", "sunscreen"]

# --- caps ---
PRODUCTS_PER_CATEGORY = 12      # take 10–12
REVIEW_PAGES_MAX = 2            # “do the pagination once” → first page + one “next”
REVIEW_TARGET = 20              # stop early if we already have ~20 reviews

# --- search page behavior ---
RESULTS_MAX_PAGES = 2           # how many search result pages to attempt per category
SCROLL_STEPS = 5                # to trigger lazy load on search pages

# --- waits ---
WAIT_SHORT = 2.0
WAIT_LONG = 5.0

OUTFILE = "myer_skin_care_reviews.json"


# ----------------- utils -----------------
def clean_text(s: Optional[str]) -> Optional[str]:
    if not s: return None
    return re.sub(r"\s+", " ", s).strip() or None

def polite_sleep(sec: float):
    time.sleep(sec)

def get_shadow_root(driver, host_el):
    try:
        return host_el.shadow_root
    except Exception:
        return driver.execute_script("return arguments[0].shadowRoot", host_el)

def safe_attr(el, name: str) -> Optional[str]:
    try:
        return el.get_attribute(name)
    except Exception:
        return None

def safe_text(el) -> Optional[str]:
    try:
        return clean_text(el.text)
    except Exception:
        return None


# ----------------- search page -----------------
def search_url_for(query: str) -> str:
    return f"{BASE_SEARCH_URL}?{urlencode({'query': query})}"

def collect_product_links_for_category(driver, query: str, max_products: int) -> List[str]:
    """
    Navigate search results for a category keyword and collect up to `max_products` product URLs.
    """
    driver.get(search_url_for(query))
    urls: List[str] = []
    pages_done = 0

    while pages_done < RESULTS_MAX_PAGES and len(urls) < max_products:
        # scroll to load cards
        for _ in range(SCROLL_STEPS):
            driver.execute_script("window.scrollBy(0, 1600);")
            polite_sleep(0.6)

        # grab anchors that look like product pages
        for a in driver.find_elements(By.CSS_SELECTOR, 'a[href*="/p/"]'):
            href = safe_attr(a, "href")
            if href and "/p/" in href:
                href = href.split("?")[0]
                if href not in urls:
                    urls.append(href)
                    if len(urls) >= max_products:
                        break

        if len(urls) >= max_products:
            break

        # try rel=next or a visual next link
        next_href = None
        try:
            rel = driver.find_element(By.CSS_SELECTOR, 'link[rel="next"]')
            nh = safe_attr(rel, "href")
            if nh:
                next_href = nh
        except Exception:
            pass

        if not next_href:
            try:
                btn = driver.find_element(By.XPATH, '//a[contains(@aria-label,"Next") or normalize-space()="Next"]')
                nh = safe_attr(btn, "href")
                if nh:
                    next_href = nh
            except Exception:
                next_href = None

        if not next_href:
            break

        driver.get(next_href)
        polite_sleep(WAIT_LONG)
        pages_done += 1

    return urls[:max_products]


# ----------------- product page parsing -----------------
@dataclass
class Review:
    title: Optional[str]
    body: Optional[str]
    rating: Optional[float]
    source: str = "dom"

def click_reviews_tab_if_present(driver):
    for xp in [
        '//button[contains(.,"Reviews")]',
        '//a[contains(.,"Reviews")]',
        '//*[@role="tab" and contains(., "Reviews")]'
    ]:
        try:
            el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            polite_sleep(0.3)
            el.click()
            polite_sleep(WAIT_SHORT)
            return
        except Exception:
            pass

def wait_for_bv_shadow(driver) -> Optional[Any]:
    try:
        host = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-automation="bazaar-voice-reviews"]'))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", host)
        polite_sleep(0.4)
        return get_shadow_root(driver, host)
    except Exception:
        return None

def parse_reviews_on_current_page(shadow_root) -> List[Review]:
    out: List[Review] = []
    try:
        items = shadow_root.find_elements(By.CSS_SELECTOR, 'section[id^="bv-review-"]')
    except Exception:
        items = []

    for it in items:
        # rating
        rating = None
        try:
            aria = it.find_element(By.CSS_SELECTOR, '[role="img"][aria-label*="out of 5"]')
            label = safe_attr(aria, "aria-label") or ""
            m = re.search(r'([0-5](?:\.\d)?)\s*out of 5', label, flags=re.I)
            if m:
                rating = float(m.group(1))
        except Exception:
            pass

        # title
        title = None
        for sel in ['h3[itemprop="name"]', '[itemprop="name"]']:
            try:
                el = it.find_element(By.CSS_SELECTOR, sel)
                title = safe_text(el)
                if title:
                    break
            except Exception:
                pass

        # body
        body = None
        try:
            el = it.find_element(By.CSS_SELECTOR, '[itemprop="reviewBody"]')
            body = safe_text(el)
        except Exception:
            pass


        if title or body:
            out.append(Review(title, body, rating))

    return out

def get_next_reviews_href(shadow_root) -> Optional[str]:
    try:
        btns = shadow_root.find_elements(By.CSS_SELECTOR, 'a.next[role="button"], a.next')
        for b in btns:
            disabled = (safe_attr(b, "aria-disabled") or "").lower()
            if disabled in ("true", "1"):
                continue
            href = safe_attr(b, "href")
            if href and "bvstate=pg:" in href:
                return href
    except Exception:
        pass
    return None

def extract_price_from_jsonld(driver) -> Optional[str]:
    """
    Try to read price from JSON-LD Product->offers->price (if present).
    """
    try:
        scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
        for s in scripts:
            raw = s.get_attribute("textContent") or ""
            # Avoid full JSON parsing (some blocks may be huge/invalid). Quick sniff:
            if '"@type"' not in raw or '"Product"' not in raw:
                continue
            # Lightweight extract for price fields
            m = re.search(r'"price"\s*:\s*"?([\d\.,]+)"?', raw)
            if m:
                return m.group(1)
            # Some sites nest offers list
            m2 = re.search(r'"priceCurrency"\s*:\s*".{1,3}".{0,80}?"price"\s*:\s*"?([\d\.,]+)"?', raw, flags=re.S)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return None

def extract_price_from_dom(driver) -> Optional[str]:
    """
    DOM fallbacks for price: itemprop=price, data-automation*price, or classes containing 'price'.
    """
    # itemprop="price"
    for sel in ['[itemprop="price"]', 'meta[itemprop="price"]']:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            val = safe_attr(el, "content") if el.tag_name.lower() == "meta" else safe_text(el)
            if val:
                # extract first number-like token
                m = re.search(r'[\$]?\s*([\d\.,]+)', val)
                if m:
                    return m.group(1)
        except Exception:
            pass
    # data-automation and class fallbacks
    for sel in ['[data-automation*="price"]', '[class*="price"]']:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = safe_text(el)
            if txt:
                m = re.search(r'[\$]?\s*([\d\.,]+)', txt)
                if m:
                    return m.group(1)
        except Exception:
            pass
    return None

def extract_product_name(driver) -> Optional[str]:
    # 1) JSON-LD Product.name
    try:
        scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
        for s in scripts:
            raw = s.get_attribute("textContent") or ""
            if '"@type"' in raw and '"Product"' in raw:
                m = re.search(r'"name"\s*:\s*"([^"]+)"', raw)
                if m:
                    return clean_text(m.group(1))
    except Exception:
        pass

    # 2) Common DOM headings (wait a bit in case it’s lazy)
    try:
        h = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h1, h2, [data-automation*="title"], [class*="product-title"]'))
        )
        txt = clean_text(h.text)
        if txt:
            return txt
    except Exception:
        pass

    # 3) OpenGraph title (often "Product Name | MYER")
    try:
        el = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:title"], meta[name="og:title"]')
        ogt = el.get_attribute("content")
        if ogt:
            ogt = clean_text(ogt)
            # Trim common suffix
            ogt = re.sub(r"\s*\|\s*MYER.*$", "", ogt, flags=re.I)
            return ogt
    except Exception:
        pass

    # 4) <title> tag as final fallback
    try:
        t = driver.title or ""
        t = clean_text(t)
        if t:
            t = re.sub(r"\s*\|\s*MYER.*$", "", t, flags=re.I)
            return t
    except Exception:
        pass

    return None

def scrape_product(driver, product_url: str, product_type: str) -> Dict[str, Any]:
    driver.get(product_url)
    polite_sleep(WAIT_LONG)

    # Basic meta
    name = extract_product_name(driver)

    # Price (JSON-LD first, then DOM)
    price = extract_price_from_jsonld(driver) or extract_price_from_dom(driver)

    # Reviews (open tab, get shadow root)
    click_reviews_tab_if_present(driver)
    shadow_root = wait_for_bv_shadow(driver)
    if not shadow_root:
        # scroll bottom & retry once
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        polite_sleep(2)
        shadow_root = wait_for_bv_shadow(driver)

    all_reviews: List[Dict[str, Any]] = []
    page_no = 1
    while shadow_root and page_no <= REVIEW_PAGES_MAX and len(all_reviews) < REVIEW_TARGET:
        for r in parse_reviews_on_current_page(shadow_root):
            all_reviews.append(asdict(r))
            if len(all_reviews) >= REVIEW_TARGET:
                break
        if len(all_reviews) >= REVIEW_TARGET:
            break

        next_href = get_next_reviews_href(shadow_root)
        if not next_href:
            break

        driver.get(next_href)
        polite_sleep(WAIT_LONG)
        click_reviews_tab_if_present(driver)
        shadow_root = wait_for_bv_shadow(driver)
        page_no += 1

    return {
        "product_url": product_url,
        "product_type": product_type,      # ← added for clear identification
        "product_name": name,
        "price": price,
        "reviews_collected": len(all_reviews),
        "reviews": all_reviews
    }


# ----------------- driver & main -----------------
def build_driver(headless: bool = False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,1000")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-AU")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(50)
    return driver

def main():
    driver = build_driver(headless=False)  # set True once stable
    try:
        out = {
            "search": {
                "categories": CATEGORIES,
                "base": BASE_SEARCH_URL,
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "products": []
        }

        for cat in CATEGORIES:
            print(f"\n=== Category: {cat} ===")
            links = collect_product_links_for_category(driver, cat, PRODUCTS_PER_CATEGORY)
            print(f"Found {len(links)} product URLs for '{cat}'")

            for i, url in enumerate(links, 1):
                print(f"  [{i}/{len(links)}] {url}")
                try:
                    prod = scrape_product(driver, url, product_type=cat)
                    out["products"].append(prod)
                except Exception as e:
                    print(f"    [!] Failed {url}: {e}")

        Path(OUTFILE).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[saved] {OUTFILE}  products={len(out['products'])}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()