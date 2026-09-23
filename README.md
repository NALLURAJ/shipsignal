# ShipSignal

End-to-end retail analytics on about 100k real e-commerce orders: a tested SQL warehouse, four business questions answered with proper statistics, a Tableau dashboard, a FastAPI service with a Streamlit front end, and a natural-language assistant with SQL guardrails that is scored against 40 questions with known answers.


**Dashboard:** _Tableau Public link goes here_ · **Notebooks:** [`analysis/`](analysis/) · **Decisions:** [`docs/decisions.md`](docs/decisions.md)

---

## Results

<!-- RESULTS -->
**Data:** 99,441 orders, 96,096 customers and 3,095 sellers (Sep 2016 to Oct 2018). All numbers below are reproducible with `make warehouse notebooks`.

| Question | Answer |
|---|---|
| Does late delivery cost repeat business? | Customers whose **first order arrived late** ordered again within 180 days **1.22%** of the time, against **1.80%** for on-time first orders: **−0.58 pp (95% CI −0.92 to −0.24), p = 0.004**, about a third fewer repeat buyers. Controlling for state, category and order value gives an odds ratio of 0.69 (0.53 to 0.91). This is an association from observational data, not a proven cause. [notebook](analysis/01_late_delivery_and_repeat_purchase.ipynb) |
| Which categories are really growing? | Almost all "growth" was the marketplace growing. Only **watches_gifts** gained revenue share (6.7% → 10.3%). **cool_stuff** (6.7% → 2.9%) and **garden_tools** (4.9% → 2.9%) lost share. Mann-Kendall test on share, Holm-corrected across 10 categories. [notebook](analysis/02_category_growth.ipynb) |
| What drives review scores? | Each day late costs about **0.06 stars** and raises the odds of a 1-2 star review by about **18%**. Bad reviews go from **9%** of orders that arrived a week early to **~80%** of orders more than a week late. Multi-seller orders score about 1 star lower. OLS with HC3 errors and a logistic check, n = 95,824. [notebook](analysis/03_review_score_drivers.ipynb) |
| Forecast next quarter's orders | On a 91-day hold-out, SARIMA beat the **seasonal naive baseline** day to day (MAPE **25.1% vs 32.5%**, MASE 1.60 vs 1.87) but was worse on the quarter's total (−13.4% vs +2.3%). Forecast for 22 Aug to 20 Nov 2018: about **27,700 orders**, with no holiday effect. [notebook](analysis/04_order_forecast.ipynb) |

**Assistant** (natural language → SQL, `qwen2.5-coder:7b` running locally in Ollama, 40 questions with answers computed from the warehouse):

| Config | What changes | Correct | Avg latency | Avg tokens |
|---|---|---:|---:|---:|
| v1 (baseline) | table and column names only | 27/40 (67.5%) | 6.4 s | 1,380 |
| v2 | column descriptions and business rules | 29/40 (72.5%) | 7.9 s | 2,727 |
| v2+rag | v2 plus retrieved metric definitions | 32/40 (80.0%) | 8.3 s | 3,001 |
| v3+rag | v2+rag plus 4 worked examples | **35/40 (87.5%)** | 8.5 s | 3,576 |

Most of the gain came from fixing *definitions*, not SQL syntax. The v1 baseline wrote valid SQL but computed revenue with freight included and on-time rate over undelivered orders. The remaining v3+rag failures are a wrong grouping, a wrong grain, a missed column, one wrong tool choice and one scorer false negative. Details are in [`eval/results/summary.md`](eval/results/summary.md).

**Engineering:** 87 pytest tests (81% coverage), 46 dbt tests, ruff and sqlfluff run in GitHub Actions on every push.

![app](docs/img/app_overview.png)
<!-- /RESULTS -->

---

## Architecture

```
 Olist csv files
       │  ingest/load_raw.py  (COPY, all text)
       ▼
 postgres: raw ──dbt──▶ staging (typed views) ──dbt──▶ marts (star schema + tests)
                                                       │
            ┌────────────────────┬─────────────────────┼─────────────────────┐
            ▼                    ▼                     ▼                     ▼
   analysis/ notebooks   bi/ csv extracts       api/ FastAPI           assistant/
   (stats, forecast)     → Tableau Public       /metrics /categories   Ollama model
                                                /delivery /forecast    + SQL guard
                                                /ask ─────────────────▶ + retrieval
                                                       ▲                 + tools
                                                       │
                                                app/ Streamlit (talks to the API only)
```

| Layer | What's in it |
|---|---|
| Warehouse | dbt: 7 staging views, 7 mart tables (`fct_orders`, `fct_order_items`, `fct_reviews`, `dim_customer`, `dim_product`, `dim_seller`, `dim_date`), generic tests and 5 business-rule tests |
| Analysis | 4 notebooks: late delivery vs repeat purchase, category growth, review score drivers, order forecast |
| Dashboard | Tableau Public, 4 pages, 14 calculated fields. Build notes in [`bi/README.md`](bi/README.md) |
| API | FastAPI, Pydantic models, input validation, JSON logs with request ids, 503s when the database or model is down |
| Assistant | JSON tool calling (`run_sql`, `lookup_definition`, `make_chart`) against a local Ollama model, with a layered SQL guard |
| Evaluation | 40 questions, gold answers computed from the warehouse, 4 configurations compared |
| Engineering | pytest, ruff, sqlfluff, dbt build in GitHub Actions on every push; `docker compose up` for the whole stack |

## Run it

You need Docker, Python 3.10+ and, for the assistant, [Ollama](https://ollama.com).

**1. Data.** Download the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) from Kaggle and unzip the 9 csv files into `data/raw/`.

**2a. Everything in Docker**

```bash
cp .env.example .env
docker compose up --build
```
This starts postgres, loads the data, builds and tests the dbt models, and starts the API (http://localhost:8000/docs) and the app (http://localhost:8501). The assistant needs Ollama running on the host: `ollama pull qwen2.5-coder:7b`.

**2b. Locally**

```bash
make setup && source .venv/bin/activate
make db          # postgres in docker
make warehouse   # load csvs + dbt build
make notebooks   # re-run the four analyses
make api         # in one terminal
make app         # in another
make eval        # score the assistant (needs ollama)
make test
```

No Kaggle account? `make sample` builds everything on a small **synthetic** dataset with the same columns. CI uses it. None of the results above come from it.

## Data-quality findings

<!-- DQ -->
The first full build ran 46 dbt tests: 43 passed and 3 warnings, all kept as warnings on purpose (see [decisions](docs/decisions.md#3-data-quality-invariants-warn-instead-of-fail)):

| Check | Rows flagged | What I did |
|---|---:|---|
| Payment total differs from items + freight by more than R$1 | 249 of 98,665 orders | Kept. Revenue is defined on item prices, so these don't affect it. Likely vouchers or interest on instalments |
| Delivered status but no delivery date | 8 | Excluded from delivery metrics (`is_delivered` requires a date) |
| Shipped or delivered with no items | 1 | Kept in order counts, contributes zero revenue |
| `review_id` reused across orders | 814 duplicate ids | Grain set to (review_id, order_id) |
| Orders with more than one review | 547 | `is_latest_for_order` flag; the order-level score uses the latest one |
| Orders with no items at all | 775 (mostly canceled/unavailable) | Zero revenue; excluded from revenue metrics by status |
| Products with no category | 610 of 32,951 | Labelled `unknown` |
| Orders after 21 Aug 2018 | volume drops to near zero | The extract is incomplete, so the forecast series stops at 21 Aug 2018 |
<!-- /DQ -->

## Limitations

- **Observational data.** The late-delivery and review findings are associations. The notebooks list the confounders and control for the measurable ones, but they don't establish cause.
- **Short history.** About 20 clean months, so the forecast has no yearly seasonality and misses Black Friday.
- **Rare outcome.** Repeat purchase is uncommon in this marketplace, so those intervals are wide relative to the base rate.
- **Local model.** The assistant runs a 7B model on a laptop. Accuracy and latency figures are for that setup and would change with a larger hosted model.
- **Keyword retrieval.** TF-IDF is enough for a small definitions file but won't handle synonyms. See [decisions](docs/decisions.md#8-tf-idf-for-retrieval).

## Data source and licence

Olist, *Brazilian E-Commerce Public Dataset by Olist*, published on Kaggle under **CC BY-NC-SA 4.0**. The data isn't redistributed in this repo; download it from the link above. This project is non-commercial.

## Repository layout

```
ingest/                    csv → postgres raw schema
warehouse/dbt_shipsignal/  staging + marts models, tests
analysis/                  4 notebooks + stats and forecast helpers
bi/                        tableau export script, build guide, screenshots
api/                       FastAPI service
app/                       Streamlit front end
assistant/                 guard, tools, retrieval, prompts, agent loop
eval/                      40 questions, scoring, results
tests/                     pytest suite
docs/                      definitions, decisions, data dictionary
```
