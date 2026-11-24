"""In-store prices from Open Prices (Open Food Facts), an open crowdsourced database.

Shoppers upload receipts and shelf-tag photos as proof; every price has a
store (an OpenStreetMap shop), a date and the proof. The data is open
(ODbL) and the API is meant for reuse, so this is store-level, in-store
pricing with no scraping. GRX asks for every price recorded within the
radius in the last N days.

API: https://prices.openfoodfacts.org/api/v1/prices  (filters lat, lon,
radius_km, currency, date__gte; ordering order_by; pagination page/size<=100)
Attribution: "Price data from Open Prices (Open Food Facts), ODbL".
"""
import datetime as dt
import json
import time
import urllib.parse
import urllib.request

from .. import geo, units
from ..catalog import BY_ID, ITEMS, match, plausible
from ..chains import chain

API = "https://prices.openfoodfacts.org/api/v1/prices"
UA = "GRX grocery tracker (github.com/clementc52/grx)"

# Loose produce is priced by category, not barcode.
CATEGORY = {"en:bananas": "bananas", "en:apples": "apples", "en:avocados": "avocados", "en:potatoes": "potatoes",
            "en:onions": "onions", "en:yellow-onions": "onions", "en:carrots": "carrots", "en:tomatoes": "tomatoes",
            "en:broccoli": "broccoli", "en:cucumbers": "cucumber", "en:romaine-lettuces": "lettuce",
            "en:strawberries": "strawberries", "en:eggs": "eggs-large", "en:chicken-breasts": "chicken-breast",
            "en:chicken-thighs": "chicken-thigh", "en:ground-beef": "ground-beef"}
PER = {"KILOGRAM": "kg", "LITER": "L", "UNIT": "each"}


def fetch_page(params, timeout=30):
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def to_row(p, home, today):
    prod = p.get("product") or {}
    loc = p.get("location") or {}
    name = prod.get("product_name") or p.get("product_name") or ""
    qty, qu = prod.get("product_quantity"), (prod.get("product_quantity_unit") or "").lower()
    size_text = f"{qty} {qu}" if qty and qu in ("g", "kg", "ml", "l") else ""
    item = None
    tag = p.get("category_tag")
    if tag and tag in CATEGORY:
        item = BY_ID[CATEGORY[tag]]
        name = name or tag.split(":", 1)[1].replace("-", " ")
    else:
        for it in ITEMS:
            if name and match(name, it):
                item = it
                break
    if not item:
        return None
    price = units.money(p.get("price"))
    per = PER.get(p.get("price_per") or "")
    if per and per == item["unit"]:
        up = price
    elif per == "kg" and item["unit"] == "each":
        up = None
    else:
        up = units.unit_price(price, item["unit"], f"{name} {size_text}")
    if not plausible(item, up):
        return None
    lat, lon = loc.get("osm_lat"), loc.get("osm_lon")
    try:
        km = round(geo.km(home, (float(lat), float(lon))), 1)
    except (TypeError, ValueError):
        km = None
    store = loc.get("osm_name") or loc.get("osm_brand") or "Unknown store"
    proof = (p.get("proof") or {}).get("type")
    return {"item": item["id"], "kind": "in-store", "merchant": chain(loc.get("osm_brand") or store), "store": store,
            "city": loc.get("osm_address_city"), "name": f"{name} {size_text}".strip(), "price": round(price, 2),
            "unit_price": round(up, 4), "date": p.get("date"), "proof": proof, "discounted": p.get("price_is_discounted"),
            "was": units.money(p.get("price_without_discount")), "km": km, "op_id": p.get("id"),
            "seen": p.get("date"), "valid_from": p.get("date"), "valid_to": None}


def collect(home_latlon, radius_km, days=120, max_pages=30, log=print, fetcher=fetch_page):
    today = dt.date.today()
    params = {"lat": home_latlon[0], "lon": home_latlon[1], "radius_km": radius_km, "currency": "CAD",
              "date__gte": (today - dt.timedelta(days=days)).isoformat(), "order_by": "-date", "size": 100}
    rows, total, seen = [], None, 0
    for page in range(1, max_pages + 1):
        data = fetcher(dict(params, page=page))
        items = data.get("items") or []
        total = data.get("total", total)
        for p in items:
            seen += 1
            r = to_row(p, home_latlon, today)
            if r:
                rows.append(r)
        if page >= (data.get("pages") or 1) or not items:
            break
        time.sleep(0.5)
    log(f"  Open Prices: {seen} prices within {radius_km} km in the last {days} days (total {total}), {len(rows)} match tracked groceries")
    return rows
