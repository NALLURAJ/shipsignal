"""Load the Olist csv files into a `raw` schema in postgres.

Every column lands as text. Casting happens in the dbt staging models so that
a bad value shows up as a failed test instead of a crashed load.

    python -m ingest.load_raw --data-dir data/raw
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

import psycopg

log = logging.getLogger("ingest")

# file name on kaggle -> table name in the raw schema
FILES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}


def database_url() -> str:
    return os.environ.get(
        "DATABASE_URL", "postgresql://shipsignal:shipsignal@localhost:5432/shipsignal"
    )


def read_header(path: Path) -> list[str]:
    # the translation file ships with a BOM, utf-8-sig strips it
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [c.strip() for c in next(csv.reader(f))]


def load_file(conn: psycopg.Connection, path: Path, table: str) -> int:
    cols = read_header(path)
    col_sql = ", ".join(f'"{c}" text' for c in cols)

    with conn.cursor() as cur:
        cur.execute(f"drop table if exists raw.{table} cascade")
        cur.execute(f"create table raw.{table} ({col_sql})")

        with path.open(encoding="utf-8-sig", newline="") as f:
            next(f)  # header
            copy_sql = f"copy raw.{table} from stdin with (format csv)"
            with cur.copy(copy_sql) as copy:
                while chunk := f.read(1 << 20):
                    copy.write(chunk)

        cur.execute(f"select count(*) from raw.{table}")
        return cur.fetchone()[0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw", type=Path)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    missing = [name for name in FILES if not (args.data_dir / name).exists()]
    if missing:
        log.error("missing files in %s: %s", args.data_dir, ", ".join(missing))
        log.error("download the dataset from kaggle first (see README)")
        return 1

    with psycopg.connect(database_url()) as conn:
        conn.execute("create schema if not exists raw")
        for name, table in FILES.items():
            n = load_file(conn, args.data_dir / name, table)
            log.info("raw.%-22s %8d rows", table, n)
        conn.commit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
