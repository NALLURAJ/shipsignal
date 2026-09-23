"""Export the mart tables to csv for Tableau Public.

Tableau Public can't connect to postgres, only to files, so the dashboard is
built on these extracts. Re-run after rebuilding the warehouse.
Booleans are written as 0/1 so Tableau can sum them.

    python -m bi.export_for_tableau
"""

from pathlib import Path

from common.db import query

OUT = Path(__file__).parent / "extracts"

TABLES = {
    "fct_orders": """
        select order_id, customer_unique_id, customer_state, order_status, purchase_date,
               delivered_at::date as delivered_date, estimated_delivery_at::date as estimated_date,
               items_count, sellers_count, items_value, freight_value, order_total,
               is_delivered::int as is_delivered, delivery_days, delay_days,
               is_late::int as is_late, is_first_order::int as is_first_order, review_score
        from marts.fct_orders
    """,
    "fct_order_items": """
        select order_id, order_item_id, product_id, seller_id, purchase_date, order_status,
               category, price, freight_value
        from marts.fct_order_items
    """,
    "dim_seller": "select seller_id, city, state, lifetime_orders from marts.dim_seller",
    "dim_date": "select date_day, year, quarter, month, month_name, month_start, week_start, is_weekend::int as is_weekend from marts.dim_date",
    "dim_customer": "select customer_unique_id, city, state, lifetime_orders from marts.dim_customer",
}


def main():
    OUT.mkdir(exist_ok=True)
    for name, sql in TABLES.items():
        df = query(sql)
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:16s} {len(df):>8,} rows")


if __name__ == "__main__":
    main()
