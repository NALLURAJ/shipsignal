"""The only tables and columns the assistant is allowed to query.

Used twice: to describe the warehouse in the prompt, and as the allow-list
that the SQL guard checks against.
"""

TABLES: dict[str, dict[str, str]] = {
    "marts.fct_orders": {
        "order_id": "order key",
        "customer_unique_id": "the real customer (use this to count customers)",
        "customer_state": "two-letter Brazilian state of the customer, e.g. SP, RJ",
        "order_status": "delivered, shipped, canceled, unavailable, invoiced, processing, created, approved",
        "purchased_at": "timestamp of purchase",
        "purchase_date": "date of purchase",
        "delivered_at": "timestamp the customer received it, null if not delivered",
        "estimated_delivery_at": "delivery date promised to the customer",
        "items_count": "number of items in the order",
        "sellers_count": "number of distinct sellers in the order",
        "items_value": "sum of item prices, excludes freight (this is revenue)",
        "freight_value": "sum of freight charged",
        "order_total": "items_value + freight_value",
        "payment_total": "what the customer paid across all payment methods",
        "is_delivered": "true if status is delivered and there is a delivery date",
        "delivery_days": "days from purchase to delivery",
        "delay_days": "delivered date minus estimated date; positive means late",
        "is_late": "true if delivered after the estimated date, null if not delivered",
        "customer_order_number": "1 for the customer's first order, 2 for the second, ...",
        "is_first_order": "true for the customer's first order",
        "review_score": "1-5 stars from the latest review of the order, null if none",
    },
    "marts.fct_order_items": {
        "order_id": "order key",
        "order_item_id": "position of the item within the order (1, 2, ...)",
        "product_id": "product key",
        "seller_id": "seller key",
        "purchase_date": "date of purchase",
        "order_status": "status of the parent order",
        "category": "english product category, e.g. health_beauty",
        "price": "item price",
        "freight_value": "freight for this item",
        "item_total": "price + freight_value",
    },
    "marts.fct_reviews": {
        "review_id": "review key",
        "order_id": "order key",
        "review_score": "1-5 stars",
        "comment_title": "optional title (Portuguese)",
        "comment_message": "optional text (Portuguese)",
        "has_comment": "true if the customer wrote a message",
        "created_at": "when the review was created",
        "is_latest_for_order": "true for the latest review of each order",
    },
    "marts.dim_customer": {
        "customer_unique_id": "customer key",
        "city": "city of the first order",
        "state": "state of the first order",
        "first_order_at": "timestamp of first order",
        "last_order_at": "timestamp of latest order",
        "lifetime_orders": "number of orders",
    },
    "marts.dim_product": {
        "product_id": "product key",
        "category": "english category",
        "category_pt": "original Portuguese category",
        "photos_qty": "number of photos on the listing",
        "weight_g": "weight in grams",
        "volume_cm3": "length x height x width",
    },
    "marts.dim_seller": {
        "seller_id": "seller key",
        "city": "seller city",
        "state": "seller state",
        "first_sale_at": "timestamp of first sale",
        "lifetime_orders": "number of distinct orders",
    },
    "marts.dim_date": {
        "date_day": "calendar date",
        "year": "year",
        "quarter": "quarter 1-4",
        "month": "month 1-12",
        "month_name": "Jan, Feb, ...",
        "month_start": "first day of the month",
        "week_start": "monday of the week",
        "day_of_week": "1 = monday ... 7 = sunday",
        "is_weekend": "saturday or sunday",
    },
}


def allowed_tables() -> set[str]:
    names = set()
    for full in TABLES:
        names.add(full)
        names.add(full.split(".", 1)[1])
    return names


def allowed_columns() -> set[str]:
    return {col for cols in TABLES.values() for col in cols}


def describe(with_descriptions: bool = True) -> str:
    lines = []
    for table, cols in TABLES.items():
        lines.append(f"table {table}")
        for name, desc in cols.items():
            lines.append(f"  - {name}: {desc}" if with_descriptions else f"  - {name}")
    return "\n".join(lines)
