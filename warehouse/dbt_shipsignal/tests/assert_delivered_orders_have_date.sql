-- a delivered order needs a delivery date, otherwise it silently drops out of the on-time rate
{{ config(severity='warn') }}

select order_id
from {{ ref('stg_orders') }}
where order_status = 'delivered'
  and delivered_at is null
