-- review_id is not unique in the raw file (the same review is attached to
-- several orders) and some orders have several reviews, so the grain here is
-- (review_id, order_id). distinct is a guard against repeated rows.
with deduped as (
    select distinct
        review_id,
        order_id,
        review_score::int                   as review_score,
        nullif(trim(review_comment_title), '')    as comment_title,
        nullif(trim(review_comment_message), '')  as comment_message,
        review_creation_date::timestamp     as created_at,
        review_answer_timestamp::timestamp  as answered_at
    from {{ source('raw', 'order_reviews') }}
)

select * from deduped
