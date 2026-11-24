"""Canonical grocery items. Each one is a 'ticker' tracked across every store.

Matching is by regex on the listing name (lower-cased): `inc` must match,
`exc` must not. Prices are compared per base unit (see units.py), so
different brands and pack sizes of the same thing are directly comparable.

Fields:
  id, label, category, unit, show (base units per display unit), show_label,
  terms (Flipp search queries), inc, exc, shelf (days it keeps),
  use (days one display unit lasts a typical 2-person household),
  statcan (words that identify the StatCan 18-10-0245-01 product, or None)
"""
import re

_C = [
 # id, label, cat, unit, show, show_label, terms, inc, exc, shelf, use, statcan
 ("eggs-large", "Large eggs", "Dairy & eggs", "egg", 12, "per dozen", ["eggs"], r"\beggs?\b", r"medium|small|jumbo|extra large|\bxl\b|liquid|egg whites|whites\b|yolk|boiled|creation|salted|duck|quail|tart|pickl|just egg|substitut|puff|noodle|fried|salad|chocolate|nog|roll|bite|sandwich|2go|jumbo pack", 35, 7, "eggs 12"),
 ("milk-2", "2% milk", "Dairy & eggs", "L", 4, "per 4 L", ["2% milk", "milk"], r"\b2\s?%.*milk|milk.*\b2\s?%", r"chocolate|lactose|evaporated|condensed|powder|oat|almond|soy|goat|a2", 12, 5, "milk 2 litres"),
 ("butter", "Butter", "Dairy & eggs", "kg", .454, "per 454 g", ["butter"], r"\bbutter\b", r"plant|dairy.?free|vegan|seed|sunflower|pumpkin|sesame|soy|almond|popping|lay.?s|honey butter|becel|i can.?t believe|not butter|sesame|turkey|danish|peanut|almond|cashew|apple|nut|cookie|chicken|cup|tart|popcorn|garlic|spread|margarine|croissant|shea|cocoa|milk|bean|squash|sauce|pastry|puff|chickpea|entree|tasty bite|biscuit|cracker|toffee|scotch|lettuce|cream|tub|whipped|ghee|flavour|flavor|candle|lotion|soap|balm|brioche|bread|bun|roll", 120, 21, "butter 454"),
 ("cheddar", "Cheddar block", "Dairy & eggs", "kg", .4, "per 400 g", ["cheddar"], r"cheddar", r"sausage|pierog|perog|ramen|noodle|rice|sourdough|bistro|ben.?s|chive|stir.?fry|express|smoked|lactose|shred|slice|string|crack|popcorn|chip|sauce|dip|soup|bun|bagel|puff|kraft dinner|macaroni|biscuit|goldfish|pasta|mac\b|velveeta|cheetos|snack|flavou?r|ruffles|crunch|broccoli|bread|pretzel|jalape|nacho|bite|melt|powder|spread", 60, 14, "cheddar"),
 ("apples", "Apples", "Produce", "kg", 1, "per kg", ["apples"], r"\bapples?\b", r"juice|sauce|cider|pie|chip|turnover|crisp|vinegar|strudel|fritter|dried|pear|sauce|bar", 30, 7, "apples"),
 ("potatoes", "Potatoes", "Produce", "kg", 1, "per kg", ["potatoes"], r"potato", r"chip|sweet|fries|salad|mash|wedge|hash|tot|skin|pierog|starch|bread|bun|perogie|soup|seasoning|parisienne|mini|little gems|baby|fingerling|creamer|nugget", 45, 7, "potatoes"),
 ("onions", "Yellow onions", "Produce", "kg", 1, "per kg", ["onions"], r"\bonions?\b", r"ring|soup|powder|green|red|sweet|fried|dip|chip|pickled|bagel|crisp", 45, 10, "onions"),
 ("carrots", "Carrots", "Produce", "kg", 1, "per kg", ["carrots"], r"carrot", r"cake|juice|muffin|baby food|chip|stick snack|soup|peas", 30, 10, "carrots"),
 ("chicken-breast", "Chicken breast (boneless)", "Meat & seafood", "kg", 1, "per kg", ["chicken breast"], r"chicken breast", r"smoked|slices?\b|herb|lemon|garlic|teriyaki|steamed|kokiio|snack|gluten free|nugget|strip|burger|sandwich|soup|sausage|deli|sliced|breaded|frozen|cutlet|wing|thigh|drumstick|cooked|roast(ed)?|wrap|salad|pie|bite|ready|meal|kiev|cordon|tender|butter chicken|bacon wrap|schnitzel|stuffed|marinated|souvlaki|skewer|kebab|parmesan|panko|seasoned", 3, 4, "chicken breast"),
 ("chicken-thigh", "Chicken thighs", "Meat & seafood", "kg", 1, "per kg", ["chicken thighs"], r"chicken thigh", r"cooked|bbq|frozen|wrap|meal|sandwich|soup|bite|nugget", 3, 4, "chicken thigh"),
 ("ground-beef", "Lean ground beef", "Meat & seafood", "kg", 1, "per kg", ["ground beef"], r"ground beef|lean ground", r"pork|chicken|turkey|burger|patty|patties|lasagna|sauce|chili|frozen meal|taco kit|meatball|pie|veal|plant|gardein|beyond|lamb|alternative|vegan|meatless", 3, 5, "ground beef"),
 ("bread", "Sliced bread", "Bakery", "kg", .675, "per 675 g loaf", ["bread"], r"\bbread\b", r"crumb|stick|naan|pita|garlic|banana|corn|french|pudding|maker|knife|flour|mix|dough|fruit|raisin|cheese|frozen|stuffing|crouton|machine|bag|loaf pan|zucchini|monkey|flat|bun", 7, 6, "white bread"),
 ("rice", "White rice", "Pantry", "kg", 8, "per 8 kg bag", ["rice"], r"\brice\b", r"glutinous|sticky|brown|arborio|sushi|black|red rice|wild|cake|cracker|chip|krispie|crispy|noodle|vinegar|paper|milk|wine|cooker|pudding|flour|seasoning|side|bowl|ready|instant|minute|cauliflower|stick|bran|cereal|snack|roll|bag in|sushi|risotto|pilaf|mix|wild|brown rice syrup", 365, 60, "rice"),
 ("canola-oil", "Canola oil", "Pantry", "L", 3, "per 3 L", ["canola oil", "vegetable oil"], r"canola|vegetable oil", r"spray|mayo|margarine|chip|tuna|in canola|cooking spray", 365, 60, "canola"),
 ("peanut-butter", "Peanut butter", "Pantry", "kg", 1, "per kg", ["peanut butter"], r"peanut butter", r"cup|cookie|bar|cereal|chocolate|pretzel|treat|dog|cracker|ice cream|filled|sandwich|bite|powder|protein|spread with", 180, 21, "peanut butter"),
 ("flour", "All-purpose flour", "Pantry", "kg", 2.5, "per 2.5 kg", ["flour"], r"\bflour\b", r"tortilla|mix|corn|almond|rice|coconut|cassava|tapioca|chickpea|oat|gluten|cake|pancake|pizza|bread|potato|self|durum|atta|desi|whole wheat|chapati|besan|gram|semolina|maida|cookie|cracker", 365, 45, "flour"),
 ("sugar", "White sugar", "Pantry", "kg", 2, "per 2 kg", ["white sugar", "granulated sugar"], r"granulated|white sugar|sugar,? (white|granulated)", r"rock|turbinado|demerara|yellow|golden|cane sugar|raw|stick|corn|heart|brown|icing|free|cookie|candy|cane|snap|cereal|syrup|substitute|coconut|less|reduced|no sugar|zero|sweetener|cube|maple|donut|scrub|pea|crisp|wafer", 720, 45, "sugar"),
 ("canned-tomatoes", "Canned tomatoes", "Pantry", "L", .796, "per 796 ml can", ["canned tomatoes", "diced tomatoes"], r"(diced|crushed|whole|stewed|plum).*tomato|tomato.*(diced|crushed|whole|plum)", r"sauce|paste|soup|ketchup|salsa|juice|sun.?dried|chip|basil pasta", 720, 7, "canned tomatoes"),
 ("coffee", "Ground coffee", "Pantry", "kg", .9, "per 900 g", ["ground coffee", "coffee"], r"ground coffee|coffee.*\bground\b|\bground\b.*coffee|roast.*coffee|coffee.*roast", r"sumiyaki|\bcan\b|drink|bottle|enhancer|foam|3.in.1|three in one|mix\b|whitener|white coffee|pod|k-cup|kcup|capsule|cup|creamer|mate|cake|ice cream|maker|machine|filter|mug|liqueur|cold brew|latte|frapp|instant|drink|bean.*whole|beverage|syrup|candy|flavour|sauce|table|chocolate|bar|cookie", 120, 30, "coffee"),
]

# When a flyer omits the size, these are the sizes flyers almost always mean.
# Rows priced this way carry assumed=True and are marked "~" on the site.
DEFAULT_SIZE = {}   # sizes are never assumed: a listing without a printed size is skipped

ITEMS = []
for row in _C:
    (i, label, cat, unit, show, show_label, terms, inc, exc, shelf, use, sc) = row
    ITEMS.append({"id": i, "label": label, "cat": cat, "unit": unit, "show": show, "show_label": show_label,
                  "terms": terms, "inc": re.compile(inc, re.I), "exc": re.compile(exc, re.I) if exc else None,
                  "shelf": shelf, "use": use, "statcan": sc, "default": DEFAULT_SIZE.get(i)})
BY_ID = {it["id"]: it for it in ITEMS}

# Typical Ontario price per display unit (late 2026, rounded). Only used as a sanity
# fence: a listing whose unit price lands outside 0.4x-2.6x of this is a parsing or
# matching error (wrong pack size, a garnish, a sauce), so it is dropped.
REF = {"eggs-large": 4.5, "milk-2": 6.5, "butter": 6.5, "cheddar": 6.5, "apples": 4.0, "potatoes": 1.6, "onions": 2.2, "carrots": 1.8, "chicken-breast": 17, "chicken-thigh": 12, "ground-beef": 12, "bread": 3.5, "rice": 20, "canola-oil": 9, "peanut-butter": 7, "flour": 6.0, "sugar": 4.5, "canned-tomatoes": 2.5, "coffee": 16}
for _it in ITEMS:
    _it["ref"] = REF[_it["id"]] / _it["show"]

# Pet food, baby food and similar never count for people groceries.
NOT_HUMAN = re.compile(r"\b(dog|dogs|cat|cats|puppy|kitten|pet|purina|pedigree|whiskas|friskies|fancy feast|baby food|infant|toddler)\b", re.I)


# Largest pack (in base units) that still counts as a household purchase; bigger is wholesale.
MAX_PACK = {"eggs-large": 30, "milk-2": 4.01, "butter": 1.0, "cheddar": 1.4, "apples": 5.0, "potatoes": 10.0, "onions": 5.0,
            "carrots": 5.0, "chicken-breast": 5.0, "chicken-thigh": 5.0, "ground-beef": 3.0, "bread": 1.4, "rice": 10.0,
            "canola-oil": 5.0, "peanut-butter": 2.0, "flour": 10.0, "sugar": 4.0, "canned-tomatoes": 3.0, "coffee": 1.5}
for _it in ITEMS:
    _it["max_pack"] = MAX_PACK[_it["id"]]


def household(item, pack):
    return pack is None or pack <= item["max_pack"] * 1.02


def plausible(item, unit_price):
    return unit_price is not None and 0.4 * item["ref"] <= unit_price <= 2.6 * item["ref"]


# Private labels: price-match policies generally exclude competitors' house brands.
PRIVATE_LABELS = re.compile(r"\b(no name|president'?s choice|\bpc\b|pc®|great value|equate|compliments|selection|irresistibles|life smart|our finest|longo'?s|farm boy|kirkland|sensations|western family|our compliments|smartly|t&t|foodland|freshco|giant tiger|rooster)\b", re.I)


# Head noun: the product's last meaningful word must be the grocery itself, so
# "Coffee Whitener", "Banana Chili Sauce" and "Bacon Pizza Pops" are rejected.
HEAD = {
 "eggs-large": r"eggs?",
 "milk-2": r"milk",
 "butter": r"butter",
 "cheddar": r"cheddar|cheese",
 "apples": r"apples?",
 "potatoes": r"potato(es)?",
 "onions": r"onions?",
 "carrots": r"carrots?",
 "chicken-breast": r"breasts?",
 "chicken-thigh": r"thighs?",
 "ground-beef": r"beef",
 "bread": r"bread|loaf",
 "rice": r"rice",
 "canola-oil": r"oil|canola",
 "peanut-butter": r"butter",
 "flour": r"flour",
 "sugar": r"sugar",
 "canned-tomatoes": r"tomato(es)?|passata",
 "coffee": r"coffee|roast|beans?|espresso|blend",
}
_DESC = re.compile(r"^(?:\d[\d.,/x×=\-]*\s*[a-z%]*|[\d.]+(?:kg|g|ml|l|lb|lbs|oz|ct|pk|pcs?|un|ea)|large|medium|small|jumbo|xl|size|salted|unsalted|"
                   r"original|plain|regular|fresh|organic|natural|classic|value|pack|packs|club|family|bag|bags|bunch|each|count|ct|pk|singles|"
                   r"sold|in|of|loose|bulk|box|tub|jug|carton|bottle|case|tray|lb|lbs|kg|g|gram|grams|ml|l|litre|litres|white|brown|red|yellow|"
                   r"light|smooth|crunchy|creamy|unsweetened|sweetened|extra|old|mild|aged|marble|block|brick|boneless|skinless|bone-in|skin-on|"
                   r"halal|lean|whole|grade|a|canada|ontario|product|imported|cello|approx|approximately|avg|average|per|each\.|ea|ea\.|only|"
                   r"double|triple|mega|super|ply|2-ply|3-ply|sheets?|rolls?=?|split|value-pack|size:|variety|assorted|wild|atlantic|pacific|"
                   r"hass|english|seedless|greenhouse|vine|on|the|ripe|bunched|thai|jasmine|long|grain|parboiled|basmati|frozen|cut|diced|crushed|"
                   r"whole|instant|quick|large-flake|rolled|ground|dark|medium-dark|roast|decaf|decaffeinated|pure|virgin|extra-virgin|refined|"
                   r"liquid|concentrated|scent|scented|unscented|fragrance|free|clumping|lightweight|dry|adult|puppy|senior|mixed|firm|soft|"
                   r"allpurpose|all-purpose|purpose|all|no|pulp|taste|king|x|inch|in\.|range|run|omega-3|farm|style|thick|slice|sliced|unbleached|bleached)$", re.I)
# Items whose names usually trail with a flavour or variety ("Ice Cream French Vanilla"):
# the head may sit anywhere, as long as no other product noun follows it.
RELAXED = {"eggs-large", "bread", "coffee", "cheddar", "peanut-butter", "apples", "milk-2", "flour", "sugar", "chicken-thigh", "canned-tomatoes", "ground-beef", "chicken-breast"}
_BADNOUN = re.compile(r"^(whip|sauce|pie|pies|bars?|cookies?|snacks?|crackers?|danish|pops|strips|spice|spices|crisps|treat|treats|cake|cakes|"
                      r"muffins?|twists|tarts?|shoots|salad|base|squeeze|whitener|creamer|cereal|drinks?|candy|candies|gummies|gummy|"
                      r"chips|sticks|bites|rolls|cheese|crust|dough|seasoning|mix|filling|frosting|icing|spread|dip|soup|noodles?|"
                      r"dumplings?|pastry|pastries|biscuits?|wafers?|sandwich|sandwiches|bun|buns|pudding|syrup|jam|jelly|powder|"
                      r"pods?|capsules?|k-cups?|beer|lager|ale|cocktail|liqueur|mints|lotion|candle|freshener|bowl|meal|kit|pizza|pizzas|hash|"
                      r"potstickers?|gyoza|turnovers?|croissants?|strudel|waffles?|chunks|nuggets?|perogies|pierogi|pierogies|sausages?|ramen|strip|yeast|olives|crackers|patties|dressing|sardines?|mackerel)$", re.I)


def head_ok(name, item):
    rx = HEAD.get(item["id"])
    if not rx:
        return True
    hrx = re.compile(r"^(?:" + rx + r")$", re.I)
    # Candidate product phrases: each "X or Y" / "Brand - Product" segment, up to its first comma,
    # bracket or "with" (what follows describes the product rather than naming it).
    phrases = [re.split(r",|\(|\)|\||;|:|\s+(?:with|w/|avec)\s+", seg)[0]
               for seg in re.split(r"\s+(?:or|ou)\s+|\s+-\s+|\s+–\s+", name or "")]
    for ph in phrases:
        words = re.findall(r"[a-z0-9'’&.%=/×-]+", ph.lower())
        words = [w.strip(".'’") for w in words if w.strip(".'’")]
        while words and _DESC.match(words[-1]):
            words.pop()
        if any(_BADNOUN.match(w) and not hrx.match(w) for w in words):
            continue   # a compound product: pizza pops with bacon, perogies with cheddar
        if words and hrx.match(words[-1]):
            return True
        if item["id"] in RELAXED:
            idx = [i for i, w in enumerate(words) if hrx.match(w)]
            if idx and not any(_BADNOUN.match(w) and not hrx.match(w) for w in words):
                return True
    return False


def match(name, item):
    n = (name or "").lower()
    if item["cat"] != "Pets" and NOT_HUMAN.search(n):
        return False
    if not item["inc"].search(n):
        return False
    if item["exc"] and item["exc"].search(n):
        return False
    return head_ok(n, item)


def classify(name):
    """All catalog items a listing name matches (usually 0 or 1)."""
    return [it for it in ITEMS if match(name, it)]
