with items as (
    select
        order_id,
        count(*)            as items_count,
        count(distinct seller_id) as sellers_count,
        sum(price)          as items_value,
        sum(freight_value)  as freight_value
    from {{ ref('stg_order_items') }}
    group by order_id
),

payments as (
    select order_id, sum(payment_value) as payment_total
    from {{ ref('stg_order_payments') }}
    group by order_id
),

reviews as (
    select order_id, review_score
    from {{ ref('fct_reviews') }}
    where is_latest_for_order
),

orders as (
    select
        o.*,
        c.customer_unique_id,
        c.state as customer_state,
        row_number() over (
            partition by c.customer_unique_id
            order by o.purchased_at, o.order_id
        ) as customer_order_number
    from {{ ref('stg_orders') }} o
    join {{ ref('stg_customers') }} c using (customer_id)
)

select
    o.order_id,
    o.customer_id,
    o.customer_unique_id,
    o.customer_state,
    o.order_status,
    o.purchased_at,
    o.purchased_at::date                                  as purchase_date,
    o.delivered_at,
    o.estimated_delivery_at,
    coalesce(i.items_count, 0)                            as items_count,
    coalesce(i.sellers_count, 0)                          as sellers_count,
    coalesce(i.items_value, 0)                            as items_value,
    coalesce(i.freight_value, 0)                          as freight_value,
    coalesce(i.items_value, 0) + coalesce(i.freight_value, 0) as order_total,
    p.payment_total,
    o.order_status = 'delivered' and o.delivered_at is not null as is_delivered,
    case
        when o.delivered_at is null then null
        else o.delivered_at::date - o.purchased_at::date
    end                                                   as delivery_days,
    case
        when o.delivered_at is null then null
        else o.delivered_at::date - o.estimated_delivery_at::date
    end                                                   as delay_days,
    case
        when o.delivered_at is null then null
        else o.delivered_at::date > o.estimated_delivery_at::date + {{ var('late_grace_days') }}
    end                                                   as is_late,
    o.customer_order_number,
    o.customer_order_number = 1                           as is_first_order,
    r.review_score
from orders o
left join items i using (order_id)
left join payments p using (order_id)
left join reviews r using (order_id)
