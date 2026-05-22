#!/usr/bin/env python3
"""Seed the Nzuri Couture catalog from Instagram.

Pulls the top N posts from @nzuri.couture via the worker's feed endpoint
(/api/ig-feed -> IG /api/v1/feed/user/<id>/), parses each caption for a product
name / category / sizes / price, SKIPS posts whose caption yields no real name
(promo / "open for deliveries" posts -> no placeholder entries), then commits
the kept items through /api/ig-sync (which downloads the images server-side).

Usage:
  python tools/seed_from_ig.py --dry        # parse + print summary, no writes
  python tools/seed_from_ig.py              # parse + commit to the catalog
"""
import json, re, sys, time, urllib.request, urllib.error, os

BASE = "https://nzuri-couture-api.stawisystems.workers.dev"
USER_ID = "2097490880"  # nzuri.couture
CAP = 150
MAX_IMAGES = 3
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
DRY = "--dry" in sys.argv

HERE = os.path.dirname(os.path.abspath(__file__))
creds = open(os.path.join(HERE, "..", "worker", ".secrets_tmp", "creds.env")).read()
TOKEN = re.search(r'(?m)^TOKEN=(\S+)$', creds).group(1)

# A line that is *dominated* by one of these is an announcement, not a product.
PURE_PROMO = re.compile(
    r'\b(new in|open for|hit us up|dm us|dm me|same day|to order|thank you|'
    r'reminder|appreciation|polite|client|offer|giveaway|back in stock|welcome|'
    r'happy|merry|closed|reopen|now open|congratulation|deliver|in stock|restock|'
    r'enquir|inbox|whatsapp|call us|order now|shop now|all pieces|few pieces|'
    r'available to order|week ahead|looking to|with love|good morning|'
    r'good afternoon|good evening|happy new|new week|this week|elevate your|'
    r'tap the link|link in bio|swipe)\b', re.I)
GENERIC_NAME = {'piece', 'pieces', 'item', 'items', 'look', 'style', 'outfit',
                'restock', 'available', 'new', 'sale', 'offer', 'order'}
# A product name ends where one of these stock/size/price markers begins.
NAME_CUT = re.compile(
    r'\b(remaining|available|sizes?|only|few\b|pcs|pieces?\s+left|piece\s+left|'
    r'ksh|kshs|price|now\b|left\b)\b', re.I)
PROMO = PURE_PROMO  # used for description filtering
SIZE_CTX = re.compile(r'\b(size|sizes|available in)\b', re.I)
SIZE_LIST = re.compile(r'^\s*((xs|s|m|l|xl|xxl|3xl)\s*[,/|]\s*)+(xs|s|m|l|xl|xxl|3xl)\s*$', re.I)
LETTER_SIZE = re.compile(r'\b(XS|XXL|XXXL|3XL|XL|S|M|L)\b')
SMALL = {'and', 'or', 'the', 'of', 'in', 'with', 'a', 'to', 'for'}


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def http_post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def clean_ascii(s):
    s = re.sub(r'[^\x00-\x7F]+', ' ', s or '')   # strip emojis / non-latin
    return re.sub(r'[ \t]+', ' ', s)


def strip_phone(s):
    return re.sub(r'(\+?254|0)\d{8,11}', ' ', s)


def smart_title(s):
    out = []
    for i, w in enumerate(s.split()):
        lw = w.lower()
        out.append(lw if (i > 0 and lw in SMALL) else (w[:1].upper() + w[1:]))
    return ' '.join(out)


def categorize(text):
    # Prefix matches (no trailing \b) so plurals like "hats", "shoes", "dresses" hit.
    t = text.lower()
    if re.search(r'\b(two\s*piece|2\s*piece|co-?ord|matching set)', t): return 'Two-Piece Sets'
    if re.search(r'\b(jumpsuit|romper|playsuit|catsuit|dungaree)', t): return 'Jumpsuits'
    if re.search(r'\b(dress|gown|bodycon|frock|kaftan|abaya)', t): return 'Dresses'
    if re.search(r'\bskirt', t): return 'Skirts'
    if re.search(r'\b(trouser|pant|jean|legging|culotte|cargo|short|skort)', t): return 'Trousers'
    if re.search(r'\b(blazer|coat|jacket|trench|bomber|kimono)', t): return 'Outerwear'
    if re.search(r'\b(sweater|knit|jumper|pullover|cardigan)', t): return 'Knitwear'
    if re.search(r'\b(shoe|heel|sandal|boot|sneaker|mule|wedge|pump|loafer|flats?\b)', t): return 'Shoes'
    if re.search(r'\b(bag|handbag|clutch|tote|purse|crossbody|backpack)', t): return 'Bags'
    if re.search(r'\b(hats?\b|caps?\b|belts?\b|scarf|scarves|jewel|necklace|earring|sunglass|bangle|accessor)', t): return 'Accessories'
    if re.search(r'\b(top|blouse|crop|cami|bodysuit|tee|t-shirt|shirt|poncho|kimono)', t): return 'Tops'
    return 'Tops'


def parse_caption(cap, category_hint=None):
    """Return dict(name, stock, price, description) or None to skip."""
    ascii_cap = clean_ascii(cap)
    raw_lines = [l.strip(" .•-*\t") for l in ascii_cap.splitlines()]
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return None

    # ---- name: first content line that yields a real product name ----
    # A line dominated by a promo phrase is an announcement -> skip the post.
    # Otherwise truncate the line at the first stock/size/price marker so
    # "Silk Cream Dress Remaining in Ls" -> "Silk Cream Dress".
    name = None
    for l in lines:
        letters = re.sub(r'[^A-Za-z]', '', l)
        if len(letters) < 4:
            continue
        if PURE_PROMO.search(l):
            return None  # leads with an announcement, not a product
        cand = NAME_CUT.split(l, maxsplit=1)[0].strip(" .,-:|/")
        cand = re.sub(r'\s+', ' ', cand)
        cand_letters = re.sub(r'[^A-Za-z]', '', cand)
        if len(cand_letters) < 4 or not re.search(r'[A-Za-z]{3,}', cand):
            return None  # first content line is a stock note -> not a product
        if len(cand.split()) == 1 and cand.lower() in GENERIC_NAME:
            return None  # bare "Piece" / "Item" etc. -> not a product name
        name = smart_title(cand)[:80]
        break
    if not name:
        return None

    # ---- sizes -> stock ----
    stock = {}
    size_line = next((l for l in lines if SIZE_CTX.search(l)), None)
    if not size_line:
        size_line = next((l for l in lines if SIZE_LIST.match(l)), None)
    if size_line:
        for s in LETTER_SIZE.findall(size_line.upper()):
            stock[s] = 1
        for n in re.findall(r'\b(3[5-9]|4[0-6]|[6-9]|1[0-8])\b', size_line):
            stock[n] = 1  # numeric (dress / EU shoe) sizes
    # cap to a sane set; drop accidental tiny numbers handled by ranges above

    # ---- price ----
    price = 0
    no_phone = strip_phone(ascii_cap)
    for c in re.findall(r'\b(\d{1,3}(?:,\d{3})+|\d{3,6})\b', no_phone):
        v = int(c.replace(',', ''))
        if 200 <= v <= 300000:
            price = v
            break

    # ---- description ----
    desc_lines = [l for l in lines if not PROMO.search(l)]
    desc = strip_phone(' '.join(desc_lines))
    desc = re.sub(r'\s+', ' ', desc).replace('—', ', ').replace('–', '-').strip(' .,-')
    desc = desc[:240] or None

    return {"name": name, "stock": stock, "price": price, "description": desc}


def http_get_retry(url, tries=3):
    for attempt in range(tries):
        try:
            return http_get(url)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            wait = 4 * (attempt + 1)
            print(f"    fetch error ({e}); retry in {wait}s")
            time.sleep(wait)
    return None


def fetch_posts():
    posts, seen, max_id = [], set(), ""
    for page in range(16):
        url = f"{BASE}/api/ig-feed?user_id={USER_ID}&count=50"
        if max_id:
            url += f"&max_id={urllib.parse.quote(max_id)}"
        data = http_get_retry(url)
        if not data:
            print(f"  page {page+1}: giving up, continuing with {len(posts)} posts")
            break
        items = data.get("items") or []
        for it in items:
            sc = it.get("shortcode")
            if sc and sc not in seen:
                seen.add(sc)
                posts.append(it)
        print(f"  page {page+1}: +{len(items)} (total {len(posts)})")
        if len(posts) >= CAP or not data.get("more_available") or not data.get("next_max_id"):
            break
        max_id = data["next_max_id"]
        time.sleep(2.5)
    return posts[:CAP]


def main():
    cache = os.path.join(HERE, "..", ".tmp", "ig_posts.json")
    if os.path.exists(cache) and "--refetch" not in sys.argv:
        posts = json.load(open(cache, encoding="utf-8"))
        print(f"Loaded {len(posts)} posts from cache ({cache}). Use --refetch to re-pull.\n")
    else:
        print(f"Fetching up to {CAP} posts from @nzuri.couture ...")
        posts = fetch_posts()
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump(posts, open(cache, "w", encoding="utf-8"))
        print(f"Fetched {len(posts)} posts (cached).\n")

    kept, skipped = [], 0
    for it in posts:
        parsed = parse_caption(it.get("caption") or "")
        if not parsed:
            skipped += 1
            continue
        imgs = (it.get("imageUrls") or ([it["imageUrl"]] if it.get("imageUrl") else []))[:MAX_IMAGES]
        if not imgs:
            skipped += 1
            continue
        cat = categorize(parsed["name"] + " " + (it.get("caption") or ""))
        kept.append({
            "shortcode": it["shortcode"],
            "name": parsed["name"],
            "category": cat,
            "stock": parsed["stock"],
            "price": parsed["price"],
            "description": parsed["description"],
            "imageUrls": imgs,
            "takenAt": it.get("takenAt"),
        })

    print(f"KEPT {len(kept)}  ·  SKIPPED {skipped} (no usable name / promo / no image)\n")
    from collections import Counter
    by_cat = Counter(k["category"] for k in kept)
    print("By category:", dict(by_cat))
    priced = sum(1 for k in kept if k["price"] > 0)
    sized = sum(1 for k in kept if k["stock"])
    print(f"With price: {priced}/{len(kept)}   With sizes: {sized}/{len(kept)}\n")
    print("Sample (first 12):")
    for k in kept[:12]:
        print(f"  - {k['name'][:46]:46} | {k['category']:15} | "
              f"Ksh {k['price'] or '-':>6} | {','.join(k['stock'].keys()) or 'one size'}")

    if DRY:
        print("\n[dry run] no writes performed.")
        return

    print(f"\nCommitting {len(kept)} items to /api/ig-sync in batches of 12 ...")
    added = errs = 0
    for i in range(0, len(kept), 12):
        batch = kept[i:i+12]
        try:
            res = http_post(f"{BASE}/api/ig-sync", {"items": batch})
            added += res.get("added", 0)
            be = res.get("errors") or []
            errs += len(be)
            print(f"  batch {i//12+1}: added {res.get('added',0)}, errors {len(be)}")
            if be:
                for e in be[:3]:
                    print(f"      ! {e}")
        except urllib.error.HTTPError as e:
            print(f"  batch {i//12+1}: HTTP {e.code} {e.read().decode()[:200]}")
        time.sleep(1.5)
    print(f"\nDone. Added {added}, errors {errs}.")


if __name__ == "__main__":
    main()
