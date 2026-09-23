with bounds as (
    select
        date_trunc('year', min(purchased_at))::date                           as first_day,
        (date_trunc('year', max(purchased_at)) + interval '1 year - 1 day')::date as last_day
    from {{ ref('stg_orders') }}
),

days as (
    select generate_series(first_day, last_day, interval '1 day')::date as date_day
    from bounds
)

select
    date_day,
    extract(year from date_day)::int                 as year,
    extract(quarter from date_day)::int              as quarter,
    extract(month from date_day)::int                as month,
    to_char(date_day, 'Mon')                         as month_name,
    date_trunc('month', date_day)::date              as month_start,
    date_trunc('week', date_day)::date               as week_start,
    extract(isodow from date_day)::int               as day_of_week,
    extract(isodow from date_day) in (6, 7)          as is_weekend
from days
