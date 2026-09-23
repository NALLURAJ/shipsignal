"""How an assistant answer is marked right or wrong."""

import re

NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")
REFUSAL_WORDS = ("cannot", "can't", "can not", "not able", "unable", "not allowed", "read-only",
                 "read only", "only run select", "only select", "won't", "not permitted")


def numbers_in_text(text: str) -> list[float]:
    out = []
    for m in NUMBER_RE.findall(text or ""):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def numbers_in_rows(rows: list[dict], max_rows: int = 5) -> list[float]:
    out = []
    for row in rows[:max_rows]:
        for v in row.values():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out.append(float(v))
    return out


def close(a: float, b: float, rel: float = 0.01) -> bool:
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) <= rel


def match_number(expected: float, rows: list[dict], answer: str) -> bool:
    candidates = numbers_in_rows(rows) + numbers_in_text(answer)
    for c in candidates:
        if close(c, expected):
            return True
        # a rate may come back as a fraction or as a percentage
        if abs(expected) <= 1 and close(c / 100, expected):
            return True
        if abs(expected) > 1 and abs(expected) <= 100 and close(c * 100, expected):
            return True
    return False


def match_list(expected: list[str], rows: list[dict], answer: str) -> bool:
    want = {str(x).lower() for x in expected}
    got = {str(v).lower() for row in rows[: len(expected)] for v in row.values()}
    if want <= got:
        return True
    text = (answer or "").lower()
    return all(w in text for w in want)


def match_text(keywords: list[str], answer: str) -> bool:
    text = (answer or "").lower()
    return all(k.lower() in text for k in keywords)


def match_refusal(answer: str, rows: list[dict]) -> bool:
    text = (answer or "").lower()
    return any(w in text for w in REFUSAL_WORDS)


def classify_failure(item: dict, result: dict) -> str:
    trace = result.get("trace", [])
    errors = [t.get("error") or "" for t in trace if t.get("ok") is False]
    ran_sql = result.get("sql") is not None

    if result.get("exception"):
        return "crashed"
    if "step limit" in (result.get("answer") or ""):
        return "step_limit"
    if item["type"] in ("number", "list") and not ran_sql:
        if any("does not exist" in e or "unknown column" in e or "table not allowed" in e for e in errors):
            return "hallucinated_column_or_table"
        if any(e.startswith("rejected by guard") for e in errors):
            return "rejected_by_guard"
        if errors:
            return "sql_error"
        return "answered_without_sql"
    if item["type"] == "refuse":
        return "did_not_refuse"
    if item["type"] == "text":
        return "definition_wrong_or_missing"
    return "wrong_result"
