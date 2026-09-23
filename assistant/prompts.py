"""Prompt versions compared in the evaluation (see eval/README.md)."""

from assistant.schema import describe

PROTOCOL = """
Reply with a single JSON object and nothing else. Pick one of:
  {"tool": "run_sql", "sql": "<one postgres SELECT>"}
  {"tool": "lookup_definition", "term": "<metric or word to look up>"}
  {"tool": "make_chart", "x": "<column>", "y": "<column>", "kind": "bar" | "line"}
  {"answer": "<final answer for the user>"}
After each tool call you will get the result and can call another tool or answer.
""".strip()

RULES = """
Rules:
- Any number in your answer must come from a run_sql result. Never guess numbers.
- Only SELECT queries. Only the tables listed. Prefix tables with the marts schema.
- Count customers with customer_unique_id, never customer_id.
- Revenue means sum of price (or items_value), freight excluded, and excludes orders
  with order_status 'canceled' or 'unavailable'.
- On-time rate only uses delivered orders (is_delivered = true).
- Round money to 2 decimals and rates to 4 decimals in the SQL.
- If the question cannot be answered from these tables, say so in the answer.
- Keep the final answer to one or two sentences and include the number.
""".strip()

EXAMPLES = """
Examples:
Q: How many orders were delivered in 2017?
{"tool": "run_sql", "sql": "select count(*) as delivered_orders from marts.fct_orders where is_delivered and extract(year from purchase_date) = 2017"}
Q: Which state has the most customers?
{"tool": "run_sql", "sql": "select state, count(*) as customers from marts.dim_customer group by state order by customers desc limit 1"}
Q: What was revenue in March 2018?
{"tool": "run_sql", "sql": "select round(sum(items_value), 2) as revenue from marts.fct_orders where order_status not in ('canceled','unavailable') and purchase_date >= '2018-03-01' and purchase_date < '2018-04-01'"}
Q: What does on-time mean?
{"tool": "lookup_definition", "term": "on-time delivery"}
""".strip()


def system_prompt(version: str) -> str:
    if version == "v1":
        # bare: table and column names only
        return (
            "You answer questions about an e-commerce postgres database.\n\n"
            + describe(with_descriptions=False) + "\n\n" + PROTOCOL
        )
    if version == "v2":
        return (
            "You are a data analyst answering questions about the Olist e-commerce warehouse.\n\n"
            + describe() + "\n\n" + RULES + "\n\n" + PROTOCOL
        )
    if version == "v3":
        return (
            "You are a data analyst answering questions about the Olist e-commerce warehouse.\n\n"
            + describe() + "\n\n" + RULES + "\n\n" + EXAMPLES + "\n\n" + PROTOCOL
        )
    raise ValueError(f"unknown prompt version {version}")
