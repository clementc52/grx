"""The trading desk: turns price histories into Buy / Wait / Stock up calls.

Model, per (item, vendor) daily series p_t with optional 'was' price w_t:

  regular price  R_t = max(w_t, 80th percentile of p over the trailing 56 days)
  on sale        p_t <= 0.93 R_t, or p_t < 0.97 w_t
  sale episode   a maximal run of sale days; depth = min(p) / R at its start
  sale gaps      days between consecutive episode starts

The waiting time to the next sale is estimated with a Kaplan-Meier survival
curve over the observed gaps, treating the time since the last sale start as
a right-censored observation. With few gaps the curve is shrunk toward the
pooled curve of the whole category (weight n / (n + 4)), so a product with
two sales on record borrows strength from its siblings.

  P(sale within h days | s days since last sale) = 1 - S(s + h) / S(s)
"""
import bisect
import datetime as dt
import math

SALE_RATIO = 0.93
WINDOW = 56


def _date(s):
    return dt.date.fromisoformat(s)


def daily(entry, ffill=4):
    """Series dict {d0, p, w} -> (d0, prices, wases) with short gaps forward-filled."""
    p, w = list(entry["p"]), list(entry.get("w") or [None] * len(entry["p"]))
    last, gap = None, 0
    for i, x in enumerate(p):
        if x is None:
            gap += 1
            if last is not None and gap <= ffill:
                p[i] = last
        else:
            last, gap = x, 0
    return _date(entry["d0"]), p, w


def _pct(sorted_vals, q):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def regular(p, w):
    R, win = [None] * len(p), []
    for i, x in enumerate(p):
        if x is not None:
            bisect.insort(win, x)
        j = i - WINDOW
        if j >= 0 and p[j] is not None:
            win.pop(bisect.bisect_left(win, p[j]))
        r = _pct(win, 0.8)
        if w[i] and (r is None or w[i] > r):
            r = w[i]
        R[i] = r
    return R


def episodes(p, R, w):
    sale = [x is not None and r is not None and (x <= SALE_RATIO * r or (wi is not None and x < 0.97 * wi))
            for x, r, wi in zip(p, R, w)]
    eps, i = [], 0
    while i < len(p):
        if sale[i]:
            j = i
            while j + 1 < len(p) and sale[j + 1]:
                j += 1
            depth = min(p[k] for k in range(i, j + 1)) / R[i]
            eps.append((i, j, depth))
            i = j + 1
        else:
            i += 1
    return sale, eps


def km_curve(events, censored):
    """Kaplan-Meier: returns sorted [(t, S(t))] step points."""
    obs = sorted([(t, 1) for t in events] + [(t, 0) for t in censored])
    n, S, pts, i = len(obs), 1.0, [(0, 1.0)], 0
    while i < len(obs):
        t = obs[i][0]
        d = sum(1 for x in obs[i:] if x[0] == t and x[1] == 1)
        c = sum(1 for x in obs[i:] if x[0] == t)
        if d and n:
            S *= 1 - d / n
            pts.append((t, S))
        n -= c
        i += c
    return pts


def S_at(curve, t):
    k = bisect.bisect_right([x[0] for x in curve], t) - 1
    return curve[max(k, 0)][1]


def p_within(curve, s, h):
    a = S_at(curve, s)
    if a <= 1e-9:
        return 1.0
    return max(0.0, min(1.0, 1 - S_at(curve, s + h) / a))


def analyze(entry, today=None):
    """Full read-out for one (item, vendor) series."""
    d0, p, w = daily(entry)
    if not any(x is not None for x in p):
        return None
    R = regular(p, w)
    sale, eps = episodes(p, R, w)
    last_i = max(i for i, x in enumerate(p) if x is not None)
    today = today or dt.date.today()
    stale = (today - (d0 + dt.timedelta(days=last_i))).days
    starts = [e[0] for e in eps]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    on_sale = sale[last_i]
    since = last_i - (starts[-1] if starts else 0) if starts else last_i + 1
    lo = max(0, last_i - 90)
    recent = sorted(x for x in p[lo:last_i + 1] if x is not None)
    depths = [e[2] for e in eps[-8:]]
    return {
        "now": p[last_i], "reg": R[last_i], "on_sale": on_sale, "stale_days": stale,
        "last": (d0 + dt.timedelta(days=last_i)).isoformat(),
        "gaps": gaps, "since": since, "n_sales": len(eps),
        "depth": _pct(sorted(depths), 0.5) if depths else None,
        "lo90": recent[0], "med90": _pct(recent, 0.5), "hi90": recent[-1],
        "sale_days_90": sum(1 for i in range(lo, last_i + 1) if sale[i]),
        "days_90": last_i + 1 - lo,
    }


def odds(a, pooled_curve, horizons=(7, 14, 28)):
    """Probability of a new sale starting within each horizon, shrunk toward the category."""
    own = km_curve(a["gaps"], [a["since"]]) if a["gaps"] else None
    wgt = len(a["gaps"]) / (len(a["gaps"]) + 4)
    out = {}
    for h in horizons:
        pc = p_within(pooled_curve, a["since"], h) if pooled_curve else 0.0
        po = p_within(own, a["since"], h) if own else pc
        out[h] = round(min(0.97, max(0.03, wgt * po + (1 - wgt) * pc)), 3)
    return out


def median_gap(a, pooled_gaps):
    g = sorted(a["gaps"] or pooled_gaps or [])
    return _pct(g, 0.5) if g else None


def call(item, vendors, offers):
    """Item-level Buy / Wait / Stock up.

    vendors: [{v, now, reg, on_sale, p14, exp, lo90, med90, gap}]
    offers:  live flyer / online offers [{unit_price, merchant, ...}]
    All prices are per base unit.
    """
    cands = [(o["unit_price"], o["merchant"], o.get("kind", "flyer")) for o in offers
             if not (o.get("pack") and o["pack"] > 4 * item["show"])]   # a 180-egg case is not a household price
    cands += [(v["now"], v["v"], "shelf") for v in vendors if v.get("now") and v.get("stale_days", 0) <= 5]
    if not cands:
        return {"action": "NO DATA", "reason": "No current prices found in range yet."}
    best_now, where, kind = min(cands)
    # what the cheapest place is likely to charge within two weeks
    fut = []
    for v in vendors:
        if v.get("exp") and v.get("p14") is not None and not v["on_sale"]:
            fut.append((v["p14"] * v["exp"] + (1 - v["p14"]) * v["now"], v["exp"], v["p14"], v["v"]))
    lows = [v["lo90"] for v in vendors if v.get("lo90")]
    low90 = min(lows) if lows else None
    show, label = item["show"], item["show_label"]
    fmt = lambda x: f"${x * show:,.2f} {label}"
    gap = min([v["gap"] for v in vendors if v.get("gap")] or [28])
    cover = min(item["shelf"], gap * 1.15)
    qty = max(1, math.ceil(cover / item["use"]))
    res = {"best": best_now, "where": where, "kind": kind, "low90": low90}
    if fut:
        ev, exp, p14, v = min(fut)
        saving = 1 - exp / best_now
        if p14 >= 0.5 and saving >= 0.08:
            res.update(action="WAIT", p14=p14, exp=exp, exp_where=v,
                       reason=f"{v} has a {p14:.0%} chance of a sale within 14 days at about {fmt(exp)}, {saving:.0%} under today's best ({fmt(best_now)} at {where}).")
            return res
    meds = [v["med90"] for v in vendors if v.get("med90")]
    med90 = min(meds) if meds else None
    if low90 and best_now <= low90 * 1.03 and (med90 is None or best_now <= med90 * 0.92):
        res.update(action="STOCK UP", qty=qty,
                   reason=f"{fmt(best_now)} at {where} is at the 90-day low. It keeps about {item['shelf']} days and the next comparable sale is ~{gap:.0f} days out, so buy {qty} × {label.replace('per ', '')}.")
        return res
    if low90 and best_now > low90 * 1.15:
        res.update(action="BUY ONLY IF NEEDED",
                   reason=f"Best today is {fmt(best_now)} at {where}, {best_now / low90 - 1:.0%} above its 90-day low ({fmt(low90)}), and no sale is clearly due. Buy what you need, not more.")
        return res
    res.update(action="BUY", reason=f"{fmt(best_now)} at {where} is a fair price and no deeper sale looks imminent.")
    return res


def verdict(unit_price, a):
    """Is a flyer price actually a deal versus this chain's own recent history?"""
    if not a or not a.get("med90"):
        return None
    r = unit_price / a["med90"]
    share = a["sale_days_90"] / max(a["days_90"], 1)
    if unit_price <= a["lo90"] * 1.01:
        tag = "90-day low"
    elif r <= 0.85:
        tag = "Real deal"
    elif r <= 0.96:
        tag = "Normal sale"
    else:
        tag = "Not really a sale"
    return {"tag": tag, "vs_median": round(r - 1, 3), "sale_share_90": round(share, 2)}


def lockstep(series_by_item, min_moves=3):
    """Regular-price increases that land within 3 days of each other across chains.

    For each item and pair of chains: observed co-moves vs the number expected
    if the two chains changed prices independently (rate x rate x window).
    A high ratio is a correlation flag, not evidence of collusion.
    """
    out = []
    for iid, vendors in series_by_item.items():
        ev = {}
        span = 0
        for v, e in vendors.items():
            d0, p, w = daily(e)
            R = regular(p, w)
            span = max(span, len(p))
            off = (d0 - dt.date(2024, 1, 1)).days
            hits, last = [], -99
            for i in range(7, len(R)):
                if R[i] and R[i - 7] and R[i] >= R[i - 7] * 1.03 and i - last > 14:
                    hits.append(off + i)
                    last = i
            if hits:
                ev[v] = hits
        vs = sorted(ev)
        for a in range(len(vs)):
            for b in range(a + 1, len(vs)):
                A, B = ev[vs[a]], ev[vs[b]]
                obs = sum(1 for x in A if any(abs(x - y) <= 3 for y in B))
                exp = len(A) * len(B) * 7 / max(span, 1)
                if obs >= min_moves:
                    out.append({"item": iid, "a": vs[a], "b": vs[b], "co_moves": obs,
                                "expected": round(exp, 2), "ratio": round(obs / max(exp, 0.05), 1),
                                "a_moves": len(A), "b_moves": len(B)})
    out.sort(key=lambda x: (-x["ratio"], -x["co_moves"]))
    return out[:40]
