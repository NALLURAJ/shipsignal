"""The three tools the assistant can call."""

import datetime as dt
import decimal
from typing import Any

from sqlalchemy import text

from assistant.guard import CheckedQuery, UnsafeQuery, check_sql
from assistant.retrieval import DefinitionIndex
from common.db import engine

STATEMENT_TIMEOUT_MS = 5000


def _jsonable(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def run_sql(sql: str, timeout_ms: int = STATEMENT_TIMEOUT_MS) -> dict[str, Any]:
    """Check the query, then run it read-only with a timeout."""
    try:
        checked: CheckedQuery = check_sql(sql)
    except UnsafeQuery as exc:
        return {"ok": False, "error": f"rejected by guard: {exc}", "kind": "guard"}

    try:
        with engine().connect() as conn:
            with conn.begin():
                conn.execute(text("set transaction read only"))
                conn.execute(text(f"set local statement_timeout = {int(timeout_ms)}"))
                conn.execute(text("set local search_path = marts"))
                result = conn.execute(text(checked.sql))
                cols = list(result.keys())
                rows = [{c: _jsonable(v) for c, v in zip(cols, r)} for r in result.fetchall()]
    except Exception as exc:  # the model gets the error back and can retry
        msg = str(getattr(exc, "orig", exc)).split("\n")[0]
        return {"ok": False, "error": msg, "kind": "database"}

    return {"ok": True, "sql": checked.sql, "columns": cols, "rows": rows}


def lookup_definition(index: DefinitionIndex, term: str, k: int = 2) -> dict[str, Any]:
    hits = index.search(term, k=k)
    return {"ok": True, "results": [{"title": h.title, "text": h.text, "score": round(h.score, 3)} for h in hits]}


def make_chart(rows: list[dict], x: str, y: str, kind: str = "bar", title: str = "") -> dict[str, Any]:
    """Return a small chart spec; the front end draws it."""
    if not rows:
        return {"ok": False, "error": "no rows to chart"}
    if x not in rows[0] or y not in rows[0]:
        return {"ok": False, "error": f"columns must be two of {list(rows[0])}"}
    if kind not in {"bar", "line"}:
        kind = "bar"
    return {"ok": True, "chart": {"kind": kind, "x": x, "y": y, "title": title,
                                  "data": [{x: r[x], y: r[y]} for r in rows]}}
