select
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    o.purchased_at::date    as purchase_date,
    o.order_status,
    p.category,
    i.price,
    i.freight_value,
    i.price + i.freight_value as item_total
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o using (order_id)
left join {{ ref('stg_products') }} p using (product_id)
