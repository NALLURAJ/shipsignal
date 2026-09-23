-- customer_id is per order in olist; customer_unique_id is the actual person
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix    as zip_prefix,
    initcap(customer_city)      as city,
    upper(customer_state)       as state
from {{ source('raw', 'customers') }}
