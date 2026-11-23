"""Assemble site/data/board.json (and hist.json) from the collected data."""
import datetime as dt
import glob
import json
import os
import re

from . import analytics as A
from .catalog import ITEMS, PRIVATE_LABELS

ALIAS = {"ttsupermarket": "tandt", "tt": "tandt", "tandtsupermarket": "tandt", "galleriasupermarket": "galleria",
         "saveonfoods": "saveonfoods", "sobeys": "voila", "voilabysobeys": "voila", "realcanadiansuperstore": "superstore",
         "walmartcanada": "walmart", "nofrills": "nofrills", "loblaw": "loblaws"}
MAJOR = re.compile(r"no frills|superstore|loblaws|metro|sobeys|freshco|food basics|walmart|giant tiger|longo|fortinos|zehrs|valu-mart|your independent|farm boy|t&t|adonis|galleria|costco|foodland|whole foods|rabba|independent", re.I)


def norm(s):
    s = re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("&", "and"))
    return ALIAS.get(s, s)


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def flipp_history(root):
    rows = []
    for fn in sorted(glob.glob(os.path.join(root, "data/flipp/*.jsonl")))[-6:]:
        with open(fn) as f:
            rows += [json.loads(l) for l in f if l.strip()]
    return rows


def flyer_cycles(rows, today):
    """Treat each flyer appearance as a sale episode: (item, merchant) -> pseudo analysis."""
    by = {}
    for r in rows:
        if r.get("kind") != "flyer" or not r.get("valid_from"):
            continue
        k = (r["item"], r["merchant"])
        d = r["valid_from"]
        cur = by.setdefault(k, {})
        cur[d] = min(cur.get(d, 9e9), r["unit_price"])
    out = {}
    for (iid, m), days in by.items():
        ds = sorted(days)
        starts = [dt.date.fromisoformat(d) for d in ds]
        merged = [starts[0]]
        for s in starts[1:]:
            if (s - merged[-1]).days >= 5:
                merged.append(s)
        gaps = [(b - a).days for a, b in zip(merged, merged[1:])]
        out[(iid, m)] = {"gaps": gaps, "since": (today - merged[-1]).days, "appearances": len(merged),
                         "low": min(days.values())}
    return out


def build(root=".", today=None, cfg=None):
    today = today or dt.date.today()
    cfg = cfg or load(os.path.join(root, "config.json"), {})
    series = load(os.path.join(root, "data/hammer/series.json"), {})
    shrink = load(os.path.join(root, "data/hammer/shrink.json"), [])
    hmeta = load(os.path.join(root, "data/hammer/meta.json"), {})
    stat = load(os.path.join(root, "data/statcan/avg.json"), {})
    latest = load(os.path.join(root, "data/flipp/latest.json"), {"rows": [], "at": None})
    hist_rows = flipp_history(root)
    fcyc = flyer_cycles(hist_rows, today)
    radius = cfg.get("radius_km", 100)
    tday = today.isoformat()

    # analyse every hammer series, pool gaps by category
    anal, pooled = {}, {}
    for it in ITEMS:
        for v, e in (series.get(it["id"]) or {}).items():
            a = A.analyze(e, today)
            if a:
                anal[(it["id"], v)] = a
                pooled.setdefault(it["cat"], []).extend(a["gaps"])
    for (iid, m), fc in fcyc.items():
        cat = next(i["cat"] for i in ITEMS if i["id"] == iid)
        pooled.setdefault(cat, []).extend(fc["gaps"])
    curves = {c: A.km_curve(g, []) if g else None for c, g in pooled.items()}

    live = [r for r in latest.get("rows", []) if r.get("km", 0) <= radius and
            ((r["kind"] == "flyer" and r.get("valid_to", "") >= tday and r.get("valid_from", "") <= tday) or r["kind"] == "online")]
    items_out, hist_out, match_plan = [], {}, []
    matchers = cfg.get("price_match_at", ["No Frills"])
    for it in ITEMS:
        offers = sorted([r for r in live if r["item"] == it["id"]], key=lambda r: r["unit_price"])
        vendors = []
        for (iid, v), a in anal.items():
            if iid != it["id"]:
                continue
            o = A.odds(a, curves.get(it["cat"]))
            vendors.append({"v": v, "src": "shelf", "now": a["now"], "reg": a["reg"], "on_sale": a["on_sale"],
                            "stale_days": a["stale_days"], "p7": o[7], "p14": o[14], "p28": o[28],
                            "exp": (a["reg"] * a["depth"]) if a["depth"] else None, "lo90": a["lo90"],
                            "med90": a["med90"], "hi90": a["hi90"], "n_sales": a["n_sales"],
                            "gap": A.median_gap(a, pooled.get(it["cat"])), "last": a["last"]})
        for (iid, m), fc in fcyc.items():
            if iid != it["id"] or fc["appearances"] < 2:
                continue
            a = {"gaps": fc["gaps"], "since": fc["since"]}
            o = A.odds(a, curves.get(it["cat"]))
            vendors.append({"v": m, "src": "flyer", "p7": o[7], "p14": o[14], "p28": o[28], "n_sales": fc["appearances"],
                            "lo_seen": fc["low"], "gap": A.median_gap(a, pooled.get(it["cat"]))})
        shelf = [v for v in vendors if v["src"] == "shelf"]
        c = A.call(it, shelf, offers)
        hv = {norm(v["v"]): (v["v"], anal[(it["id"], v["v"])]) for v in shelf}
        offs = []
        for r in offers[:30]:
            h = hv.get(norm(r["merchant"]))
            o = {k: r.get(k) for k in ("merchant", "name", "price", "unit_price", "kind", "story", "valid_to", "km", "fsa", "pre", "post", "was", "assumed", "pack")}
            o["bulk"] = bool(r.get("pack") and r["pack"] > 4 * it["show"])
            o["verdict"] = A.verdict(r["unit_price"], h[1]) if h else None
            offs.append(o)
        sc = stat.get(it["id"], {})
        base = sc.get("Ontario") or sc.get("Canada")
        statline = None
        if base and base["m"]:
            mo = sorted(base["m"])[-1]
            statline = {"geo": "Ontario" if "Ontario" in sc else "Canada", "month": mo, "avg": base["m"][mo],
                        "yoy": round(base["m"][mo] / base["m"][sorted(base["m"])[-13]] - 1, 3) if len(base["m"]) >= 13 else None,
                        "product": base["product"]}
        items_out.append({"id": it["id"], "label": it["label"], "cat": it["cat"], "unit": it["unit"], "show": it["show"],
                          "show_label": it["show_label"], "shelf": it["shelf"], "use": it["use"], "call": c,
                          "offers": offs, "vendors": sorted(vendors, key=lambda v: -(v.get("p14") or 0)),
                          "statcan": statline, "n_offers": len(offers)})
        hist_out[it["id"]] = {v: {"d0": (dt.date.fromisoformat(e["d0"]) + dt.timedelta(days=max(0, len(e["p"]) - 400))).isoformat(),
                                  "p": e["p"][-400:], "w": (e.get("w") or [])[-400:]} for v, e in (series.get(it["id"]) or {}).items()}
        # price-match plan: cheapest matchable competitor flyer item
        flyer = [r for r in offers if r["kind"] == "flyer" and MAJOR.search(r["merchant"])]
        for mstore in matchers:
            own = [r for r in flyer if norm(r["merchant"]) == norm(mstore)]
            comp = [r for r in flyer if norm(r["merchant"]) != norm(mstore) and not PRIVATE_LABELS.search(r["name"])]
            if comp:
                b = comp[0]
                o_best = own[0]["unit_price"] if own else None
                if o_best is None or b["unit_price"] < o_best * 0.97:
                    match_plan.append({"item": it["id"], "label": it["label"], "at": mstore, "show": it["show"],
                                       "show_label": it["show_label"], "merchant": b["merchant"], "name": b["name"],
                                       "price": b["price"], "unit_price": b["unit_price"], "valid_to": b.get("valid_to"),
                                       "own": o_best})
    merchants = sorted({r["merchant"] for r in live})
    board = {
        "generated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "today": tday,
        "home": {"label": cfg.get("home_label", ""), "fsa": cfg.get("home_fsa"), "radius_km": radius},
        "sources": {"flipp": {"at": latest.get("at"), "rows": len(live), "merchants": len(merchants), "fsas": latest.get("fsas", []),
                              "history_rows": len(hist_rows)},
                    "hammer": hmeta, "statcan": {"items": len(stat)}},
        "items": items_out, "shrink": shrink[:60], "lockstep": A.lockstep(series),
        "match": sorted(match_plan, key=lambda m: m["at"]), "merchants": merchants,
    }
    os.makedirs(os.path.join(root, "site/data"), exist_ok=True)
    with open(os.path.join(root, "site/data/board.json"), "w") as f:
        json.dump(board, f, separators=(",", ":"))
    with open(os.path.join(root, "site/data/hist.json"), "w") as f:
        json.dump(hist_out, f, separators=(",", ":"))
    return board
