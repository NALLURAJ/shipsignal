with products as (
    select * from {{ source('raw', 'products') }}
),

translation as (
    select * from {{ source('raw', 'category_translation') }}
)

select
    p.product_id,
    p.product_category_name                     as category_pt,
    -- two categories have no english name in the translation file
    coalesce(
        t.product_category_name_english,
        p.product_category_name,
        'unknown'
    )                                           as category,
    p.product_photos_qty::int                   as photos_qty,
    p.product_weight_g::numeric                 as weight_g,
    p.product_length_cm::numeric                as length_cm,
    p.product_height_cm::numeric                as height_cm,
    p.product_width_cm::numeric                 as width_cm
from products p
left join translation t
    on p.product_category_name = t.product_category_name
