"""Checks every query the model writes before it goes near the database.

Rules:
  * exactly one statement, and it has to be a SELECT (CTEs and UNION are fine)
  * no write / DDL nodes anywhere in the tree
  * only allow-listed tables, only allow-listed column names
  * no dangerous functions (pg_sleep, file access, dblink, set_config, ...)
  * a row limit is always applied

Execution then happens in a read-only transaction with a statement timeout,
so even if something slipped through here it could not write or hang.
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from assistant.schema import allowed_columns, allowed_tables

MAX_ROWS = 200

_WRITE_NODES = tuple(
    getattr(exp, name)
    for name in ("Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "AlterTable",
                 "TruncateTable", "Command", "Grant", "Copy", "Set", "Transaction", "Commit",
                 "Rollback", "Use", "LoadData", "Into")
    if hasattr(exp, name)
)

_BLOCKED_FUNCTIONS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file", "pg_read_binary_file",
    "pg_ls_dir", "pg_stat_file", "lo_import", "lo_export", "dblink", "dblink_exec",
    "set_config", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "current_setting", "query_to_xml", "copy",
}


class UnsafeQuery(ValueError):
    pass


@dataclass
class CheckedQuery:
    sql: str          # the query that will actually run (limit applied)
    tables: set[str]


def _strip(sql: str) -> str:
    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        if sql.lower().startswith("sql"):
            sql = sql[3:]
    return sql.strip().rstrip(";").strip()


def check_sql(sql: str, max_rows: int = MAX_ROWS) -> CheckedQuery:
    sql = _strip(sql)
    if not sql:
        raise UnsafeQuery("empty query")

    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise UnsafeQuery(f"could not parse sql: {exc}") from exc

    if len(statements) != 1:
        raise UnsafeQuery("only a single statement is allowed")
    tree = statements[0]

    set_op = getattr(exp, "SetOperation", exp.Union)
    if not isinstance(tree, (exp.Select, set_op)):
        raise UnsafeQuery(f"only SELECT is allowed, got {tree.key.upper()}")

    for node in tree.walk():
        if isinstance(node, _WRITE_NODES):
            raise UnsafeQuery(f"{node.key.upper()} is not allowed")

    # table allow-list (CTE names are fine, they are defined in the query)
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    ok_tables = {t.lower() for t in allowed_tables()}
    used = set()
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        full = f"{table.db.lower()}.{name}" if table.db else name
        if not name:
            raise UnsafeQuery("table functions are not allowed")
        if name in cte_names and not table.db:
            continue
        if full not in ok_tables:
            raise UnsafeQuery(f"table not allowed: {full}")
        used.add(full)

    # column allow-list: real columns, or aliases the query itself defines
    aliases = {a.alias.lower() for a in tree.find_all(exp.Alias)}
    aliases |= {
        col.name.lower()
        for cte in tree.find_all(exp.CTE)
        for col in (cte.args.get("alias").columns if cte.args.get("alias") else [])
    }
    ok_columns = {c.lower() for c in allowed_columns()} | aliases
    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if name and name != "*" and name not in ok_columns:
            raise UnsafeQuery(f"unknown column: {col.name}")

    for fn in tree.find_all(exp.Func):
        fname = (fn.name if isinstance(fn, exp.Anonymous) else fn.sql_name()).lower()
        if fname in _BLOCKED_FUNCTIONS:
            raise UnsafeQuery(f"function not allowed: {fname}")

    limited = f"select * from ({tree.sql(dialect='postgres')}) as q limit {int(max_rows)}"
    return CheckedQuery(sql=limited, tables=used)
