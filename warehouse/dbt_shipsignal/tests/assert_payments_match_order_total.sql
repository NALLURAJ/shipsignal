-- what the customer paid should equal items + freight.
-- vouchers and rounding make some orders miss, so this warns instead of failing.
{{ config(severity='warn') }}

select order_id, order_total, payment_total
from {{ ref('fct_orders') }}
where payment_total is not null
  and items_count > 0
  and abs(payment_total - order_total) > 1.00
