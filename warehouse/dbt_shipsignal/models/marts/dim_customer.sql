-- one row per real customer (customer_unique_id). location is taken from
-- their first order, which is what the repeat-purchase analysis groups on.
with orders as (
    select
        c.customer_unique_id,
        c.city,
        c.state,
        o.order_id,
        o.purchased_at,
        row_number() over (
            partition by c.customer_unique_id
            order by o.purchased_at, o.order_id
        ) as rn
    from {{ ref('stg_orders') }} o
    join {{ ref('stg_customers') }} c using (customer_id)
)

select
    customer_unique_id,
    max(case when rn = 1 then city end)     as city,
    max(case when rn = 1 then state end)    as state,
    min(purchased_at)                       as first_order_at,
    max(purchased_at)                       as last_order_at,
    count(*)                                as lifetime_orders
from orders
group by customer_unique_id
