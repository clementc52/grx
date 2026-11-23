"""Daily shelf-price history from Project Hammer (jacobfilipp.com/hammer).

Eight vendors (Voila, T&T, Loblaws, No Frills, Metro, Galleria, Walmart,
Save-On-Foods), one price per product per day since 2024-02-28, including
the 'was' price when an item is on sale. We stream the zipped CSVs and keep
only products that match the catalog, rolled up to one series per
(catalog item, vendor): the cheapest unit price that day.
"""
import csv
import datetime as dt
import io
import re
import urllib.request
import zipfile

from .. import units
from ..catalog import ITEMS, match, plausible

URLS = ["https://jacobfilipp.com/hammerdata/hammer-5-csv.zip"]
LASTUPDATED = "https://jacobfilipp.com/hammerdata/hammer-lastupdated.txt"
_PPU = re.compile(r"\$?\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)?\s*(kg|g|ml|l|lb|ea|un|each)\b", re.I)

csv.field_size_limit(10_000_000)


def download(path, log=print):
    last = None
    for u in URLS:
        try:
            log(f"  downloading {u}")
            req = urllib.request.Request(u, headers={"User-Agent": "GRX grocery research"})
            with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            return path
        except Exception as e:
            last = e
            log(f"  ! {e}")
    raise RuntimeError(f"Project Hammer download failed: {last}")


def _member(z, word):
    names = [n for n in z.namelist() if n.lower().endswith(".csv") and word in n.lower()]
    if not names:
        raise RuntimeError(f"no '{word}' csv in archive: {z.namelist()}")
    return names[0]


def _reader(z, name):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig", errors="replace", newline=""))


def _size_from_ppu(price, ppu_text):
    """Package size implied by price / price-per-unit, in g, ml or count."""
    m = _PPU.search(ppu_text or "")
    if not m or not price:
        return None
    per, qty, u = float(m.group(1)), float(m.group(2) or 1), m.group(3).lower()
    if per <= 0:
        return None
    mult = {"kg": 1000, "g": 1, "l": 1000, "ml": 1, "lb": 453.592, "ea": 1, "un": 1, "each": 1}[u]
    return round(price / per * qty * mult, 1)


def _unit_price(price, item, name, size_text):
    has_digit = any(c.isdigit() for c in size_text or "")
    post = "" if has_digit else (size_text or "")
    return units.unit_price(price, item["unit"], name, size_text or "", post)


def parse(zip_path, since_days=None, log=print, basket=6, recent_days=120):
    """Two passes over the daily price file.

    Pass 1 scores every matching product by how often it was priced recently
    and its typical unit price. Each (item, chain) then gets a stable basket:
    the cheapest few products that are priced on most days. Pass 2 builds the
    daily series as the cheapest basket product, carrying each product's last
    price forward up to 7 days. A fixed basket stops the series from jumping
    whenever the scraper happens to skip a product on some day.
    """
    z = zipfile.ZipFile(zip_path)
    prods = {}
    for r in _reader(z, _member(z, "product")):
        name = r.get("product_name") or ""
        for item in ITEMS:
            if match(name, item):
                prods[r.get("id")] = (item, (r.get("vendor") or "").strip(), name, r.get("units") or "", r.get("brand") or "")
                break
    log(f"  {len(prods)} Hammer products match the catalog")
    today = dt.date.today()
    cutoff = (today - dt.timedelta(days=since_days)).isoformat() if since_days else ""

    def rows():
        for r in _reader(z, _member(z, "raw")):
            p = prods.get(r.get("product_id"))
            if not p:
                continue
            digits = re.sub(r"\D", "", r.get("nowtime") or "")[:8]   # '2026-11-22 08:00' or '20261122 ...'
            if len(digits) < 8:
                continue
            d = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            if d < cutoff:
                continue
            item, vendor, name, size_text, brand = p
            price = units.money(r.get("current_price"))
            up = _unit_price(price, item, name, size_text)
            if not plausible(item, up):
                yield None
                continue
            yield r.get("product_id"), d, price, up, r

    # pass 1: coverage and typical price per product, by month (relative to the newest data)
    stat, dropped, n, newest = {}, 0, 0, ""
    for x in rows():
        if x is None:
            dropped += 1
            continue
        pid, d, price, up, r = x
        m = stat.setdefault(pid, {}).setdefault(d[:7], [0, 0.0])
        m[0] += 1
        m[1] += up
        newest = max(newest, d)
        n += 1
    log(f"  pass 1: {n} plausible daily rows, {dropped} dropped as implausible unit prices; newest {newest}")
    nd = dt.date.fromisoformat(newest) if newest else today
    months = {(nd - dt.timedelta(days=k)).isoformat()[:7] for k in range(0, recent_days, 15)}
    groups = {}
    for pid, bym in stat.items():
        cnt = sum(v[0] for k, v in bym.items() if k in months)
        if not cnt:
            continue
        tot = sum(v[1] for k, v in bym.items() if k in months)
        item, vendor = prods[pid][0], prods[pid][1]
        groups.setdefault((item["id"], vendor), []).append((cnt, tot / cnt, pid))
    chosen = {}
    for k, lst in groups.items():
        top = max(c for c, _, _ in lst)
        stable = [x for x in lst if x[0] >= 0.4 * top]
        for c, avg, pid in sorted(stable, key=lambda x: x[1])[:basket]:
            chosen[pid] = k
    log(f"  basket: {len(chosen)} stable products across {len(groups)} item-chain pairs")
    if not chosen:
        raise RuntimeError("no stable products selected; refusing to overwrite history")

    # pass 2: daily prices of basket products, sizes for shrinkflation
    daily_ = {}   # pid -> {date: (up, was_up, price)}
    sizes = {}
    for x in rows():
        if x is None:
            continue
        pid, d, price, up, r = x
        item, vendor, name, size_text, brand = prods[pid]
        s_ = _size_from_ppu(price, r.get("price_per_unit"))
        if s_:
            h = sizes.setdefault(pid, [])
            if not h or abs(h[-1][1] - s_) / max(h[-1][1], 1e-9) > 0.02:
                h.append((d, s_, price))
        if pid not in chosen:
            continue
        was = units.money(r.get("old_price"))
        wup = _unit_price(was, item, name, size_text) if was and price and was > price else None
        if wup and not plausible(item, wup):
            wup = None
        daily_.setdefault(pid, {})[d] = (up, wup, price)

    agg, audit = {}, {}
    by_group = {}
    for pid, k in chosen.items():
        if pid in daily_:
            by_group.setdefault(k, []).append(pid)
    for (iid, vendor), pids in by_group.items():
        days = sorted({d for pid in pids for d in daily_[pid]})
        if not days:
            continue
        d0, d1 = dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1])
        last = {pid: None for pid in pids}
        for j in range((d1 - d0).days + 1):
            d = (d0 + dt.timedelta(days=j)).isoformat()
            best = None
            for pid in pids:
                v = daily_[pid].get(d)
                if v:
                    last[pid] = (j, v)
                lv = last[pid]
                if lv and j - lv[0] <= 7 and (best is None or lv[1][0] < best[0]):
                    best = lv[1]
            if best:
                agg[(iid, vendor, d)] = [best[0], best[1]]
        cur = []
        for pid in pids:
            dd = max(daily_[pid])
            up, _, price = daily_[pid][dd]
            cur.append({"unit_price": round(up, 4), "name": prods[pid][2], "price": price, "units": prods[pid][3], "last_seen": dd})
        audit.setdefault(iid, {})[vendor] = sorted(cur, key=lambda c: c["unit_price"])
    return _series(agg), _shrink(sizes, prods), audit


def _series(agg):
    """{item: {vendor: {d0, p:[...], w:[...]}}} with one slot per day (None = missing)."""
    byiv = {}
    for (i, v, d), (p, w) in agg.items():
        byiv.setdefault((i, v), {})[d] = (p, w)
    out = {}
    for (i, v), days in byiv.items():
        ds = sorted(days)
        d0, d1 = dt.date.fromisoformat(ds[0]), dt.date.fromisoformat(ds[-1])
        span = (d1 - d0).days + 1
        P, W = [None] * span, [None] * span
        for d, (p, w) in days.items():
            j = (dt.date.fromisoformat(d) - d0).days
            P[j], W[j] = round(p, 4), (round(w, 4) if w else None)
        out.setdefault(i, {})[v] = {"d0": ds[0], "p": P, "w": W}
    return out


def _shrink(sizes, prods):
    """Products whose package got smaller while the shelf price barely moved."""
    ev = []
    for pid, h in sizes.items():
        for (d0, s0, p0), (d1, s1, p1) in zip(h, h[1:]):
            if s1 < s0 * 0.97 and p1 >= p0 * 0.97:
                item, vendor, name, _, brand = prods[pid]
                ev.append({"item": item["id"], "vendor": vendor, "name": name, "brand": brand,
                           "date": d1, "size_before": s0, "size_after": s1, "price_before": p0, "price_after": p1,
                           "hidden_increase": round((p1 / s1) / (p0 / s0) - 1, 4)})
    ev.sort(key=lambda e: e["date"], reverse=True)
    return ev[:200]
