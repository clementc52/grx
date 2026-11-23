"""Official monthly average retail prices (StatCan table 18-10-0245-01).

Built by StatCan from retailers' checkout (scanner) data, by province.
Used as the 'what normal costs' baseline next to live store prices.
Open Government Licence - Canada.
"""
import csv
import io
import json
import urllib.request
import zipfile

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 GRX-grocery-research"}

from .. import units
from ..catalog import ITEMS

WDS = "https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/18100245/en"
FALLBACK = "https://www150.statcan.gc.ca/n1/tbl/csv/18100245-eng.zip"


def download(path, log=print):
    url = FALLBACK
    try:
        with urllib.request.urlopen(urllib.request.Request(WDS, headers=UA), timeout=60) as r:
            j = json.loads(r.read())
            url = j.get("object") or FALLBACK
    except Exception as e:
        log(f"  ! WDS lookup failed ({e}); using fallback URL")
    log(f"  downloading {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def _item_for(product):
    p = product.lower()
    for it in ITEMS:
        if it["statcan"] and all(w in p for w in it["statcan"].split()):
            return it
    return None


def parse(zip_path, geos=("Canada", "Ontario"), months=36):
    z = zipfile.ZipFile(zip_path)
    name = next(n for n in z.namelist() if n.endswith(".csv") and "MetaData" not in n)
    rows = csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig", newline=""))
    out = {}
    for r in rows:
        geo = r.get("GEO")
        if geo not in geos:
            continue
        prod = r.get("Products") or r.get("Product") or ""
        it = _item_for(prod)
        if not it:
            continue
        try:
            v = float(r.get("VALUE") or "")
        except ValueError:
            continue
        post = "kg" if "per kilogram" in prod.lower() else ""
        up = units.unit_price(v, it["unit"], prod, "", post)
        if up is None:
            continue
        s = out.setdefault(it["id"], {}).setdefault(geo, {"product": prod, "m": {}, "raw": {}})
        s["m"][r["REF_DATE"][:7]] = round(up, 4)
        s["raw"][r["REF_DATE"][:7]] = v
    for it, geos_ in out.items():
        for g, s in geos_.items():
            ks = sorted(s["m"])[-months:]
            s["m"] = {k: s["m"][k] for k in ks}
            s["raw"] = {k: s["raw"][k] for k in ks if k in s["raw"]}
    return out
