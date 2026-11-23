"""Live flyer + online shelf prices from Flipp's public search back end.

One GET per (search term, postal code). Returns flyer items (this week's ad
prices with validity dates) and ecom items (everyday online prices, mostly
Walmart and a few others). No key required. Be polite: throttle requests.
"""
import json
import time
import urllib.parse
import urllib.request

from .. import units
from ..catalog import ITEMS, match

URL = "https://backflipp.wishabi.com/flipp/items/search"
UA = "Mozilla/5.0 (GRX grocery price research; +https://github.com/)"


def fetch(term, postal, timeout=25):
    q = urllib.parse.urlencode({"locale": "en-ca", "postal_code": postal, "q": term})
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def rows_from(payload, item, fsa, dist_km, seen_at):
    """Normalise one search response into price rows for one catalog item."""
    out = []
    for it in payload.get("items") or []:
        name = it.get("name") or ""
        if not name or not match(name, item):
            continue
        price = units.effective_price(it.get("current_price"), it.get("pre_price_text"))
        up = units.unit_price(price, item["unit"], name, "", it.get("post_price_text") or "")
        assumed = False
        if up is None and item.get("default") and price:
            up, assumed = price / item["default"], True
        if up is None:
            continue
        out.append({
            "item": item["id"], "kind": "flyer", "merchant": (it.get("merchant_name") or "").strip(),
            "name": name.strip(), "price": round(price, 2), "unit_price": round(up, 4),
            "pre": it.get("pre_price_text"), "post": it.get("post_price_text"),
            "story": it.get("sale_story"), "valid_from": (it.get("valid_from") or "")[:10],
            "valid_to": (it.get("valid_to") or "")[:10], "flyer_id": it.get("flyer_id"),
            "flipp_id": it.get("id"), "image": it.get("clean_image_url") or it.get("image_url"),
            "fsa": fsa, "km": dist_km, "seen": seen_at, "assumed": assumed, "pack": round(price / up, 3),
        })
    for it in payload.get("ecom_items") or []:
        name = it.get("name") or ""
        if not name or not match(name, item):
            continue
        price = units.money(it.get("current_price"))
        up = units.unit_price(price, item["unit"], name)
        if up is None:
            continue
        orig = units.money(it.get("original_price"))
        out.append({
            "item": item["id"], "kind": "online", "merchant": (it.get("merchant") or "").strip(),
            "name": name.strip(), "price": round(price, 2), "unit_price": round(up, 4),
            "was": orig if orig and orig > price else None, "sku": it.get("sku"),
            "image": it.get("image_url"), "fsa": fsa, "km": dist_km, "seen": seen_at, "pack": round(price / up, 3),
        })
    return out


def collect(fsas, items=ITEMS, sleep=0.6, log=print, fetcher=fetch):
    """fsas: [(fsa, km)]. Returns list of rows, deduplicated."""
    seen_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows, keys, errors = [], set(), 0
    for fsa, dist in fsas:
        postal = fsa + "1A1"
        for item in items:
            for term in item["terms"][:1] if dist > 0 else item["terms"]:
                try:
                    payload = fetcher(term, postal)
                except Exception as e:  # network hiccups should not kill a sweep
                    errors += 1
                    log(f"  ! {fsa} {term}: {e}")
                    time.sleep(2)
                    continue
                for r in rows_from(payload, item, fsa, dist, seen_at):
                    k = (r["item"], r["kind"], r["merchant"], r["name"], r["price"], r.get("valid_from"))
                    if k in keys:
                        continue
                    keys.add(k)
                    rows.append(r)
                time.sleep(sleep)
        log(f"  {fsa} ({dist} km): {len(rows)} rows so far")
    return rows, errors
