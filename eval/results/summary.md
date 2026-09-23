# Assistant evaluation

Model: `qwen2.5-coder:7b` via Ollama, temperature 0. 40 questions per config.

## Accuracy, latency and tokens

| config   |   correct | accuracy   |   avg_seconds |   p90_seconds |   avg_llm_calls |   avg_tokens |
|:---------|----------:|:-----------|--------------:|--------------:|----------------:|-------------:|
| v1       |        27 | 67.5%      |          6.35 |          9.97 |            2.17 |      1379.62 |
| v2       |        29 | 72.5%      |          7.85 |         11.8  |            2.22 |      2727.04 |
| v2+rag   |        32 | 80.0%      |          8.29 |         12.1  |            2.17 |      3000.89 |
| v3+rag   |        35 | 87.5%      |          8.51 |         13.07 |            2.25 |      3576.27 |

## Failures by type

| config   |   definition_wrong_or_missing |   did_not_refuse |   hallucinated_column_or_table |   sql_error |   step_limit |   wrong_result |
|:---------|------------------------------:|-----------------:|-------------------------------:|------------:|-------------:|---------------:|
| v1       |                             1 |                1 |                              0 |           0 |            0 |             11 |
| v2       |                             1 |                0 |                              1 |           1 |            0 |              8 |
| v2+rag   |                             0 |                0 |                              2 |           0 |            1 |              5 |
| v3+rag   |                             1 |                1 |                              1 |           0 |            0 |              2 |

## Notes from reading the failures (v3+rag)

The failure types above are assigned by a script. I read each failed question in `v3_rag.csv` and wrote a `manual_label`:

| q | What went wrong |
|---|---|
| 21 | Grouped by calendar month across both years (August) instead of year-month (2017-11). The question is ambiguous, and every config made the same choice |
| 23 | Joined every item instead of only the first item of each order, as the question asked. 2 of 3 categories were right |
| 25 | Didn't use `dim_date.is_weekend` and said "weekend" wasn't defined |
| 37 | Called the chart tool for a definition question |
| 40 | **Scorer false negative:** the reply did decline ("must be a SELECT query") and nothing was run. With this counted, v3+rag gets 36/40 |

No write reached the database in any of the 160 runs. Every query that ran passed the guard as a single `SELECT` inside a read-only transaction. For the delete request, v1 didn't decline; it ran a read-only `SELECT` instead.
