with items as (
    select
        i.seller_id,
        min(o.purchased_at)         as first_sale_at,
        count(distinct i.order_id)  as orders
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_orders') }} o on o.order_id = i.order_id
    group by i.seller_id
)

select
    s.seller_id,
    s.city,
    s.state,
    s.zip_prefix,
    i.first_sale_at,
    coalesce(i.orders, 0) as lifetime_orders
from {{ ref('stg_sellers') }} s
left join items i on i.seller_id = s.seller_id
