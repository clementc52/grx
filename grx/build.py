"""Assemble site/data/board.json (and hist.json) from the collected data.

Everything shown is an observed price: no forecasts. Each live price passes
three gates before it is shown: the product matches the grocery's definition,
the unit price is inside a sanity range, and it agrees with the other sources
(a price far from all others is treated as a reading error).
"""
import datetime as dt
import glob
import json
import os

from . import analytics as A
from . import units
from .catalog import BY_ID, ITEMS, household, match, plausible
from .chains import chain


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def valid(r):
    """Re-check stored rows against the current rules, so rule fixes apply retroactively."""
    it = BY_ID.get(r.get("item"))
    return (bool(it) and match(r.get("name", ""), it) and plausible(it, r.get("unit_price"))
            and household(it, r.get("pack")) and not units.ambiguous(r.get("name", "")))


def hours_since(iso):
    if not iso:
        return None
    try:
        t = dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return round((dt.datetime.utcnow() - t).total_seconds() / 3600, 1)


def build(root=".", today=None, cfg=None):
    today = today or dt.date.today()
    cfg = cfg or load(os.path.join(root, "config.json"), {})
    radius = cfg.get("radius_km", 100)
    tday = today.isoformat()
    series = load(os.path.join(root, "data/hammer/series.json"), {})
    hmeta = load(os.path.join(root, "data/hammer/meta.json"), {})
    stat = load(os.path.join(root, "data/statcan/avg.json"), {})
    latest = load(os.path.join(root, "data/flipp/latest.json"), {"rows": [], "at": None})
    op = load(os.path.join(root, "data/openprices/latest.json"), {"rows": [], "at": None})

    fresh = (today - dt.timedelta(days=cfg.get("in_store_days", 21))).isoformat()
    community = [dict(r, chain=chain(r["merchant"])) for r in op.get("rows", [])
                 if valid(r) and (r.get("km") is None or r["km"] <= radius) and (r.get("date") or "") >= fresh]
    current = [dict(r, chain=chain(r["merchant"])) for r in latest.get("rows", [])
               if valid(r) and r.get("km", 0) <= radius and
               ((r["kind"] == "flyer" and r.get("valid_from", "") <= tday <= r.get("valid_to", "")) or r["kind"] == "online")]
    live = community + current

    items_out, hist_out, dropped_total = [], {}, 0
    for it in ITEMS:
        shelf = []
        for v, e in (series.get(it["id"]) or {}).items():
            s = A.summary(e, today)
            if s and (today - dt.date.fromisoformat(s["now_date"])).days <= 3:
                shelf.append({"v": v, "chain": chain(v), **s})
        offers = [r for r in live if r["item"] == it["id"]]
        offers += [{"item": it["id"], "kind": "shelf", "merchant": s["chain"], "chain": s["chain"], "name": "Everyday shelf price (cheapest of its basket)",
                    "unit_price": s["now"], "date": s["now_date"]} for s in shelf]
        offers, dropped = A.drop_outliers(offers)
        dropped_total += len(dropped)
        offers.sort(key=lambda r: r["unit_price"])
        keep = ("merchant", "chain", "name", "price", "unit_price", "kind", "story", "valid_to", "valid_from", "km", "pre", "post",
                "was", "store", "date", "proof")
        sc = stat.get(it["id"], {})
        base = sc.get("Ontario") or sc.get("Canada")
        statline = None
        if base and base.get("raw"):
            mo = sorted(base["raw"])[-1]
            statline = {"geo": "Ontario" if "Ontario" in sc else "Canada", "month": mo, "value": base["raw"][mo], "product": base["product"]}
        items_out.append({"id": it["id"], "label": it["label"], "cat": it["cat"], "unit": it["unit"], "show": it["show"],
                          "show_label": it["show_label"], "offers": [{k: r.get(k) for k in keep} for r in offers[:60]],
                          "shelf": shelf, "statcan": statline, "dropped": len(dropped)})
        hist_out[it["id"]] = {v: {"d0": (dt.date.fromisoformat(e["d0"]) + dt.timedelta(days=max(0, len(e["p"]) - 400))).isoformat(),
                                  "p": e["p"][-400:]} for v, e in (series.get(it["id"]) or {}).items()}

    cc = {}
    for r in live:
        cc[r["chain"]] = cc.get(r["chain"], 0) + 1
    for it in items_out:
        for s in it["shelf"]:
            cc.setdefault(s["chain"], 0)
    fl_age, hm_age = hours_since(latest.get("at")), hours_since(hmeta.get("fetched"))
    health = {
        "flyers": {"age_h": fl_age, "ok": fl_age is not None and fl_age <= 3, "rows": len(current)},
        "shelf": {"age_h": hm_age, "ok": hm_age is not None and hm_age <= 36, "last_load": hmeta.get("last_load"),
                  "chains": len(hmeta.get("vendors") or [])},
        "in_store": {"age_h": hours_since(op.get("at")), "rows": len(community)},
        "statcan": {"items": len(stat)},
        "outliers_dropped": dropped_total,
    }
    board = {
        "generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "today": tday,
        "home": {"label": cfg.get("home_label", ""), "fsa": cfg.get("home_fsa"), "radius_km": radius},
        "health": health, "items": items_out,
        "chains": sorted(({"name": k, "offers": v} for k, v in cc.items()), key=lambda x: -x["offers"]),
        "vendors": {v: chain(v) for vs in series.values() for v in vs},
        "my_stores": cfg.get("my_stores") or [], "repo": cfg.get("repo", ""),
    }
    validate(board)
    os.makedirs(os.path.join(root, "site/data"), exist_ok=True)
    with open(os.path.join(root, "site/data/board.json"), "w") as f:
        json.dump(board, f, separators=(",", ":"))
    with open(os.path.join(root, "site/data/hist.json"), "w") as f:
        json.dump(hist_out, f, separators=(",", ":"))
    return board


def validate(board):
    """Refuse to publish a board that is malformed; the previous site stays up instead."""
    assert board["items"], "no items"
    for it in board["items"]:
        for o in it["offers"]:
            u = o["unit_price"]
            assert isinstance(u, (int, float)) and u > 0 and u == u, f"bad unit price in {it['id']}: {u}"
            assert o["merchant"], f"offer without a store in {it['id']}"
