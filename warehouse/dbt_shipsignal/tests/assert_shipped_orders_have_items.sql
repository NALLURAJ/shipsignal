-- orders that shipped or were delivered should have at least one item
{{ config(severity='warn') }}

select order_id, order_status
from {{ ref('fct_orders') }}
where order_status in ('shipped', 'delivered')
  and items_count = 0
