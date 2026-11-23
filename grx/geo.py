"""Forward sortation areas (first 3 postal characters) used to sweep a radius.

Flipp returns the flyers that serve a given FSA, so covering a radius means
querying a spread of FSAs inside it. Coordinates are approximate centroids.
Add rows for other regions; the collector picks those within the radius.
"""
import math

FSAS = {
    # Toronto
    "M5S": (43.663, -79.396, "Downtown / U of T"), "M4Y": (43.666, -79.385, "Church-Wellesley"),
    "M5V": (43.643, -79.398, "King West"), "M6P": (43.661, -79.464, "Junction"),
    "M4C": (43.689, -79.307, "East York"), "M2N": (43.770, -79.413, "North York Centre"),
    "M1P": (43.757, -79.270, "Scarborough Centre"), "M9W": (43.706, -79.594, "Etobicoke North"),
    "M3J": (43.766, -79.487, "York University"), "M8V": (43.606, -79.501, "Mimico"),
    # GTA and beyond
    "L5B": (43.585, -79.640, "Mississauga City Centre"), "L6Y": (43.672, -79.743, "Brampton"),
    "L3R": (43.857, -79.335, "Markham"), "L4C": (43.871, -79.437, "Richmond Hill"),
    "L4J": (43.807, -79.452, "Thornhill / Vaughan"), "L1V": (43.835, -79.090, "Pickering"),
    "L1H": (43.897, -78.865, "Oshawa"), "L6H": (43.474, -79.694, "Oakville"),
    "L7L": (43.355, -79.787, "Burlington"), "L9T": (43.517, -79.882, "Milton"),
    "L8P": (43.256, -79.871, "Hamilton"), "L3Y": (44.052, -79.461, "Newmarket"),
    "L4M": (44.390, -79.690, "Barrie"), "N1H": (43.543, -80.248, "Guelph"),
    "N2G": (43.449, -80.489, "Kitchener"), "N2L": (43.472, -80.540, "Waterloo"),
    "L2R": (43.159, -79.246, "St. Catharines"), "L2E": (43.100, -79.080, "Niagara Falls"),
    "K9J": (44.300, -78.320, "Peterborough"), "L9W": (43.920, -80.100, "Orangeville"),
}


def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def sweep(home_fsa, radius_km, max_fsas=12):
    """FSAs within the radius, nearest first, thinned so they spread out."""
    home = FSAS[home_fsa][:2]
    cands = sorted(((km(home, v[:2]), f) for f, v in FSAS.items() if km(home, v[:2]) <= radius_km))
    picked = []
    for d, f in cands:
        if all(km(FSAS[f][:2], FSAS[p][:2]) > min(6, radius_km / 4) for p, _ in picked) or not picked:
            picked.append((f, round(d, 1)))
        if len(picked) >= max_fsas:
            break
    return picked
