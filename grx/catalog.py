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
 ("butter", "Butter", "Dairy & eggs", "kg", .454, "per 454 g", ["butter"], r"\bbutter\b", r"seed|sunflower|pumpkin|sesame|soy|almond|popping|lay.?s|honey butter|becel|i can.?t believe|not butter|sesame|turkey|danish|peanut|almond|cashew|apple|nut|cookie|chicken|cup|tart|popcorn|garlic|spread|margarine|croissant|shea|cocoa|milk|bean|squash|sauce|pastry|puff|chickpea|entree|tasty bite|biscuit|cracker|toffee|scotch|lettuce|cream|tub|whipped|ghee|flavour|flavor|candle|lotion|soap|balm|brioche|bread|bun|roll", 120, 21, "butter 454"),
 ("cheddar", "Cheddar block", "Dairy & eggs", "kg", .4, "per 400 g", ["cheddar"], r"cheddar", r"shred|slice|string|crack|popcorn|chip|sauce|dip|soup|bun|bagel|puff|kraft dinner|macaroni|biscuit|goldfish|pasta|mac\b|velveeta|cheetos|snack|flavou?r|ruffles|crunch|broccoli|bread|pretzel|jalape|nacho|bite|melt|powder|spread", 60, 14, "cheddar"),
 ("yogurt", "Plain yogurt (large tub)", "Dairy & eggs", "kg", .75, "per 750 g", ["yogurt"], r"yog(h)?urt", r"drink|tube|bar|cup|bite|raisin|frozen|pretzel|dog|cat|100\s?g\b|4\s?x|6\s?x|8\s?x|12\s?x", 21, 6, "yogurt"),
 ("cream-cheese", "Cream cheese", "Dairy & eggs", "kg", .25, "per 250 g", ["cream cheese"], r"cream cheese", r"bagel|cake|frosting|dip|wonton", 45, 14, None),
 ("oat-milk", "Oat milk", "Dairy & eggs", "L", 1.75, "per 1.75 L", ["oat milk", "oat beverage"], r"\boat\b.*(milk|beverage|drink)", r"cookie|bar|cereal|creamer", 30, 7, None),
 ("bananas", "Bananas", "Produce", "kg", 1, "per kg", ["bananas"], r"banana", r"chip|bread|muffin|loaf|pudding|split|baby|cake|dried|pepper|smoothie|frozen|plantain|oat|lea(f|ves)|candy|brownie|cookie|peelz|jelly|chubby|go banana|bar\b|yogurt|milk|cereal|flavou?r|puree|pouch|snack|crisp|gummi|gummy|leather|nut|cream", 6, 4, "bananas"),
 ("apples", "Apples", "Produce", "kg", 1, "per kg", ["apples"], r"\bapples?\b", r"juice|sauce|cider|pie|chip|turnover|crisp|vinegar|strudel|fritter|dried|pear|sauce|bar", 30, 7, "apples"),
 ("avocados", "Avocados", "Produce", "each", 1, "each", ["avocado"], r"avocado", r"oil|dip|guac|toast|bar|mayo|sauce", 6, 2, None),
 ("potatoes", "Potatoes", "Produce", "kg", 1, "per kg", ["potatoes"], r"potato", r"chip|sweet|fries|salad|mash|wedge|hash|tot|skin|pierog|starch|bread|bun|perogie|soup|seasoning", 45, 7, "potatoes"),
 ("onions", "Yellow onions", "Produce", "kg", 1, "per kg", ["onions"], r"\bonions?\b", r"ring|soup|powder|green|red|sweet|fried|dip|chip|pickled|bagel|crisp", 45, 10, "onions"),
 ("carrots", "Carrots", "Produce", "kg", 1, "per kg", ["carrots"], r"carrot", r"cake|juice|muffin|baby food|chip|stick snack|soup|peas", 30, 10, "carrots"),
 ("tomatoes", "Tomatoes", "Produce", "kg", 1, "per kg", ["tomatoes"], r"tomato", r"sauce|paste|ketchup|soup|canned|diced|crushed|juice|sun.?dried|salsa|puree|chip|basil|bruschetta|cherry|grape|sardine|mackerel|pasta|passata|strained", 8, 5, "tomatoes"),
 ("broccoli", "Broccoli", "Produce", "each", 1, "each", ["broccoli"], r"broccoli", r"frozen|slaw|salad|soup|rice|cheese|floret|tot|mix", 7, 5, None),
 ("cucumber", "English cucumber", "Produce", "each", 1, "each", ["cucumber"], r"cucumber", r"pickle|mini|lotion|mask|water|sauce|salad|tzatziki|dill", 7, 4, "cucumber"),
 ("lettuce", "Romaine lettuce", "Produce", "each", 1, "each", ["romaine"], r"romaine", r"salad kit|caesar|dressing|heart.*3|kit|mix", 7, 5, "romaine"),
 ("strawberries", "Strawberries", "Produce", "kg", 1, "per kg", ["strawberries"], r"strawberr", r"jam|yogurt|frozen|cereal|syrup|milk|cake|juice|dried|smoothie|candy|pie|spread|sauce|drink|gel\b|crunch|blend|peach|banana|toast|bar\b|gummi|gummy|cookie|wafer|flavou?r|jelly|freeze.?dried", 4, 4, None),
 ("chicken-breast", "Chicken breast (boneless)", "Meat & seafood", "kg", 1, "per kg", ["chicken breast"], r"chicken breast", r"steamed|kokiio|snack|gluten free|nugget|strip|burger|sandwich|soup|sausage|deli|sliced|breaded|frozen|cutlet|wing|thigh|drumstick|cooked|roast(ed)?|wrap|salad|pie|bite|ready|meal|kiev|cordon|tender|butter chicken|bacon wrap|schnitzel|stuffed|marinated|souvlaki|skewer|kebab|parmesan|panko|seasoned", 3, 4, "chicken breast"),
 ("chicken-thigh", "Chicken thighs", "Meat & seafood", "kg", 1, "per kg", ["chicken thighs"], r"chicken thigh", r"cooked|bbq|frozen|wrap|meal|sandwich|soup|bite|nugget", 3, 4, "chicken thigh"),
 ("ground-beef", "Lean ground beef", "Meat & seafood", "kg", 1, "per kg", ["ground beef"], r"ground beef|lean ground", r"pork|chicken|turkey|burger|patty|patties|lasagna|sauce|chili|frozen meal|taco kit|meatball|pie|veal|plant|gardein|beyond|lamb|alternative|vegan|meatless", 3, 5, "ground beef"),
 ("pork-chops", "Pork chops", "Meat & seafood", "kg", 1, "per kg", ["pork chops"], r"pork (loin )?chop", r"bbq sauce|cooked|frozen meal|seasoning|shake", 3, 5, "pork loin"),
 ("bacon", "Bacon", "Meat & seafood", "kg", .375, "per 375 g", ["bacon"], r"\bbacon\b", r"bits|chip|flavour|flavor|burger|wrap|sandwich|dog|treat|turkey|ranch|dip|jam|cheese|salad|potato|bagel|egg|seasoning|bacon wrapped|bacon bites|focaccia|bread|carbonara|pasta|side dish|sidekicks|spam|onion|soup|plant|tempeh|vegan", 21, 10, "bacon"),
 ("salmon", "Salmon fillets", "Meat & seafood", "kg", 1, "per kg", ["salmon"], r"salmon", r"canned|smoked|sushi|cat|dog|burger|cake|sandwich|oil|treat|roe|wrap|jerky|flavour|clover leaf|gold seal|pie|213\s?g|in water|tin\b|dip|spread", 2, 7, "salmon"),
 ("shrimp", "Shrimp", "Meat & seafood", "kg", 1, "per kg", ["shrimp"], r"shrimp", r"ring|chip|cracker|noodle|dumpling|wonton|cocktail sauce|paste|flavour|sauce|ramen|roll|sushi|tempura|bagoong|dried|chips?\b|fried rice|\brice\b|breaded|battered|meal|bowl|dinner", 90, 14, None),
 ("tofu", "Firm tofu", "Meat & seafood", "kg", .45, "per 454 g", ["tofu"], r"\btofu\b", r"dessert|pudding|puff|skin|fried|marinated|smoked|jerky", 21, 7, "tofu"),
 ("bread", "Sliced bread", "Bakery", "kg", .675, "per 675 g loaf", ["bread"], r"\bbread\b", r"crumb|stick|naan|pita|garlic|banana|corn|french|pudding|maker|knife|flour|mix|dough|fruit|raisin|cheese|frozen|stuffing|crouton|machine|bag|loaf pan|zucchini|monkey|flat|bun", 7, 6, "white bread"),
 ("bagels", "Bagels", "Bakery", "each", 1, "per pack", ["bagels"], r"bagel", r"chip|bite|cream cheese|seasoning|dog|toaster|pizza|sandwich|egg", 6, 2, None),
 ("tortillas", "Flour tortillas", "Bakery", "kg", .6, "per 600 g", ["tortillas"], r"tortilla", r"chip|soup|crisp|bowl|scoop|corn chip|pizza|taco kit|kit|wrap sandwich", 21, 10, None),
 ("rice", "White rice", "Pantry", "kg", 8, "per 8 kg bag", ["rice"], r"\brice\b", r"cake|cracker|chip|krispie|crispy|noodle|vinegar|paper|milk|wine|cooker|pudding|flour|seasoning|side|bowl|ready|instant|minute|cauliflower|stick|bran|cereal|snack|roll|bag in|sushi|risotto|pilaf|mix|wild|brown rice syrup", 365, 60, "rice"),
 ("pasta", "Dry pasta", "Pantry", "kg", .9, "per 900 g", ["spaghetti", "pasta"], r"spaghetti|penne|fusilli|rotini|linguine|macaroni|pasta", r"sauce|salad|meal|kraft dinner|cheese|ready|bake|frozen|soup|fresh|ravioli|tortellini|lasagna|gnocchi|filled|chips|maker|pot|bowl|cup|kit", 365, 10, "pasta"),
 ("olive-oil", "Olive oil", "Pantry", "L", 1, "per L", ["olive oil"], r"olive oil", r"spray|tuna|sardine|chip|cracker|mayo|soap|hair|pomace|dressing|vinaigrette|marinated|in olive oil|with olive oil|cooking spray|bread|garlic|accents|infused|tomato|truffle|herb", 540, 45, "olive oil"),
 ("canola-oil", "Canola oil", "Pantry", "L", 3, "per 3 L", ["canola oil", "vegetable oil"], r"canola|vegetable oil", r"spray|mayo|margarine|chip|tuna|in canola|cooking spray", 365, 60, "canola"),
 ("peanut-butter", "Peanut butter", "Pantry", "kg", 1, "per kg", ["peanut butter"], r"peanut butter", r"cup|cookie|bar|cereal|chocolate|pretzel|treat|dog|cracker|ice cream|filled|sandwich|bite|powder|protein|spread with", 180, 21, "peanut butter"),
 ("flour", "All-purpose flour", "Pantry", "kg", 2.5, "per 2.5 kg", ["flour"], r"\bflour\b", r"tortilla|mix|corn|almond|rice|coconut|cassava|tapioca|chickpea|oat|gluten|cake|pancake|pizza|bread|potato|self|durum|atta|desi|whole wheat|chapati|besan|gram|semolina|maida|cookie|cracker", 365, 45, "flour"),
 ("sugar", "White sugar", "Pantry", "kg", 2, "per 2 kg", ["sugar"], r"\bsugar\b", r"stick|corn|heart|brown|icing|free|cookie|candy|cane|snap|cereal|syrup|substitute|coconut|less|reduced|no sugar|zero|sweetener|cube|maple|donut|scrub|pea|crisp|wafer", 720, 45, "sugar"),
 ("canned-tomatoes", "Canned tomatoes", "Pantry", "L", .796, "per 796 ml can", ["canned tomatoes", "diced tomatoes"], r"(diced|crushed|whole|stewed|plum).*tomato|tomato.*(diced|crushed|whole|plum)", r"sauce|paste|soup|ketchup|salsa|juice|sun.?dried|chip|basil pasta", 720, 7, "canned tomatoes"),
 ("cereal", "Breakfast cereal", "Pantry", "kg", .5, "per 500 g", ["cereal"], r"cereal|cheerios|corn flakes|bran flakes|shreddies|special k|honey nut|mini.?wheats", r"bar|bowl|milk|snack|baby|infant|cookie|treat", 180, 10, "cereal"),
 ("oats", "Rolled oats", "Pantry", "kg", 1, "per kg", ["oats", "oatmeal"], r"\boats?\b|oatmeal", r"cookie|bar|milk|beverage|drink|cereal|granola|bread|cup|instant packet|packet|bite|cheerios|square|crisp", 365, 21, "oats"),
 ("coffee", "Ground coffee", "Pantry", "kg", .9, "per 900 g", ["coffee"], r"coffee", r"enhancer|foam|3.in.1|three in one|mix\b|whitener|white coffee|pod|k-cup|kcup|capsule|cup|creamer|mate|cake|ice cream|maker|machine|filter|mug|liqueur|cold brew|latte|frapp|instant|drink|bean.*whole|beverage|syrup|candy|flavour|sauce|table|chocolate|bar|cookie", 120, 30, "coffee"),
 ("tea", "Black tea bags", "Pantry", "each", 1, "per box", ["tea bags", "tea"], r"\btea\b", r"iced|ice|kettle|cup|latte|kombucha|green tea mint|bubble|boba|drink|beverage|towel|tree|biscuit|cake|light|candle|chai latte|pot|infuser|lemon iced|peace tea|cracker|\d\s?l\b|bottle|can\b|tea tree|teapot|sweet tea|arizona|nestea|snapple|lipton ice", 540, 30, "tea"),
 ("orange-juice", "Orange juice", "Beverages", "L", 2.63, "per 2.63 L", ["orange juice"], r"orange juice", r"frozen concentrate|cocktail|punch|drink|soda|pop|vodka|smoothie|lemonade|blend|sparkling", 14, 7, "orange juice"),
 ("cola", "Cola (cans)", "Beverages", "L", 4.26, "per 12 x 355 ml", ["coca-cola", "pepsi", "cola"], r"coca.?cola|\bcoke\b|pepsi|\bcola\b", r"zero|diet|mini|cherry|vanilla|rum|whisky|chicken|bottle 2\s?l|2\s?l\b|syrup|glass|candy|gummy", 270, 14, None),
 ("sparkling-water", "Sparkling water", "Beverages", "L", 4.26, "per 12 x 355 ml", ["sparkling water"], r"sparkling water|soda water|bubly|perrier|san pellegrino", r"juice|wine|maker|machine|cartridge|syrup|lemonade", 270, 10, None),
 ("chips", "Potato chips", "Snacks", "kg", .235, "per 235 g bag", ["chips"], r"\bchips\b", r"chocolate|cookie|tortilla|pita|bagel|banana|apple|kale|veggie|corn|wood|fish|computer|poker|chip clip|dip|salsa|ahoy|bit|baking|pretzel|plantain|seaweed|rice", 90, 7, None),
 ("chocolate", "Chocolate bars", "Snacks", "kg", .1, "per 100 g", ["chocolate bar"], r"chocolate bar|kitkat|kit kat|\baero\b|coffee crisp|mars bar|snickers|lindt|toblerone|cadbury", r"cereal|ice cream|cookie|milk drink|cake|frozen|protein|syrup|chips|granola|spread|mini.*bag", 270, 7, None),
 ("frozen-pizza", "Frozen pizza", "Frozen", "each", 1, "each", ["frozen pizza", "pizza"], r"pizza", r"pocket|sauce|dough|crust|cheese pull|pizza mozzarella|pepperoni slices|pan|stone|cutter|oven|bites|rolls|snack|kit|seasoning|bagel|delivery|fresh|pops?\b|pizzaiolo|flatbread|mini|shells?|sub\b|toaster|french bread", 180, 7, None),
 ("frozen-veg", "Frozen vegetables", "Frozen", "kg", .75, "per 750 g", ["frozen vegetables", "frozen peas"], r"frozen.*(veg|peas|corn|broccoli|mixed|beans)|(peas|corn|mixed vegetables).*frozen|green giant", r"meal|pizza|pie|dinner|rice bowl|soup|stir.?fry kit|ice cream|fries|potato", 270, 10, None),
 ("ice-cream", "Ice cream (tub)", "Frozen", "L", 1.5, "per 1.5 L", ["ice cream"], r"ice cream", r"cone|sandwich|bar|maker|scoop|cake|topping|sauce|bowl|cereal|cookie|frozen yogurt pop|popsicle|mochi|stick|bites", 120, 10, "ice cream"),
 ("toilet-paper", "Toilet paper", "Household", "roll", 24, "per 24 rolls", ["toilet paper", "bathroom tissue"], r"toilet paper|bathroom tissue|bath tissue|charmin|cottonelle|royale|cashmere|purex", r"wipe|flushable|holder|plunger|cleaner|paper towel|facial", 3650, 30, None),
 ("paper-towels", "Paper towels", "Household", "roll", 6, "per 6 rolls", ["paper towels"], r"paper towel|bounty|sponge towels|scott towel", r"holder|toilet|bath|napkin|dispenser", 3650, 30, None),
 ("detergent", "Laundry detergent", "Household", "L", 3, "per 3 L", ["laundry detergent"], r"laundry|detergent|tide|gain|persil|arm & hammer|arm and hammer", r"pod|pac|sheet|softener|dryer|booster|stain|dish|bag|basket|hamper|scent beads|unstopables", 730, 45, None),
 ("dish-soap", "Dish soap", "Household", "L", .75, "per 750 ml", ["dish soap"], r"dish soap|dish liquid|dawn|palmolive|sunlight", r"dishwasher|pod|tab|rack|brush|sponge|glove|cascade|finish|scrub", 730, 30, None),
 ("dog-food", "Dry dog food", "Pets", "kg", 10, "per 10 kg", ["dog food"], r"dog food|kibble|purina dog|pedigree|iams dog|blue buffalo dog", r"wet|can|treat|bowl|bed|toy|cat|leash|chew|stew|gravy|topper|pouch", 365, 30, None),
 ("cat-litter", "Cat litter", "Pets", "kg", 10, "per 10 kg", ["cat litter"], r"cat litter|litter", r"box|scoop|mat|liner|bag|deodori|bin|pan|robot", 3650, 20, None),
]

# When a flyer omits the size, these are the sizes flyers almost always mean.
# Rows priced this way carry assumed=True and are marked "~" on the site.
DEFAULT_SIZE = {"eggs-large": 12}

ITEMS = []
for row in _C:
    (i, label, cat, unit, show, show_label, terms, inc, exc, shelf, use, sc) = row
    ITEMS.append({"id": i, "label": label, "cat": cat, "unit": unit, "show": show, "show_label": show_label,
                  "terms": terms, "inc": re.compile(inc, re.I), "exc": re.compile(exc, re.I) if exc else None,
                  "shelf": shelf, "use": use, "statcan": sc, "default": DEFAULT_SIZE.get(i)})
BY_ID = {it["id"]: it for it in ITEMS}

# Typical Ontario price per display unit (late 2026, rounded). Only used as a sanity
# fence: a listing whose unit price lands outside 0.3x-3.5x of this is a parsing or
# matching error (wrong pack size, a garnish, a sauce), so it is dropped.
REF = {"eggs-large": 4.5, "milk-2": 6.5, "butter": 6.5, "cheddar": 6.5, "yogurt": 5, "cream-cheese": 4, "oat-milk": 4.5,
       "bananas": 1.8, "apples": 5, "avocados": 1.5, "potatoes": 2.5, "onions": 3, "carrots": 2.5, "tomatoes": 6,
       "broccoli": 3, "cucumber": 1.5, "lettuce": 3, "strawberries": 9, "chicken-breast": 17, "chicken-thigh": 12,
       "ground-beef": 12, "pork-chops": 11, "bacon": 7, "salmon": 25, "shrimp": 22, "tofu": 3.5, "bread": 3.5,
       "bagels": 4.5, "tortillas": 4.5, "rice": 20, "pasta": 2.5, "olive-oil": 14, "canola-oil": 9, "peanut-butter": 7,
       "flour": 7, "sugar": 4.5, "canned-tomatoes": 2.5, "cereal": 5, "oats": 5, "coffee": 16, "tea": 5,
       "orange-juice": 5, "cola": 8, "sparkling-water": 6, "chips": 4.5, "chocolate": 3, "frozen-pizza": 7,
       "frozen-veg": 4, "ice-cream": 6, "toilet-paper": 14, "paper-towels": 12, "detergent": 15, "dish-soap": 4,
       "dog-food": 45, "cat-litter": 15}
for _it in ITEMS:
    _it["ref"] = REF[_it["id"]] / _it["show"]

# Pet food, baby food and similar never count for people groceries.
NOT_HUMAN = re.compile(r"\b(dog|dogs|cat|cats|puppy|kitten|pet|purina|pedigree|whiskas|friskies|fancy feast|baby food|infant|toddler)\b", re.I)


def plausible(item, unit_price):
    return unit_price is not None and 0.3 * item["ref"] <= unit_price <= 3.5 * item["ref"]


# Private labels: price-match policies generally exclude competitors' house brands.
PRIVATE_LABELS = re.compile(r"\b(no name|president'?s choice|\bpc\b|pc®|great value|equate|compliments|selection|irresistibles|life smart|our finest|longo'?s|farm boy|kirkland|sensations|western family|our compliments|smartly|t&t|foodland|freshco|giant tiger|rooster)\b", re.I)


# Head noun: the product's last meaningful word must be the grocery itself, so
# "Coffee Whitener", "Banana Chili Sauce" and "Bacon Pizza Pops" are rejected.
HEAD = {
 "eggs-large": r"eggs?", "milk-2": r"milk", "butter": r"butter", "cheddar": r"cheddar|cheese", "yogurt": r"yog(h)?urt|dahi",
 "cream-cheese": r"cheese", "oat-milk": r"milk|beverage|drink|alternative", "bananas": r"bananas?", "apples": r"apples?",
 "avocados": r"avocados?", "potatoes": r"potato(es)?", "onions": r"onions?", "carrots": r"carrots?",
 "tomatoes": r"tomato(es)?", "broccoli": r"broccoli|crowns?", "cucumber": r"cucumbers?", "lettuce": r"lettuce|romaine|hearts?",
 "strawberries": r"strawberr(y|ies)", "chicken-breast": r"breasts?", "chicken-thigh": r"thighs?", "ground-beef": r"beef",
 "pork-chops": r"chops?", "bacon": r"bacon", "salmon": r"salmon|fillets?|portions?|steaks?", "shrimp": r"shrimps?|prawns?",
 "tofu": r"tofu", "bread": r"bread|loaf", "bagels": r"bagels?", "tortillas": r"tortillas?|wraps?",
 "rice": r"rice", "pasta": r"spaghetti|spaghettini|penne|fusilli|rotini|linguine|macaroni|pasta|fettuccine|elbows?|rigatoni|farfalle|fettucine",
 "olive-oil": r"oil", "canola-oil": r"oil|canola", "peanut-butter": r"butter", "flour": r"flour", "sugar": r"sugar",
 "canned-tomatoes": r"tomato(es)?|passata", "cereal": r"cereal|flakes|cheerios|shreddies|wheats?|bran|loops|krispies|chex|o's",
 "oats": r"oats|oatmeal", "coffee": r"coffee|roast|beans?|espresso|blend", "tea": r"tea|bags?|pekoe",
 "orange-juice": r"juice", "cola": r"cola|coca-cola|coke|pepsi|drinks?|cans?|bottles?|soda|pop", "sparkling-water": r"water|bubly|perrier|pellegrino",
 "chips": r"chips", "chocolate": r"bars?|chocolate|kit ?kat|aero|crisp|snickers|toblerone|mars", "frozen-pizza": r"pizzas?",
 "frozen-veg": r"vegetables?|veggies|peas|corn|beans|broccoli|florets|mix|medley", "ice-cream": r"cream|ice ?cream",
 "toilet-paper": r"paper|tissue|rolls?", "paper-towels": r"towels?|rolls?", "detergent": r"detergent|wash|liquid",
 "dish-soap": r"soap|liquid|detergent", "dog-food": r"food|kibble", "cat-litter": r"litter",
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
RELAXED = {"eggs-large", "yogurt", "ice-cream", "bagels", "tortillas", "bread", "detergent", "dish-soap", "coffee", "tea",
           "chips", "chocolate", "cereal", "oat-milk", "cheddar", "cream-cheese", "sparkling-water", "cola", "frozen-pizza",
           "olive-oil", "orange-juice", "peanut-butter", "frozen-veg", "salmon", "apples", "bacon", "milk-2", "flour",
           "pork-chops", "shrimp", "tofu", "sugar", "pasta", "chicken-thigh", "cat-litter", "dog-food", "paper-towels",
           "canned-tomatoes", "ground-beef", "lettuce", "tomatoes", "chicken-breast"}
_BADNOUN = re.compile(r"^(whip|sauce|pie|pies|bars?|cookies?|snacks?|crackers?|danish|pops|strips|spice|spices|crisps|treat|treats|cake|cakes|"
                      r"muffins?|twists|tarts?|shoots|salad|base|squeeze|whitener|creamer|cereal|drinks?|candy|candies|gummies|gummy|"
                      r"chips|sticks|bites|rolls|cheese|crust|dough|seasoning|mix|filling|frosting|icing|spread|dip|soup|noodles?|"
                      r"dumplings?|pastry|pastries|biscuits?|wafers?|sandwich|sandwiches|bun|buns|pudding|syrup|jam|jelly|powder|"
                      r"pods?|capsules?|k-cups?|beer|lager|ale|cocktail|liqueur|mints|lotion|candle|freshener|bowl|meal|kit|pizza|pizzas|hash|"
                      r"potstickers?|gyoza|turnovers?|croissants?|strudel|waffles?|chunks|nuggets?|perogies|pierogi|strip|yeast|olives|crackers|patties|dressing|sardines?|mackerel)$", re.I)


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
