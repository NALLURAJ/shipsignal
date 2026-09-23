# Assistant evaluation

`questions.json` has 40 questions:

| Type | Count | Marked correct when |
|---|---|---|
| number | 28 | the expected value (computed from the gold SQL) is within 1% of a number in the assistant's result rows or answer. A rate can come back as a fraction or a percentage |
| list | 7 | every expected item appears in the top rows of the assistant's result, or in its answer |
| text | 4 | the answer contains the key terms from the definitions doc |
| refuse | 1 | the answer declines a destructive request |

Expected answers are **computed from the warehouse at run time** by the gold SQL. They are not typed in by hand, so they stay right if the data is rebuilt.

## Configurations

| Config | Prompt | Retrieval |
|---|---|---|
| `v1` | table and column names only (baseline) | no |
| `v2` | column descriptions and business rules | no |
| `v2+rag` | same as v2 | top-2 definition sections added to the question, plus the `lookup_definition` tool |
| `v3+rag` | v2 plus four worked examples | yes |

## Run

```bash
ollama pull qwen2.5-coder:7b
python -m eval.run_eval                          # all four configs
python -m eval.run_eval --configs v3+rag --limit 5   # quick check
```

Replies are cached in `.cache/llm/`, so re-running only re-scores. Use `--no-cache` for fresh calls.

Output: `results/<config>.csv` (one row per question, with the SQL, the answer and the failure type) and `results/summary.md`.

## Failure types

Assigned automatically:
- `answered_without_sql`: gave a number without querying
- `hallucinated_column_or_table`: used a column or table that doesn't exist
- `rejected_by_guard` / `sql_error`: never got a query to run
- `wrong_result`: the query ran but the answer was wrong
- `definition_wrong_or_missing`, `did_not_refuse`, `step_limit`

`wrong_result` rows have an empty `manual_label` column. Read the SQL and label them (`wrong filter`, `wrong join`, `wrong date range`, `wrong definition`). This is the part of the error analysis that can't be automated honestly.
