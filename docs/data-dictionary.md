# Data dictionary

Schemas in postgres:

| Schema | What's in it |
|---|---|
| `raw` | the nine Olist csv files, all columns as text |
| `staging` | one view per raw table: typed, renamed, deduplicated |
| `marts` | the star schema below, which the api, the notebooks, the dashboard and the assistant use |

## marts

**fct_orders** — one row per order
`order_id`, `customer_id`, `customer_unique_id`, `customer_state`, `order_status`, `purchased_at`, `purchase_date`, `delivered_at`, `estimated_delivery_at`, `items_count`, `sellers_count`, `items_value` (revenue, no freight), `freight_value`, `order_total`, `payment_total`, `is_delivered`, `delivery_days`, `delay_days` (+ late / − early), `is_late`, `customer_order_number`, `is_first_order`, `review_score` (latest review)

**fct_order_items** — one row per item
`order_id`, `order_item_id`, `product_id`, `seller_id`, `purchase_date`, `order_status`, `category`, `price`, `freight_value`, `item_total`

**fct_reviews** — one row per (review, order)
`review_id`, `order_id`, `review_score`, `comment_title`, `comment_message`, `has_comment`, `created_at`, `answered_at`, `is_latest_for_order`

**dim_customer** — one row per `customer_unique_id`
`city`, `state` (from the first order), `first_order_at`, `last_order_at`, `lifetime_orders`

**dim_product** — one row per product
`category` (english), `category_pt`, `photos_qty`, `weight_g`, `volume_cm3`

**dim_seller** — one row per seller
`city`, `state`, `zip_prefix`, `first_sale_at`, `lifetime_orders`

**dim_date** — one row per calendar day covering every year with orders
`date_day`, `year`, `quarter`, `month`, `month_name`, `month_start`, `week_start`, `day_of_week` (1 = Monday), `is_weekend`

Metric definitions are in [definitions.md](definitions.md).
