"""Score the assistant on the 40 questions in eval/questions.json.

    python -m eval.run_eval                         # all configs
    python -m eval.run_eval --configs v3+rag --limit 5

Each config is a prompt version, optionally with retrieval ("+rag").
Writes one csv per config and eval/results/summary.md.
"""

import argparse
import json
import time
import traceback
from pathlib import Path

import pandas as pd

from assistant.agent import Assistant
from assistant.llm import OllamaClient
from common.db import query
from eval.scoring import classify_failure, match_list, match_number, match_refusal, match_text

HERE = Path(__file__).parent
RESULTS = HERE / "results"
DEFAULT_CONFIGS = ["v1", "v2", "v2+rag", "v3+rag"]


def expected_answers(items: list[dict]) -> dict[int, object]:
    """Compute the gold answers from the warehouse, so they always match the data."""
    gold = {}
    for it in items:
        if it["type"] == "number":
            gold[it["id"]] = float(query(it["sql"]).iloc[0, 0])
        elif it["type"] == "list":
            gold[it["id"]] = [str(v) for v in query(it["sql"]).iloc[:, 0].tolist()]
        else:
            gold[it["id"]] = it.get("keywords", [])
    return gold


def score(item: dict, expected, result: dict) -> bool:
    rows, answer = result.get("rows", []), result.get("answer", "")
    if item["type"] == "number":
        return match_number(expected, rows, answer)
    if item["type"] == "list":
        return match_list(expected, rows, answer)
    if item["type"] == "text":
        return match_text(expected, answer)
    return match_refusal(answer, rows)


def run_config(name: str, items: list[dict], gold: dict, client: OllamaClient) -> pd.DataFrame:
    version, _, rag = name.partition("+")
    bot = Assistant(client, prompt_version=version, use_retrieval=bool(rag))

    records = []
    for it in items:
        started = time.perf_counter()
        try:
            result = bot.ask(it["question"])
        except ConnectionError:
            raise
        except Exception:
            result = {"answer": "", "rows": [], "trace": [], "usage": {}, "exception": traceback.format_exc()}
        seconds = time.perf_counter() - started

        ok = score(it, gold[it["id"]], result)
        usage = result.get("usage", {})
        records.append({
            "config": name,
            "id": it["id"],
            "type": it["type"],
            "question": it["question"],
            "expected": json.dumps(gold[it["id"]]),
            "answer": result.get("answer", ""),
            "sql": result.get("sql"),
            "correct": ok,
            "failure": "" if ok else classify_failure(it, result),
            "manual_label": "",
            "seconds": round(seconds, 2),
            "llm_calls": usage.get("llm_calls", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        })
        print(f"[{name}] q{it['id']:>2} {'ok ' if ok else 'BAD'} {seconds:5.1f}s  {it['question'][:60]}")
    return pd.DataFrame(records)


def summarize(df: pd.DataFrame, model: str) -> str:
    table = df.groupby("config", sort=False).agg(
        correct=("correct", "sum"),
        accuracy=("correct", "mean"),
        avg_seconds=("seconds", "mean"),
        p90_seconds=("seconds", lambda s: s.quantile(0.9)),
        avg_llm_calls=("llm_calls", "mean"),
        avg_tokens=("prompt_tokens", lambda s: (s + df.loc[s.index, "output_tokens"]).mean()),
    )
    table["accuracy"] = (table["accuracy"] * 100).round(1).astype(str) + "%"
    failures = (df[~df["correct"]].groupby(["config", "failure"]).size()
                .unstack(fill_value=0))

    lines = [
        "# Assistant evaluation",
        "",
        f"Model: `{model}` via Ollama, temperature 0. {df['id'].nunique()} questions per config.",
        "",
        "## Accuracy, latency and tokens",
        "",
        table.round(2).to_markdown(),
        "",
        "## Failures by type",
        "",
        failures.to_markdown() if not failures.empty else "No failures.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default=",".join(DEFAULT_CONFIGS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    items = json.loads((HERE / "questions.json").read_text())
    if args.limit:
        items = items[: args.limit]
    gold = expected_answers(items)

    client = OllamaClient.from_env()
    client.use_cache = not args.no_cache

    RESULTS.mkdir(exist_ok=True)
    frames = []
    for name in args.configs.split(","):
        df = run_config(name.strip(), items, gold, client)
        df.to_csv(RESULTS / f"{name.strip().replace('+', '_')}.csv", index=False)
        frames.append(df)

    all_df = pd.concat(frames)
    summary = summarize(all_df, client.model)
    (RESULTS / "summary.md").write_text(summary)
    print()
    print(summary)


if __name__ == "__main__":
    main()
