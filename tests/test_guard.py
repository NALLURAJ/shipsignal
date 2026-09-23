import pytest

from assistant.guard import MAX_ROWS, UnsafeQuery, check_sql

ALLOWED = [
    "select count(*) from marts.fct_orders",
    "SELECT avg(review_score) FROM fct_orders WHERE is_late;",
    "select category, sum(price) as revenue from marts.fct_order_items group by category order by revenue desc",
    "with s as (select customer_state, count(*) as n from marts.fct_orders group by 1) select * from s",
    "select d.year, count(*) from marts.fct_orders o join marts.dim_date d on d.date_day = o.purchase_date group by 1",
    "```sql\nselect count(*) from marts.dim_customer\n```",
]

BLOCKED = [
    "drop table marts.fct_orders",
    "DROP TABLE marts.fct_orders; --",
    "select 1; drop table marts.fct_orders",
    "delete from marts.fct_orders",
    "update marts.fct_orders set review_score = 5",
    "insert into marts.dim_date select * from marts.dim_date",
    "truncate marts.fct_orders",
    "alter table marts.fct_orders add column x int",
    "create table marts.x as select 1",
    "with d as (delete from marts.fct_orders returning *) select * from d",
    "select * into marts.copy from marts.fct_orders",
    "copy marts.fct_orders to '/tmp/out.csv'",
    "grant all on marts.fct_orders to public",
    "set statement_timeout = 0",
    "select * from raw.orders",
    "select * from pg_catalog.pg_user",
    "select * from information_schema.tables",
    "select pg_sleep(30)",
    "select pg_read_file('/etc/passwd')",
    "select current_setting('data_directory')",
    "select * from generate_series(1, 1000000000)",
    "select made_up_column from marts.fct_orders",
    "",
    "this is not sql",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_queries_pass(sql):
    checked = check_sql(sql)
    assert checked.sql.lower().startswith("select * from (")
    assert checked.sql.endswith(f"limit {MAX_ROWS}")


@pytest.mark.parametrize("sql", BLOCKED)
def test_unsafe_queries_are_blocked(sql):
    with pytest.raises(UnsafeQuery):
        check_sql(sql)


def test_row_limit_is_always_applied():
    checked = check_sql("select order_id from marts.fct_orders limit 100000", max_rows=10)
    assert checked.sql.endswith("limit 10")


def test_tables_are_reported():
    checked = check_sql("select * from marts.fct_orders o join marts.dim_customer c using (customer_unique_id)")
    assert checked.tables == {"marts.fct_orders", "marts.dim_customer"}
