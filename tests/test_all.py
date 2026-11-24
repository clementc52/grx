"""Run: python tests/test_all.py"""
import csv, datetime as dt, io, json, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grx import units, analytics as A, build as B, geo
from grx.catalog import BY_ID, ITEMS, classify
from grx.chains import chain
from grx.sources import flipp, hammer, openprices
from grx import run as R

FX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_units():
    assert units.count_of("PC® FREE RUN LARGE BROWN EGGS, 12'S", "egg") == 12
    assert units.count_of("18 pcs Extra Large White Eggs", "egg") == 18
    assert units.count_of("Gray Ridge Large White Eggs", "egg") is None
    assert units.count_of("Large Size Brown Eggs 12 Pack", "egg") == 12
    assert abs(units.unit_price(3.99, "kg", "chicken breast", "", "/lb") - 3.99 / 0.45359237) < 1e-6
    assert abs(units.unit_price(5.99, "kg", "chicken breast", "", "lb 13.21kg") - 5.99 / 0.45359237) < 1e-6
    assert units.unit_price(13.21, "kg", "x", "", "/kg") == 13.21
    assert abs(units.unit_price(6.49, "L", "Neilson 2% milk 4 L") - 6.49 / 4) < 1e-9
    assert abs(units.unit_price(5.49, "kg", "Butter 454 g") - 5.49 / .454) < 1e-9
    assert units.effective_price(5, "2/") == 2.5
    assert units.money("$1.10/100g") == 1.10 and units.money("2/$5") is None and units.money(None) is None


def test_ambiguous_listings_are_skipped():
    for n in ["NO NAME® CREAM CHEESE, 227/250 G", "PC® ROAST AND GROUND COFFEE, 800-930 G",
              "DANONE ACTIVIA YOGURT TUB (650g) or NO NAME CREAM CHEESE (227g - 250g)",
              "Chicken Breast Boneless & Skinless Value Pack (~3lb)", "~3lb"]:
        assert units.ambiguous(n), n
    for n in ["FARMER'S MARKET™ CARROTS OR YELLOW ONIONS, 3 LB BAG", "NEILSON TRUTASTE 1%, 2% OR SKIM MILK, 4 L", "Gay Lea Salted Butter 454 G"]:
        assert not units.ambiguous(n), n


def test_catalog_matching():
    assert len(ITEMS) == 19
    assert [i["id"] for i in classify("GRADE A LARGE WHITE EGGS, 18 PACK")] == ["eggs-large"]
    assert [i["id"] for i in classify("Neilson 2% Milk 4 L")] == ["milk-2"]
    assert [i["id"] for i in classify("Kraft Peanut Butter 1 kg")] == ["peanut-butter"]
    for bad in ["JUST EGG", "Egg Tart", "NO NAME® MEDIUM EGG, 30'S", "Great Value Butter Puff Pastry, 450 G", "Salted Plant Butter",
                "Coffee Whitener", "Banana Chili Sauce", "Cheddar Smoked Sausages", "Frozen Cheddar and Bacon Pierogies",
                "Smoked Chicken Breast Slices", "Golden Panda White Glutinous Rice 1.81kg", "Yellow Rock Sugar",
                "Purina One True Instinct Classic Ground Beef & Wild-Caught Salmon, Wet Dog Food",
                "Gardein Plant Based Frozen Meat Alternative Ground Beef 397 g"]:
        assert not classify(bad), bad
    for good, iid in [("Gay Lea Salted Butter 454 G", "butter"), ("Medium Cheddar Cheese", "cheddar"), ("Bone in Chicken Thighs", "chicken-thigh"),
                      ("Maxwell House Original Roast Ground Coffee 925 g", "coffee"), ("Redpath Granulated Sugar 2 kg", "sugar"),
                      ("Russet Potatoes, 10 lb Bag", "potatoes"), ("Thai Jasmine Rice 8 kg", "rice")]:
        assert [i["id"] for i in classify(good)] == [iid], good


def test_flipp_rows_real_sample():
    payload = json.load(open(os.path.join(FX, "flipp_eggs_M5S.json")))
    rows = flipp.rows_from(payload, BY_ID["eggs-large"], "M5S", 0.0, "2026-11-23T20:00:00Z")
    got = {}
    for r in rows:
        got[(r["merchant"], r["kind"])] = min(got.get((r["merchant"], r["kind"]), 1e9), round(r["unit_price"] * 12, 2))
    assert got[("Loblaws", "flyer")] == 6.50
    assert got[("Walmart", "online")] == 3.93
    assert ("Longos", "flyer") not in got                      # no size printed: skipped, never assumed
    assert ("Real Canadian Superstore", "flyer") not in got    # medium eggs are not large eggs
    assert all("JUST EGG" not in r["name"] for r in rows)


def test_outlier_crosscheck():
    ps = [{"unit_price": x} for x in (4.0, 4.2, 4.5, 3.9, 2.0, 1.0, 15.0)]
    kept, dropped = A.drop_outliers(ps)
    assert {p["unit_price"] for p in dropped} == {1.0, 15.0}       # misreads go
    assert 2.0 in {p["unit_price"] for p in kept}                  # a real half-price sale stays
    assert A.drop_outliers(ps[:3])[1] == []                    # too few prices to judge: keep all


def test_chicken_not_taken_from_shelf_history():
    assert not BY_ID["chicken-breast"]["shelf_ok"] and not BY_ID["chicken-thigh"]["shelf_ok"] and BY_ID["eggs-large"]["shelf_ok"]


def test_wholesale_packs_excluded():
    from grx.catalog import household
    assert not household(BY_ID["onions"], 22.7)      # 50 lb bag
    assert household(BY_ID["potatoes"], 4.54)        # 10 lb bag is a household pack
    assert not household(BY_ID["rice"], 18.1)


def test_summary_is_descriptive():
    e = {"d0": "2026-08-01", "p": [5.0] * 60 + [4.0] + [None] * 2 + [5.5] * 51}
    s = A.summary(e, dt.date(2026, 11, 22))
    assert s["low"] == 4.0 and s["high"] == 5.5 and s["now"] == 5.5


def _hammer_zip(path):
    prod = io.StringIO(); w = csv.writer(prod)
    w.writerow(["id", "concatted", "vendor", "product_name", "units", "brand", "detail_url", "sku", "upc"])
    w.writerow([1, "", "Metro", "Selection Large Eggs", "12un", "Selection", "", "", ""])
    w.writerow([2, "", "NoFrills", "Grade A Large White Eggs 12", "12 ea", "", "", "", ""])
    w.writerow([3, "", "NoFrills", "Large Eggs 12 Pack", "12 ea", "", "", "", ""])
    raw = io.StringIO(); w = csv.writer(raw)
    w.writerow(["nowtime", "current_price", "old_price", "price_per_unit", "other", "product_id"])
    d0 = dt.date(2025, 1, 1)
    for d in range(500):
        day = (d0 + dt.timedelta(days=d)).strftime("%Y%m%d" if d % 2 else "%Y-%m-%d") + " 08:00:00"
        w.writerow([day, "$3.99" if d % 28 < 7 else "$5.49", "", "", "", 1])
        if d % 3:   # product 2 is skipped by the scraper on some days; product 3 is always priced higher
            w.writerow([day, "$4.49", "", "", "", 2])
        w.writerow([day, "$5.99", "", "", "", 3])
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("hammer-5-product.csv", "﻿" + prod.getvalue())
        z.writestr("hammer-5-raw.csv", "﻿" + raw.getvalue())
    return d0


def test_hammer_stable_basket_has_no_spikes():
    with tempfile.TemporaryDirectory() as root:
        zp = os.path.join(root, "h.zip")
        _hammer_zip(zp)
        series, audit = hammer.parse(zp, log=lambda *a: None)
        nf = [x for x in series["eggs-large"]["NoFrills"]["p"][7:] if x is not None]   # after the first week
        assert max(nf) <= 4.49 / 12 + 1e-4, "missing days must not let the pricier product spike the series"
        assert set(series["eggs-large"]) == {"Metro", "NoFrills"}


def test_build_end_to_end():
    with tempfile.TemporaryDirectory() as root:
        d0 = _hammer_zip(os.path.join(root, "h.zip"))
        series, audit = hammer.parse(os.path.join(root, "h.zip"), log=lambda *a: None)
        os.makedirs(os.path.join(root, "data/hammer")); os.makedirs(os.path.join(root, "data/flipp"))
        json.dump(series, open(os.path.join(root, "data/hammer/series.json"), "w"))
        today = d0 + dt.timedelta(days=499)
        rows = flipp.rows_from(json.load(open(os.path.join(FX, "flipp_eggs_M5S.json"))), BY_ID["eggs-large"], "M5S", 0.0, "x")
        for r in rows:
            r["valid_from"], r["valid_to"] = today.isoformat(), (today + dt.timedelta(days=5)).isoformat()
        json.dump({"at": "2026-11-23T20:00:00Z", "rows": rows}, open(os.path.join(root, "data/flipp/latest.json"), "w"))
        b = B.build(root, today=today, cfg={"radius_km": 100})
        eggs = next(i for i in b["items"] if i["id"] == "eggs-large")
        ups = [o["unit_price"] for o in eggs["offers"]]
        assert ups == sorted(ups) and eggs["offers"]
        assert {o["kind"] for o in eggs["offers"]} >= {"flyer", "shelf"}
        assert eggs["shelf"] and eggs["shelf"][0]["low"] <= eggs["shelf"][0]["high"]
        assert R.summary(b).startswith("board: 19 staples")
        # price alert respects chosen stores
        hits = R.check_rules(b, [{"item": "eggs-large", "below": 99}], ["Metro"])
        assert hits and "Metro" in hits[0]["body"]
        assert not R.check_rules(b, [{"item": "eggs-large", "below": 99}], ["Nonexistent"])


def test_openprices_rows():
    home = (43.663, -79.396)
    page = {"items": [
        {"id": 1, "category_tag": "en:potatoes", "price": 1.10, "price_per": "KILOGRAM", "date": "2026-11-20", "proof": {"type": "PRICE_TAG"},
         "location": {"osm_name": "No Frills", "osm_brand": "No Frills", "osm_lat": 43.66, "osm_lon": -79.40}},
        {"id": 2, "price": 4.99, "date": "2026-11-21", "proof": {"type": "RECEIPT"},
         "product": {"product_name": "Lactantia Salted Butter", "product_quantity": 454, "product_quantity_unit": "g"},
         "location": {"osm_name": "T&T Supermarket", "osm_brand": "T&T Supermarket", "osm_lat": 43.80, "osm_lon": -79.42}},
        {"id": 3, "price": 2.0, "product": {"product_name": "Nutella"}, "location": {}},
    ], "total": 3, "pages": 1}
    rows = openprices.collect(home, 100, fetcher=lambda params: page, log=lambda *a: None)
    by = {r["item"]: r for r in rows}
    assert by["potatoes"]["unit_price"] == 1.10 and by["potatoes"]["merchant"] == "No Frills"
    assert abs(by["butter"]["unit_price"] - 4.99 / .454) < 1e-3 and by["butter"]["merchant"] == "T&T"
    assert len(rows) == 2


def test_chains_and_geo():
    assert chain("NoFrills") == chain("No Frills") == "No Frills" and chain("TandT") == chain("T&T Supermarket") == "T&T"
    s = geo.sweep("M5S", 100, 10)
    assert s[0][0] == "M5S" and len(s) == 10 and all(d <= 100 for _, d in s)


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("ok", k)
