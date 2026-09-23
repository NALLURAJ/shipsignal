select
    r.review_id,
    r.order_id,
    r.review_score,
    r.comment_title,
    r.comment_message,
    r.comment_message is not null  as has_comment,
    r.created_at,
    r.answered_at,
    -- a handful of orders have more than one review; keep a flag for the latest
    row_number() over (
        partition by r.order_id
        order by r.created_at desc, r.answered_at desc, r.review_id desc
    ) = 1 as is_latest_for_order
from {{ ref('stg_order_reviews') }} r
