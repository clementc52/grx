"""Parse package sizes and flyer price text into comparable unit prices.

Every catalog item has a base unit: 'kg', 'L', 'egg', 'roll' or 'each'.
`unit_price()` returns dollars per base unit, or None when the listing
cannot be normalised honestly (we never guess a size).
"""
import re

LB = 0.45359237

_MULTIPACK = re.compile(r"(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b", re.I)
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|kilograms?|g|gr|grams?|lbs?|pounds?|oz|l|litres?|liters?|ml)\b", re.I)
_EGGS = re.compile(r"(\d+)\s*(?:'s|’s|s\b|pcs?\b|pk\b|pack\b|ct\b|count\b|un\b|units?\b|eggs?\b|ea\b|each\b|-?pack\b)", re.I)
_EGGS_AFTER = re.compile(r"eggs?\W{0,3}(\d{1,3})\b", re.I)
_DOZEN = re.compile(r"\b(\d+)?\s*dozen\b", re.I)
_ROLLS = re.compile(r"(\d+)\s*(?:double|triple|mega|super|giant|jumbo|huge|regular|big|=\s*\d+)?\s*rolls?\b", re.I)
_MONEY = re.compile(r"(\d+(?:\.\d{1,2})?)")
_MULTIBUY = re.compile(r"^\s*(\d+)\s*(?:/|for)\s*\$?\s*$", re.I)


def money(v):
    """'$4.99', '4.99', 4.99, '2/$5' (-> None) -> float or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = str(v).replace(",", "").strip()
    if not s or "/" in s and not s.startswith("$"):
        return None
    m = _MONEY.search(s)
    if not m:
        return None
    x = float(m.group(1))
    if "¢" in s and x >= 1 and "$" not in s:
        x /= 100
    return x if x > 0 else None


def _num(s):
    return float(s.replace(",", "."))


def mass_or_volume(text):
    """Return (amount, 'g'|'ml') for the package, handling '6 x 355 ml'."""
    t = text or ""
    m = _MULTIPACK.search(t)
    if m:
        n, amt, u = int(m.group(1)), _num(m.group(2)), m.group(3).lower()
        base = {"kg": ("g", 1000), "g": ("g", 1), "l": ("ml", 1000), "ml": ("ml", 1)}[u]
        return n * amt * base[1], base[0]
    m = _SIZE.search(t)
    if not m:
        return None
    amt, u = _num(m.group(1)), m.group(2).lower()
    if u.startswith("kg") or u.startswith("kilo"):
        return amt * 1000, "g"
    if u in ("g", "gr") or u.startswith("gram"):
        return amt, "g"
    if u.startswith("lb") or u.startswith("pound"):
        return amt * LB * 1000, "g"
    if u == "oz":
        return amt * 28.3495, "g"
    if u == "ml":
        return amt, "ml"
    return amt * 1000, "ml"


def count_of(text, kind):
    t = text or ""
    if kind == "egg":
        m = _DOZEN.search(t)
        if m:
            return 12 * int(m.group(1) or 1)
        for m in _EGGS.finditer(t):
            n = int(m.group(1))
            if 4 <= n <= 360:
                return n
        m = _EGGS_AFTER.search(t)
        if m and 4 <= int(m.group(1)) <= 360:
            return int(m.group(1))
        return None
    if kind == "roll":
        m = _ROLLS.search(t)
        return int(m.group(1)) if m else None
    return None


def per_text_unit(post):
    """Flyer 'post_price_text' like '/lb', 'lb', '/kg', '/100 g', 'ea.' -> multiplier to $/kg or None."""
    p = (post or "").lower().replace(" ", "").lstrip("/$.")
    # The first unit printed is what the price is for: "lb 13.21/kg" means $/lb.
    m = re.match(r"(?:ea\.?|each)?/?(100g|lb|kg)", p)
    if not m:
        return None
    u = m.group(1)
    return ("kg", 10.0) if u == "100g" else ("kg", 1.0) if u == "kg" else ("kg", 1 / LB)


def effective_price(current, pre_text=None):
    """Flyer price after multi-buy: current=5, pre='2/' -> 2.50."""
    c = money(current)
    if c is None:
        return None
    m = _MULTIBUY.match(pre_text or "")
    if m:
        n = int(m.group(1))
        if 1 < n <= 12:
            return c / n
    return c


_RANGE = re.compile(r"\d+(?:\.\d+)?\s*(?:-|–|/|to)\s*\d+(?:\.\d+)?\s*(?:kg|g|ml|l|lb|lbs|oz)\b", re.I)
_SIZE_TOKEN = re.compile(r"\d+(?:\.\d+)?\s*(?:kg|g|ml|l|lb|lbs|oz|'s|pcs?|pack|pk|ct|count|un|ea)\b", re.I)
_ORWORD = re.compile(r"\s(?:or|ou)\s", re.I)


_APPROX = re.compile(r"~|\bapprox|\bavg\b|\baverage\b|\bvalue pack \(|\bvariable weight", re.I)


def ambiguous(name):
    """True when a listing can't be priced per unit with certainty:
    a size range ("227/250 G", "800-930 g"), an "X or Y" ad that prints
    more than one size ("YOGURT 650 g or CREAM CHEESE 227 g"), or a
    variable-weight pack ("Value Pack (~3lb)") whose price may be per lb."""
    n = name or ""
    if _APPROX.search(n):
        return True
    if _RANGE.search(n):
        return True
    if _ORWORD.search(n) and len(_SIZE_TOKEN.findall(n)) > 1:
        return True
    return False


_OR = re.compile(r"\s+(?:or|ou)\s+|\s*/\s*(?=[a-z])", re.I)


def segment(name, rx):
    """'DANONE YOGURT (650g) or NO NAME CREAM CHEESE (227g)' -> the part that matches rx."""
    parts = [p for p in _OR.split(name or "") if p.strip()]
    if len(parts) <= 1:
        return name
    hits = [p for p in parts if rx.search(p.lower())]
    if not hits:
        return name
    seg = hits[0]
    # 'PC ORANGE JUICE 2.5 L OR SIGGI'S YOGURT 650/750 G': size belongs to its own segment;
    # if our segment has no size but another does, the size is ambiguous -> keep only our text.
    return seg


def unit_price(price, unit, name="", size_text="", post_text=""):
    """Dollars per base unit for one listing, or None.

    unit: 'kg' | 'L' | 'egg' | 'roll' | 'each'
    """
    if price is None or price <= 0:
        return None
    txt = f"{name} {size_text}"
    if unit == "kg":
        per = per_text_unit(post_text)
        if per:
            return price * per[1]
        mv = mass_or_volume(txt)
        if mv and mv[1] == "g" and mv[0] >= 20:
            return price / (mv[0] / 1000)
        return None
    if unit == "L":
        mv = mass_or_volume(txt)
        if mv and mv[1] == "ml" and mv[0] >= 50:
            return price / (mv[0] / 1000)
        return None
    if unit in ("egg", "roll"):
        n = count_of(txt, unit)
        return price / n if n else None
    if unit == "each":
        return None if per_text_unit(post_text) else price   # priced by weight: not comparable per item
    return None
