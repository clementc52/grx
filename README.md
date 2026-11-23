# GRX: Grocery Exchange

Real grocery prices for every store within a radius of you, watched around the clock, with a
**Buy / Wait / Stock up** call for each grocery.

- **Live flyer + online prices** from Flipp's public search, swept across the postal areas in your radius (hourly near home, full radius every 6 hours).
- **Daily shelf-price history** since Feb 2024 for Loblaws, No Frills, Metro, Walmart, Voila, T&T, Galleria, Save-On-Foods from [Project Hammer](https://jacobfilipp.com/hammer/).
- **Official averages** from Statistics Canada table 18-10-0245-01.

## What it tells you
| Feature | How |
|---|---|
| Buy / Wait / Stock up | Kaplan–Meier survival model of each chain's gaps between sales, shrunk toward the aisle when history is thin |
| Sale odds 7 / 14 / 28 days | P(sale starts within h days given s days since the last one) |
| Stock-up quantity | Covers the expected gap to the next sale, capped by shelf life and your usage |
| Deal check | Flyer price vs that chain's own 90-day median and low ("Not really a sale" flags fake promos) |
| Shrinkflation | Package size drops while shelf price holds (from price-per-unit) |
| Lockstep radar | Two chains' regular-price hikes within 3 days, vs chance |
| Price-match plan | Competitor flyer prices No Frills / Superstore / Giant Tiger will match (house brands excluded) |
| Alerts | Rules in `config.json` open a GitHub issue, so GitHub notifies you |

Prices are compared per kg, L, egg or roll, so pack sizes can't hide the real price.

## Run
```
python tests/test_all.py
python -m grx.run flipp --full   # live prices across the radius
python -m grx.run hammer         # shelf-price history (~large download)
python -m grx.run statcan
python -m grx.run build          # writes site/data/board.json
python -m grx.run alerts
```
Stdlib-only Python 3.10+. GitHub Actions (`.github/workflows/collect.yml`) runs it on a schedule and
publishes `site/` to GitHub Pages. Edit `config.json` for home area, radius, price-match stores and alerts.
Add postal areas for other regions in `grx/geo.py` and groceries in `grx/catalog.py`.

Not affiliated with Flipp or any retailer. Flyer prices can vary by store and may need a loyalty card.
