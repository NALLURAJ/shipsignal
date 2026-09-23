-- nothing can arrive before it was bought
select order_id, purchased_at, delivered_at
from {{ ref('stg_orders') }}
where delivered_at < purchased_at
