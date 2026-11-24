"""Descriptive statistics only: what prices have actually been, nothing predicted."""
import datetime as dt


def window(entry, today, days=90):
    """Prices of one daily series within the last `days` days (gaps of up to 4 days carried forward)."""
    d0 = dt.date.fromisoformat(entry["d0"])
    out, last, gap = [], None, 0
    for i, x in enumerate(entry["p"]):
        if x is None:
            gap += 1
            x = last if gap <= 4 else None
        else:
            last, gap = x, 0
        d = d0 + dt.timedelta(days=i)
        if x is not None and (today - d).days < days:
            out.append((d, x))
    return out


def summary(entry, today, days=90):
    """{now, now_date, low, median, high} for the last `days` days, or None."""
    w = window(entry, today, days)
    if not w:
        return None
    vals = sorted(x for _, x in w)
    n = len(vals)
    med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return {"now": w[-1][1], "now_date": w[-1][0].isoformat(), "low": vals[0], "median": med, "high": vals[-1], "days": n}


def drop_outliers(prices, lo=0.35, hi=3.0):
    """Cross-check: a price far from what every other source says for the same item is treated as a
    reading error and dropped. The band is wide on purpose: real loss-leader sales (50% off) must survive;
    only misreads (a wrong size, a missing digit) land this far out. Returns (kept, dropped). Needs at least 4 prices to judge."""
    if len(prices) < 4:
        return prices, []
    vals = sorted(p["unit_price"] for p in prices)
    med = vals[len(vals) // 2]
    kept = [p for p in prices if lo * med <= p["unit_price"] <= hi * med]
    return kept, [p for p in prices if p not in kept]
