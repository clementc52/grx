"""One name per grocery chain, so the store filter works across sources
(Flipp says "T&T Supermarket", Project Hammer says "TandT")."""
import re

_RULES = [
    (r"^no ?frills", "No Frills"), (r"t\s*&\s*t|tandt", "T&T"), (r"real canadian superstore|^superstore", "Real Canadian Superstore"),
    (r"^loblaws?", "Loblaws"), (r"wholesale club", "Wholesale Club"), (r"your independent|independent city|^independent", "Independent"),
    (r"valu-?mart", "Valu-mart"), (r"zehrs", "Zehrs"), (r"fortinos", "Fortinos"), (r"^metro", "Metro"), (r"food ?basics", "Food Basics"),
    (r"freshco", "FreshCo"), (r"^sobeys", "Sobeys"), (r"^voil[aà]", "Voilà (Sobeys online)"), (r"foodland", "Foodland"),
    (r"walmart", "Walmart"), (r"giant tiger", "Giant Tiger"), (r"longo", "Longo's"), (r"farm boy", "Farm Boy"),
    (r"galleria", "Galleria"), (r"h ?mart", "H Mart"), (r"save-?on", "Save-On-Foods"), (r"costco", "Costco"),
    (r"adonis", "Adonis"), (r"highland farms", "Highland Farms"), (r"whole foods", "Whole Foods"), (r"rabba", "Rabba"),
    (r"shoppers drug", "Shoppers Drug Mart"), (r"rexall", "Rexall"), (r"healthy planet", "Healthy Planet"),
    (r"london drugs", "London Drugs"), (r"nature'?s emporium", "Nature's Emporium"), (r"centra", "Centra"),
]
_C = [(re.compile(p, re.I), n) for p, n in _RULES]


def chain(name):
    n = (name or "").strip()
    for rx, label in _C:
        if rx.search(n):
            return label
    return n
