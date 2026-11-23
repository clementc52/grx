"""Run: python -m pytest -q  (or python tests/test_all.py)"""
import csv, datetime as dt, io, json, os, random, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grx import units, analytics as A, build as B, geo
from grx.catalog import BY_ID, classify
from grx.sources import flipp, hammer

FX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_units():
    assert units.count_of("PC® FREE RUN LARGE BROWN EGGS, 12'S", "egg") == 12
    assert units.count_of("NO NAME® MEDIUM EGG, 30'S", "egg") == 30
    assert units.count_of("18 pcs Extra Large White Eggs", "egg") == 18
    assert units.count_of("Gray Ridge Large White Eggs", "egg") is None
    assert units.count_of("Large eggs, 1 dozen", "egg") == 12
    assert abs(units.unit_price(3.99, "kg", "chicken breast", "", "/lb") - 3.99 / 0.45359237) < 1e-6
    assert abs(units.unit_price(6.49, "L", "Neilson 2% milk 4 L") - 6.49 / 4) < 1e-9
    assert abs(units.unit_price(7.99, "L", "Pepsi 12 x 355 mL") - 7.99 / 4.26) < 1e-9
    assert abs(units.unit_price(5.49, "kg", "Butter 454 g") - 5.49 / .454) < 1e-9
    assert units.unit_price(12.99, "roll", "Royale toilet paper 24 double rolls") == 12.99 / 24
    assert units.effective_price(5, "2/") == 2.5
    assert abs(units.unit_price(5.99, "kg", "chicken breast", "", "lb 13.21kg") - 5.99 / 0.45359237) < 1e-6
    assert abs(units.unit_price(6.99, "kg", "chicken breast", "", "/lb 15.41/kg!") - 6.99 / 0.45359237) < 1e-6
    assert units.unit_price(13.21, "kg", "x", "", "/kg") == 13.21
    from grx.catalog import BY_ID as _B
    seg = units.segment("DANONE ACTIVIA YOGURT TUB (650g) or NO NAME CREAM CHEESE (227g - 250g)", _B["cream-cheese"]["inc"])
    assert "650" not in seg and abs(units.unit_price(4.19, "kg", seg) - 4.19 / .227) < 1e-6
    assert units.unit_price(1.48, "each", "CROWN BROCCOLI", "", "/lb") is None
    assert units.money("$1.10/100g") == 1.10 and units.money("2/$5") is None and units.money(None) is None


def test_catalog_matching():
    eggs = BY_ID["eggs-large"]
    assert [i["id"] for i in classify("GRADE A LARGE WHITE EGGS")] == ["eggs-large"]
    for bad in ["JUST EGG", "Egg Tart", "CHINA MAID SALTED DUCK EGG YOLK, 144G", "Burnbrae Farms Egg Creations Whole Eggs Original", "Kosa Can Quail Eggs In Water 425 G", "Burnbrae Farms Eggs2GO!"]:
        assert eggs not in classify(bad), bad
    assert classify("Neilson 2% Milk 4 L")[0]["id"] == "milk-2"
    assert not any(i["id"] == "butter" for i in classify("Kraft Peanut Butter 1 kg"))
    assert classify("Kraft Peanut Butter 1 kg")[0]["id"] == "peanut-butter"
    for bad in ["Great Value Butter Puff Pastry, 450 G", "Tasty Bite Butter Chickpea All Natural Indian Entree, 285g"]:
        assert not classify(bad), bad
    assert not classify("Purina One True Instinct Classic Ground Beef & Wild-Caught Salmon, Wet Dog Food")
    assert not classify("Buenas Banana Leaves 454g") and not classify("Chubby Go Banana 250g")
    assert not any(i["id"] == "chicken-breast" for i in classify("Farm Boy Chicken Breast Schnitzel"))


def test_flipp_rows_real_sample():
    payload = json.load(open(os.path.join(FX, "flipp_eggs_M5S.json")))
    rows = flipp.rows_from(payload, BY_ID["eggs-large"], "M5S", 0.0, "2026-11-23T20:00:00Z")
    got = {}
    for r in rows:
        k = (r["merchant"], r["kind"])
        got[k] = min(got.get(k, 1e9), round(r["unit_price"] * 12, 2))
    assert got[("Loblaws", "flyer")] == 6.50
    assert ("Real Canadian Superstore", "flyer") not in got   # medium eggs are not large eggs
    assert got[("Walmart", "online")] == 3.93
    longos = next(r for r in rows if r["merchant"] == "Longos")
    assert longos["assumed"] and round(longos["unit_price"] * 12, 2) == 3.99   # no count printed: assume a dozen, flagged
    assert all("JUST EGG" not in r["name"] for r in rows)
    assert ("Foody Mart", "flyer") not in got and ("Seasons Food Mart", "flyer") not in got  # medium / XL excluded


def cyc_series(days=600, period=35, depth=0.75, base=10.0, seed=1, start="2025-01-01"):
    rnd = random.Random(seed)
    p, w = [], []
    for d in range(days):
        on = (d % period) < 7
        x = base * (depth if on else 1) * (1 + rnd.uniform(-.01, .01))
        p.append(round(x, 2)); w.append(base if on else None)
    return {"d0": start, "p": p, "w": w}


def test_cycle_model():
    e = cyc_series()
    today = dt.date.fromisoformat(e["d0"]) + dt.timedelta(days=len(e["p"]) - 1)
    a = A.analyze(e, today)
    assert a["n_sales"] >= 16 and all(33 <= g <= 37 for g in a["gaps"])
    assert abs(a["depth"] - 0.75) < .03
    curve = A.km_curve(a["gaps"], [])
    # 30 days after a sale start, a new one is almost certain within 7 days
    assert A.p_within(curve, 30, 7) > .9
    assert A.p_within(curve, 2, 7) < .05
    o = A.odds(a, curve)
    assert 0 <= o[7] <= o[14] <= o[28] <= 1


def test_km_censoring():
    c = A.km_curve([10, 10, 20], [15])
    assert abs(A.S_at(c, 10) - 0.5) < 1e-9 and A.S_at(c, 20) == 0.0


def test_call_wait_and_stockup():
    item = BY_ID["coffee"]
    v_wait = [{"v": "Metro", "now": 20.0, "reg": 20.0, "on_sale": False, "p14": .8, "exp": 14.0, "lo90": 13.5, "gap": 30, "stale_days": 0}]
    c = A.call(item, v_wait, [])
    assert c["action"] == "WAIT" and "Metro" in c["reason"]
    v_low = [{"v": "Metro", "now": 13.6, "reg": 20.0, "on_sale": True, "p14": .1, "exp": 14.0, "lo90": 13.5, "gap": 30, "stale_days": 0}]
    c = A.call(item, v_low, [])
    assert c["action"] == "STOCK UP" and c["qty"] >= 1


def test_hammer_and_build_end_to_end():
    with tempfile.TemporaryDirectory() as root:
        zp = os.path.join(root, "h.zip")
        prod = io.StringIO(); w = csv.writer(prod)
        w.writerow(["id", "concatted", "vendor", "product_name", "units", "brand", "detail_url", "sku", "upc"])
        w.writerow([1, "", "Metro", "Selection Large Eggs", "12un", "Selection", "", "", ""])
        w.writerow([2, "", "NoFrills", "Grade A Large White Eggs 12", "12 ea", "", "", "", ""])
        w.writerow([3, "", "Metro", "Maxwell House Ground Coffee 925 g", "925 g", "", "", "", ""])
        raw = io.StringIO(); w = csv.writer(raw)
        w.writerow(["nowtime", "current_price", "old_price", "price_per_unit", "other", "product_id"])
        d0 = dt.date(2025, 1, 1)
        for d in range(500):
            day = (d0 + dt.timedelta(days=d)).isoformat() + " 08:00:00"
            on = d % 28 < 7
            w.writerow([day, "$3.99" if on else "$5.49", "$5.49" if on else "", "", "", 1])
            w.writerow([day, "$4.49" if d % 42 < 7 else "$5.29", "", "", "", 2])
            size = 925 if d < 400 else 850   # shrinkflation at day 400, same price
            w.writerow([day, "$12.99", "", f"${12.99 / size * 100:.2f}/100g", "", 3])
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("hammer-5-product.csv", "﻿" + prod.getvalue())
            z.writestr("hammer-5-raw.csv", "﻿" + raw.getvalue())
        series, shrink, audit = hammer.parse(zp, log=lambda *a: None)
        assert set(series["eggs-large"]) == {"Metro", "NoFrills"}
        assert any(s["item"] == "coffee" and s["size_after"] < s["size_before"] for s in shrink)
        os.makedirs(os.path.join(root, "data/hammer")); os.makedirs(os.path.join(root, "data/flipp"))
        json.dump(series, open(os.path.join(root, "data/hammer/series.json"), "w"))
        json.dump(shrink, open(os.path.join(root, "data/hammer/shrink.json"), "w"))
        payload = json.load(open(os.path.join(FX, "flipp_eggs_M5S.json")))
        rows = flipp.rows_from(payload, BY_ID["eggs-large"], "M5S", 0.0, "2026-11-23T20:00:00Z")
        json.dump({"at": "2026-11-23T20:00:00Z", "fsas": [["M5S", 0]], "rows": rows}, open(os.path.join(root, "data/flipp/latest.json"), "w"))
        today = d0 + dt.timedelta(days=499)
        for r in rows:  # move fixture validity onto the synthetic 'today'
            r["valid_from"], r["valid_to"] = today.isoformat(), (today + dt.timedelta(days=5)).isoformat()
        json.dump({"at": "x", "fsas": [], "rows": rows}, open(os.path.join(root, "data/flipp/latest.json"), "w"))
        b = B.build(root, today=today, cfg={"radius_km": 100, "price_match_at": ["No Frills"]})
        eggs = next(i for i in b["items"] if i["id"] == "eggs-large")
        assert eggs["call"]["action"] in ("BUY", "WAIT", "STOCK UP", "BUY ONLY IF NEEDED")
        assert eggs["offers"][0]["unit_price"] == min(r["unit_price"] for r in rows)
        nf = next(o for o in eggs["offers"] if o["merchant"] == "No Frills")
        assert nf["verdict"] is not None
        assert any(m["at"] == "No Frills" for m in b["match"])
        assert os.path.exists(os.path.join(root, "site/data/hist.json"))


def test_geo_sweep():
    s = geo.sweep("M5S", 100, 10)
    assert s[0][0] == "M5S" and len(s) == 10 and all(d <= 100 for _, d in s)


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("ok", k)
