"""Write a small *synthetic* dataset with the same files and columns as Olist.

This is only for CI and the test suite, so the pipeline can run without the
real download. None of the numbers in the README come from this data.

    python scripts/make_sample_data.py --out data/sample --orders 3000
"""

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

CATEGORIES = [
    ("beleza_saude", "health_beauty"),
    ("cama_mesa_banho", "bed_bath_table"),
    ("esporte_lazer", "sports_leisure"),
    ("informatica_acessorios", "computers_accessories"),
    ("moveis_decoracao", "furniture_decor"),
    ("utilidades_domesticas", "housewares"),
    ("relogios_presentes", "watches_gifts"),
    ("telefonia", "telephony"),
]
STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF"]
CITIES = {"SP": "sao paulo", "RJ": "rio de janeiro", "MG": "belo horizonte", "RS": "porto alegre",
          "PR": "curitiba", "SC": "florianopolis", "BA": "salvador", "DF": "brasilia"}
PAYMENT_TYPES = ["credit_card", "credit_card", "credit_card", "boleto", "voucher", "debit_card"]

TS = "%Y-%m-%d %H:%M:%S"


def hexid(rng: random.Random) -> str:
    return f"{rng.getrandbits(128):032x}"


def write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sample", type=Path)
    ap.add_argument("--orders", default=3000, type=int)
    ap.add_argument("--seed", default=7, type=int)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    sellers = [[hexid(rng), f"{rng.randint(10000, 99999)}", CITIES[s], s]
               for s in (rng.choice(STATES) for _ in range(60))]
    products = []
    for _ in range(400):
        cat_pt, _ = rng.choice(CATEGORIES)
        products.append([hexid(rng), cat_pt, rng.randint(20, 60), rng.randint(100, 2000),
                         rng.randint(1, 6), rng.randint(100, 5000), rng.randint(10, 60),
                         rng.randint(5, 40), rng.randint(10, 50)])
    base_price = {p[0]: round(rng.lognormvariate(4.2, 0.7), 2) for p in products}

    people = [(hexid(rng), rng.choice(STATES)) for _ in range(int(args.orders * 0.9))]

    customers, orders, items, payments, reviews = [], [], [], [], []
    start = datetime(2016, 10, 1)
    span_days = (datetime(2018, 8, 31) - start).days
    last_order_late: dict[str, bool] = {}

    for _ in range(args.orders):
        # a person with a late first order is less likely to come back
        if last_order_late and rng.random() < 0.06:
            uid = rng.choice(list(last_order_late))
            if last_order_late[uid] and rng.random() < 0.5:
                uid, state = rng.choice(people)
            else:
                state = next(s for u, s in people if u == uid)
        else:
            uid, state = rng.choice(people)

        # volume grows over time, with a bump in november
        while True:
            d = rng.randint(0, span_days)
            purchased = start + timedelta(days=d, seconds=rng.randint(0, 86399))
            weight = 0.3 + d / span_days + (0.4 if purchased.month == 11 else 0)
            if rng.random() < weight / 1.7:
                break

        order_id = hexid(rng)
        customer_id = hexid(rng)
        customers.append([customer_id, uid, f"{rng.randint(10000, 99999)}", CITIES[state], state])

        status = rng.choices(["delivered", "shipped", "canceled", "invoiced"], [94, 3, 2, 1])[0]
        estimated = purchased + timedelta(days=rng.randint(15, 35))
        delivered = None
        if status == "delivered":
            delivered = purchased + timedelta(days=max(1, int(rng.gauss(12, 7))), hours=rng.randint(0, 23))
            if rng.random() < 0.02:
                delivered = None  # the real data has a few of these too
        late = bool(delivered and delivered.date() > estimated.date())
        last_order_late.setdefault(uid, late)

        n_items = rng.choices([1, 2, 3], [88, 9, 3])[0]
        total = 0.0
        for i in range(1, n_items + 1):
            prod = rng.choice(products)
            seller = rng.choice(sellers)
            price = base_price[prod[0]]
            freight = round(rng.uniform(7, 40), 2)
            total += price + freight
            items.append([order_id, i, prod[0], seller[0],
                          (purchased + timedelta(days=5)).strftime(TS), f"{price:.2f}", f"{freight:.2f}"])

        pay_total = round(total, 2)
        if rng.random() < 0.03:
            pay_total = round(total * rng.uniform(0.5, 0.95), 2)
        payments.append([order_id, 1, rng.choice(PAYMENT_TYPES), rng.randint(1, 10), f"{pay_total:.2f}"])

        delay = (delivered.date() - estimated.date()).days if delivered else 0
        score = 4.4 - 0.12 * max(delay, 0) + rng.gauss(0, 1.0)
        score = int(min(5, max(1, round(score))))
        review_created = (delivered or estimated) + timedelta(days=1)
        comment = rng.choice(["", "", "otimo produto", "chegou atrasado", "recomendo", "nao recebi"])
        reviews.append([hexid(rng), order_id, score, "", comment,
                        review_created.strftime(TS), (review_created + timedelta(days=2)).strftime(TS)])

        orders.append([order_id, customer_id, status, purchased.strftime(TS),
                       (purchased + timedelta(hours=2)).strftime(TS),
                       (purchased + timedelta(days=2)).strftime(TS) if status != "canceled" else "",
                       delivered.strftime(TS) if delivered else "",
                       estimated.strftime("%Y-%m-%d 00:00:00")])

    write(args.out / "olist_customers_dataset.csv",
          ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
          customers)
    write(args.out / "olist_geolocation_dataset.csv",
          ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"],
          [["01037", "-23.54", "-46.63", "sao paulo", "SP"]])
    write(args.out / "olist_order_items_dataset.csv",
          ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
          items)
    write(args.out / "olist_order_payments_dataset.csv",
          ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
          payments)
    write(args.out / "olist_order_reviews_dataset.csv",
          ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
           "review_creation_date", "review_answer_timestamp"],
          reviews)
    write(args.out / "olist_orders_dataset.csv",
          ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
           "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
          orders)
    write(args.out / "olist_products_dataset.csv",
          ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
           "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
          products)
    write(args.out / "olist_sellers_dataset.csv",
          ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"], sellers)
    write(args.out / "product_category_name_translation.csv",
          ["product_category_name", "product_category_name_english"], [list(c) for c in CATEGORIES])

    print(f"wrote {len(orders)} orders, {len(items)} items to {args.out}")


if __name__ == "__main__":
    main()
