# mecca_skin_care_reviews.py
from __future__ import annotations
import re, json, time, datetime as dt
from typing import List, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException
from webdriver_manager.chrome import ChromeDriverManager

# -------- CONFIG --------
BASE = "https://www.mecca.com"
CATEGORIES = ["cleanser", "toner", "serum", "moisturizer", "sunscreen"]
PRODUCTS_PER_CATEGORY = 12
REVIEWS_PER_PRODUCT = 20
HEADLESS = False
OUTFILE = "mecca_skin_care_reviews.json"
SCROLL_ATTEMPTS = 40
SCROLL_SLEEP = 1.2
# ------------------------

# ---------- driver ----------
def make_driver():
    opts = webdriver.ChromeOptions()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,1024")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        })
    except Exception:
        pass
    return driver

def wait_body(driver, timeout=20):
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

def close_banners(driver):
    for xp in [
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//button[contains(.,'Got it')]",
        "//button[contains(.,'Close')]",
    ]:
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
            break
        except TimeoutException:
            pass

# ---------- search page ----------
def js_collect_tiles(driver) -> List[dict]:
    script = """
      const tiles = Array.from(document.querySelectorAll("div[data-testid='ProductTile']"));
      return tiles.map(t => {
        const titleWrap = t.querySelector("div[data-testid='ProductTitle']");
        const a = titleWrap ? titleWrap.querySelector("a") : null;
        const name = a ? a.textContent.trim() : null;
        const href = a ? a.href : null;
        let brand = null;
        if (titleWrap && titleWrap.previousElementSibling && titleWrap.previousElementSibling.tagName === 'P') {
          brand = titleWrap.previousElementSibling.textContent.trim();
        }
        let price = null;
        const texts = [];
        t.querySelectorAll("p, span, div").forEach(el => {
          const txt = (el.textContent||'').trim();
          if (txt && txt.includes('$') && txt.length <= 40) texts.push(txt);
        });
        texts.sort((a,b) => a.length - b.length);
        price = texts.length ? texts[0] : null;
        return {href, name, brand, price};
      }).filter(x => x.href);
    """
    try:
        return driver.execute_script(script)
    except JavascriptException:
        return []

def collect_product_tiles(driver, term: str, max_tiles: int) -> List[dict]:
    driver.get(f"{BASE}/en-au/search/?searchTerm={term}")
    wait_body(driver)
    close_banners(driver)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='search-product-tabs']"))
        )
    except TimeoutException:
        pass

    results, seen = [], set()
    attempts, last_h = 0, 0

    while len(results) < max_tiles and attempts < SCROLL_ATTEMPTS:
        tiles = js_collect_tiles(driver)
        if not tiles:
            try:
                tiles = driver.execute_script("""
                  const sel = "div[data-testid='ProductTile'] a[href*='/en-au/']";
                  return Array.from(document.querySelectorAll(sel)).map(a => ({
                    href:a.href, name:(a.textContent||'').trim(), brand:null, price:null
                  })).filter(t=>t.href);
                """)
            except JavascriptException:
                tiles = []

        for t in tiles:
            if t["href"] not in seen and (t.get("name") or "").strip():
                seen.add(t["href"])
                results.append(t)
                if len(results) >= max_tiles:
                    break

        if len(results) >= max_tiles:
            break

        driver.execute_script("window.scrollBy(0, Math.max(1200, window.innerHeight*0.95));")
        time.sleep(SCROLL_SLEEP)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h and attempts % 3 == 2:
            driver.execute_script("window.scrollBy(0, -350);")
            time.sleep(0.6)
        last_h = new_h
        attempts += 1

    if not results:
        try:
            el = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@data-testid='ProductTile']//a[@href and contains(@href,'/en-au/')]"))
            )
            href = el.get_attribute("href")
            name = el.text.strip() or "Unknown product"
            results = [{"href": href, "name": name, "brand": None, "price": None}]
        except Exception:
            pass

    return results[:max_tiles]

# ---------- PDP meta (brand/name/price) ----------
def _jsonld_meta(driver) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
        for s in scripts:
            txt = s.get_attribute("textContent") or ""
            for block in re.findall(r"\{.*?\}|\[.*?\]", txt, flags=re.DOTALL):
                try: data = json.loads(block)
                except Exception: continue
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if not isinstance(it, dict): continue
                    t = it.get("@type")
                    if (t in {"Product","product"} or (isinstance(t, list) and "Product" in t)) and it.get("name"):
                        name = it.get("name")
                        b = it.get("brand")
                        brand = b.get("name") if isinstance(b, dict) else (b if isinstance(b, str) else None)
                        price = None
                        off = it.get("offers")
                        if isinstance(off, dict):
                            price = off.get("price") or (off.get("priceSpecification") or {}).get("price")
                        elif isinstance(off, list) and off:
                            o0 = off[0]
                            if isinstance(o0, dict):
                                price = o0.get("price") or (o0.get("priceSpecification") or {}).get("price")
                        if price and not str(price).strip().startswith("$"):
                            price = f"${price}"
                        return brand, name, price
    except Exception:
        pass
    return None, None, None

def _brand_from_url(url: str) -> Optional[str]:
    try:
        path = url.split("/en-au/")[1]
        brand_slug = path.split("/")[0]
        if brand_slug:
            return " ".join([w.capitalize() for w in re.split(r"[-\s]+", brand_slug)])
    except Exception:
        pass
    return None

def get_pdp_meta_via_selenium(driver, fb_brand, fb_name, fb_price, url) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    jb, jn, jp = _jsonld_meta(driver)
    brand, name, price = jb or fb_brand, jn or fb_name, jp or fb_price
    try:
        h1 = driver.find_element(By.XPATH, "//h1[normalize-space()]")
        t = h1.text.strip()
        if t: name = t
    except NoSuchElementException:
        pass
    if not brand or (name and brand and brand.strip().lower() == name.strip().lower()):
        brand = _brand_from_url(url) or brand
    if not price:
        try:
            cand = driver.find_elements(By.XPATH, "//*[self::span or self::p or self::div][contains(., '$') and string-length(normalize-space())<=40]")
            texts = [c.text.strip() for c in cand if c.text.strip()]
            texts = [t for t in texts if re.search(r"\$\s*\d", t)]
            texts.sort(key=len)
            price = texts[0] if texts else None
        except Exception:
            pass
    return brand, name, price

# ---------- Reviews via in-page JS over DOM (title/body/rating) ----------
def extract_reviews_inpage(driver, need: int = 20) -> list[dict]:
    script = """
      const done = arguments[0];
      const NEED = %NEED%;
      const wait = (ms)=>new Promise(r=>setTimeout(r, ms));

      const cleanBody = (t) => (t||'').replace(/\\bRead\\s+more\\b/gi,'').replace(/\\bRead\\s+less\\b/gi,'').trim();

      const scrollToReviews = async () => {
        const ugc = document.querySelector("#ugc-form");
        if (ugc) { ugc.scrollIntoView({block:'center'}); await wait(600); }
        window.scrollBy(0, 360);
        await wait(400);
      };

      const clickLoadMore = async () => {
        const candidates = Array.from(document.querySelectorAll("button"));
        const btn = candidates.find(b => {
          const txt = (b.textContent || "").trim();
          const spanTxt = Array.from(b.querySelectorAll("span")).map(s => (s.textContent||"").trim()).join(" ");
          return /read\\s+more\\s+reviews/i.test(txt) || /read\\s+more\\s+reviews/i.test(spanTxt);
        });
        if (!btn || btn.disabled) return false;
        btn.scrollIntoView({block:'center'});
        await wait(180);
        try { btn.click(); } catch(e) { try { btn.dispatchEvent(new MouseEvent('click', {bubbles:true})); } catch(_){} }
        await wait(1400);
        return true;
      };

      const expandAllCards = async () => {
        const triggers = Array.from(document.querySelectorAll("#ugc-form button, #ugc-form a"))
          .filter(el => /read\\s+more/i.test(el.textContent||""));
        for (const el of triggers) {
          try { el.click(); await wait(120); } catch(e){}
        }
      };

      const pickTitle = (node) => {
        const t1 = node.querySelector("div.css-7qt0pw > span");
        if (t1 && t1.textContent.trim()) return t1.textContent.trim();
        const sp = Array.from(node.querySelectorAll("span"))
          .map(s => (s.textContent||"").trim())
          .find(tx => tx && !/read\\s+more|read\\s+less/i.test(tx) && tx.length<=100);
        return sp || null;
      };

      const pickBody = (node) => {
        const reg = node.querySelector("[data-testid='mui-expandable-copy'] [role='region']");
        if (reg && reg.textContent.trim()) return cleanBody(reg.textContent);
        const textBlocks = Array.from(node.querySelectorAll("p, div"))
          .map(e => (e.textContent||"").trim())
          .filter(t => t && t.length > 30 && !/like review|dislike review|report|recommends this product/i.test(t));
        if (textBlocks.length) {
          textBlocks.sort((a,b)=>b.length-a.length);
          return cleanBody(textBlocks[0]);
        }
        return null;
      };

      const pickRating = (node) => {
        const numSpan = node.querySelector("span.css-13q2n6h");
        if (numSpan) {
          const txt = (numSpan.textContent || "").replace(/[()]/g, "").trim();
          const m = txt.match(/\\d+(?:\\.\\d+)?/);
          if (m) return parseFloat(m[0]);
        }
        const aria = node.querySelector("[aria-label*='out of 5'],[aria-label*='out of five']");
        if (aria && aria.getAttribute) {
          const lab = aria.getAttribute("aria-label") || "";
          const m = lab.match(/(\\d+(?:\\.\\d+)?)\\s*out\\s*of\\s*5/i);
          if (m) return parseFloat(m[1]);
        }
        return null;
      };

      const collect = () => {
        const arts = Array.from(document.querySelectorAll("#ugc-form section article"));
        const out = [];
        for (const art of arts) {
          const node = art.querySelector("div.css-1q22pos") || art;
          const body = pickBody(node);
          if (!body) continue;
          const title = pickTitle(node);
          const rating = pickRating(node);
          out.push({title, body, rating});
        }
        return out;
      };

      (async () => {
        try {
          await scrollToReviews();
          let seen = 0, tries = 0;
          while (collect().length < NEED && tries < 10) {
            const clicked = await clickLoadMore();
            await expandAllCards();
            const now = collect().length;
            if (!clicked && now === seen) break;
            seen = now; tries += 1;
          }
          await expandAllCards();
          const all = collect().slice(0, NEED);
          done({ok:true, reviews: all});
        } catch (e) {
          done({ok:false, error: String(e)});
        }
      })();
    """.replace("%NEED%", str(need))

    result = driver.execute_async_script(script)
    if isinstance(result, dict) and result.get("ok"):
        return result.get("reviews") or []
    return []

def go_to_reviews_block(driver):
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1200);")
    except Exception:
        pass
    try:
        ugc = WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.XPATH, "//div[@id='ugc-form']")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ugc)
    except TimeoutException:
        pass
    time.sleep(0.8)

# ---------- Orchestration per product ----------
def combine_product_name(brand: Optional[str], name: Optional[str]) -> Optional[str]:
    if brand and name:
        # avoid duplicating brand if PDP h1 already includes it
        return name if name.lower().startswith(brand.lower()) else f"{brand} {name}"
    return name or brand

def scrape_one_product(driver, tile: dict, product_type: str, need_reviews=20) -> dict:
    url = tile["href"]
    driver.get(url); wait_body(driver); close_banners(driver)

    brand, name, price = get_pdp_meta_via_selenium(driver, tile.get("brand"), tile.get("name"), tile.get("price"), url)
    product_name = combine_product_name(brand, name)

    go_to_reviews_block(driver)
    reviews = extract_reviews_inpage(driver, need=need_reviews)
    if not reviews:
        time.sleep(1.0)
        reviews = extract_reviews_inpage(driver, need=need_reviews)

    reviews = [{"title": r.get("title"), "body": r.get("body"), "rating": r.get("rating")} for r in reviews]

    return {
        "product_url": url,
        "product_type": product_type,
        "product_name": product_name,
        "price": price,
        "reviews_collected": len(reviews),
        "reviews": reviews,  # [{title, body, rating}]
    }

# ---------- Main across categories ----------
def main():
    driver = make_driver()
    products = []
    try:
        for cat in CATEGORIES:
            print(f"\n=== Category: {cat} ===")
            tiles = collect_product_tiles(driver, cat, PRODUCTS_PER_CATEGORY)
            if not tiles:
                print(f"[{cat}] No tiles found.")
                continue
            for i, t in enumerate(tiles, 1):
                print(f"[{cat} {i}/{len(tiles)}] {t['name']} -> {t['href']}")
                products.append(scrape_one_product(driver, t, cat, REVIEWS_PER_PRODUCT))
    finally:
        driver.quit()

    data = {
        "search": {
            "categories": CATEGORIES,
            "base": f"{BASE}/en-au/search",
            "scraped_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "products": products
    }
    with open(OUTFILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved → {OUTFILE}  | products: {len(products)}")

if __name__ == "__main__":
    main()
