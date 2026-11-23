"""CLI entry point used by GitHub Actions.

  python -m grx.run flipp [--full]   live flyer + online prices (home FSA, or full radius sweep)
  python -m grx.run hammer            daily shelf-price history (Project Hammer)
  python -m grx.run statcan           official monthly averages
  python -m grx.run build             rebuild site/data/board.json
  python -m grx.run alerts            check watch rules, open GitHub issues
"""
import datetime as dt
import json
import os
import sys
import tempfile
import time
import urllib.request

from . import build as B
from . import geo
from .sources import flipp, hammer, statcan

ROOT = os.environ.get("GRX_ROOT", ".")


def cfg():
    with open(os.path.join(ROOT, "config.json")) as f:
        return json.load(f)


def write(path, obj):
    path = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, separators=(",", ":"))


def cmd_flipp(full):
    c = cfg()
    fsas = geo.sweep(c["home_fsa"], c["radius_km"], c.get("max_fsas", 10)) if full else [(c["home_fsa"], 0.0)]
    print(f"Flipp sweep over {len(fsas)} FSAs: {[f for f, _ in fsas]}")
    rows, errors = flipp.collect(fsas)
    if not rows:
        print(f"No rows collected ({errors} errors); keeping previous data.")
        return 1 if errors else 0
    month = time.strftime("%Y-%m")
    hist = os.path.join(ROOT, f"data/flipp/{month}.jsonl")
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    old = B.load(os.path.join(ROOT, "data/flipp/latest.json"), {"rows": []})
    seen = set()   # dedupe against this month's log, so each distinct price is logged once
    if os.path.exists(hist):
        with open(hist) as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    seen.add((r["item"], r["kind"], r["merchant"], r["name"], r["price"], r.get("valid_from")))
    new = [r for r in rows if (r["item"], r["kind"], r["merchant"], r["name"], r["price"], r.get("valid_from")) not in seen]
    with open(hist, "a") as f:
        for r in new:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    if full:
        latest = {"at": rows[0]["seen"], "fsas": fsas, "rows": rows}
    else:  # light run: refresh the home FSA rows, keep the rest of the last full sweep
        keep = [r for r in old["rows"] if r.get("fsa") != c["home_fsa"]]
        latest = {"at": rows[0]["seen"], "fsas": old.get("fsas") or fsas, "rows": keep + rows}
    write("data/flipp/latest.json", latest)
    print(f"{len(rows)} rows, {len(new)} new price points, {errors} errors")
    return 0


def cmd_hammer():
    with tempfile.TemporaryDirectory() as d:
        z = hammer.download(os.path.join(d, "h.zip"))
        series, shrink, audit = hammer.parse(z, since_days=cfg().get("hammer_days", 730))
    try:
        with urllib.request.urlopen(hammer.LASTUPDATED, timeout=30) as r:
            last = r.read().decode().strip()[:40]
    except Exception:
        last = None
    vendors = sorted({v for s in series.values() for v in s})
    write("data/hammer/series.json", series)
    write("data/hammer/shrink.json", shrink)
    write("data/audit/hammer_cheapest.json", audit)   # committed: the products behind each shelf price
    for iid, vs in sorted(audit.items()):
        for v, xs in sorted(vs.items()):
            if xs:
                x = xs[0]
                print(f"  audit {iid:16} {v:12} {x['unit_price']:9.4f}  {x['price']}  [{x['units']}] {x['name'][:70]}")
    write("data/hammer/meta.json", {"fetched": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "last_load": last,
                                     "vendors": vendors, "items": len(series)})
    print(f"Hammer: {len(series)} items, vendors {vendors}, {len(shrink)} shrink events")


def cmd_statcan():
    with tempfile.TemporaryDirectory() as d:
        z = statcan.download(os.path.join(d, "s.zip"))
        avg = statcan.parse(z)
    write("data/statcan/avg.json", avg)
    print(f"StatCan: {len(avg)} catalog items mapped")


def check_rules(board, rules):
    hits = []
    by = {i["id"]: i for i in board["items"]}
    for r in rules:
        it = by.get(r["item"])
        if not it or "best" not in it["call"]:
            continue
        c, show = it["call"], it["show"]
        price = c["best"] * show
        why = None
        if "below" in r and price <= r["below"]:
            why = f"{it['label']} is ${price:.2f} {it['show_label']} at {c['where']} (your line: ${r['below']:.2f})"
        if r.get("signal") and c["action"] == r["signal"]:
            why = f"{it['label']}: {c['action']}. {c['reason']}"
        if why:
            key = f"{r['item']}|{r.get('below', r.get('signal'))}|{c['where']}|{round(price, 2)}"
            hits.append({"key": key, "title": f"GRX alert: {it['label']} {c['action'] if r.get('signal') else 'under $' + format(r['below'], '.2f')}", "body": why})
    return hits


def gh(method, path, body=None):
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}{path}", method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def cmd_alerts():
    board = B.load(os.path.join(ROOT, "site/data/board.json"), None)
    if not board:
        return
    state = B.load(os.path.join(ROOT, "data/alerts_state.json"), {})
    hits = [h for h in check_rules(board, cfg().get("watch", [])) if h["key"] not in state]
    for h in hits:
        print("ALERT:", h["body"])
        if os.environ.get("GITHUB_TOKEN"):
            try:
                gh("POST", "/issues", {"title": h["title"], "body": h["body"] + "\n\nDashboard: see the Pages site for this repo.", "labels": ["alert"]})
            except Exception as e:
                print("  ! could not open issue:", e)
        state[h["key"]] = board["generated"]
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=21)).strftime("%Y-%m-%d")
    write("data/alerts_state.json", {k: v for k, v in state.items() if v >= cutoff})


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    c = argv[0]
    if c == "flipp":
        return cmd_flipp("--full" in argv)
    if c == "hammer":
        return cmd_hammer()
    if c == "statcan":
        return cmd_statcan()
    if c == "build":
        b = B.build(ROOT)
        print(f"board: {len(b['items'])} items, {b['sources']['flipp']['rows']} live offers from {b['sources']['flipp']['merchants']} merchants")
        return 0
    if c == "alerts":
        return cmd_alerts()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
