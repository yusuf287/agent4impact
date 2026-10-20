"""Synthetic food-equity dataset so the whole kit is rehearsable with ZERO external data.
Run:  python domains/food_equity/gen_data.py domains/food_equity/data
Deterministic (seeded). Synthetic data only — no real people or places."""
import csv
import math
import os
import random
import sys

random.seed(42)
out = sys.argv[1] if len(sys.argv) > 1 else "data"
os.makedirs(out, exist_ok=True)

N = 40
districts = ["North", "South", "East", "West", "Central"]
neighborhoods, outlets, survey = [], [], []
oid = 1

for i in range(1, N + 1):
    income = random.randint(24_000, 120_000)
    no_car = max(0.0, min(0.6, 0.45 - income / 300_000 + random.uniform(-0.05, 0.08)))
    seniors = random.uniform(0.06, 0.28)
    dist = max(0.2, 4.5 - income / 30_000 + random.uniform(-0.8, 1.2))
    pop = random.randint(3_000, 25_000)
    row = dict(neighborhood_id=i, name=f"Neighborhood {i:02d}", district=random.choice(districts),
               population=pop, median_income=income, pct_no_vehicle=round(no_car, 3),
               pct_seniors=round(seniors, 3), distance_to_grocery_km=round(dist, 2),
               lat=round(43.60 + random.uniform(0, 0.25), 5), lon=round(-79.60 + random.uniform(0, 0.35), 5))
    neighborhoods.append(row)

    n_out = max(0, int(random.gauss(income / 30_000, 1.2)))
    for _ in range(n_out):
        t = random.choices(["grocery", "pantry", "corner_store", "farmers_market"], [3, 2, 4, 1])[0]
        outlets.append(dict(outlet_id=oid, neighborhood_id=i, outlet_type=t,
                            accepts_ebt=int(t in ("grocery", "pantry") or random.random() < 0.3)))
        oid += 1

    for year in range(2019, 2025):
        score = (0.55 - income / 250_000) + no_car * 0.5 + dist * 0.025 + seniors * 0.2 \
            + (0.01 if year in (2020, 2021) else 0) + random.gauss(0, 0.025)
        rate = max(0.02, min(0.6, score))
        survey.append(dict(neighborhood_id=i, year=year, insecurity_rate=round(rate, 3),
                           high_need=int(rate >= 0.22)))


def dump(name, rows):
    with open(os.path.join(out, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


dump("neighborhoods", neighborhoods)
dump("food_outlets", outlets)
dump("food_insecurity_survey", survey)
