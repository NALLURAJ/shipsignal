# Decisions


## 1. Load everything as text, cast in dbt
The loader copies every csv column into postgres as `text`, and types are set in the staging models.
**Why:** a bad date or number shows up as a failing model or test with a clear location, instead of a crashed load halfway through a 100k-row file.
**Cost:** the raw schema is untyped, and the casts are repeated in the staging models instead of being declared once.

## 2. `customer_unique_id` is the customer
Olist creates a new `customer_id` for every order. Anything about repeat purchase or customer counts uses `customer_unique_id`, and `dim_customer` is keyed on it.
**Cost:** a customer's location is taken from their first order. A few customers ordered from more than one state.

## 3. Data-quality invariants warn instead of fail
Payments that don't match items plus freight, and delivered orders with no delivery date, are real features of this data (vouchers, missing scans). Those tests use `severity: warn` and their counts are reported in the README instead of blocking the build.
**Cost:** a new problem of the same kind wouldn't stop the pipeline. The counts need to be checked when the data changes.

## 4. Repeat purchase = an order after the first one arrived, within 180 days
Counting any second order would include people who placed two orders on the same day, before they could know whether delivery was late. First orders delivered in the last 180 days of the data are dropped so everyone gets the same follow-up window.
**Cost:** a smaller sample, and it ignores loyal customers who come back after more than six months.

## 5. Daily forecast with a weekly season, not monthly
There are only about 20 clean months, which isn't enough for a model with yearly seasonality. Daily data with a weekly pattern gives the model hundreds of points to learn from. The baseline is a seasonal naive forecast (repeat last week).
**Cost:** holiday peaks like Black Friday aren't modelled. The notebook says so.

## 6. Plain JSON tool calling instead of a framework
The assistant asks the model for one JSON object per turn (`{"tool": ...}` or `{"answer": ...}`) and runs the loop itself, about 100 lines. Ollama's `format: "json"` keeps small local models on track.
**Why:** it works with any local model, has no framework version churn, and every step can be tested with a scripted fake model.
**Cost:** no streaming, no parallel tool calls, and adding a tool means editing the loop.

## 7. The SQL guard is layered
The model's SQL is parsed with sqlglot and rejected unless it is a single SELECT on allow-listed tables and columns with no blocked functions. It then runs in a `READ ONLY` transaction with a `statement_timeout` and a row limit.
**Why:** the parser check gives the model a readable error it can fix. The database settings are the backstop if the parser ever misses something.
**Cost:** some valid queries are rejected, such as table functions like `generate_series`.

## 8. TF-IDF for retrieval
The definitions and findings documents are around thirty short sections. TF-IDF retrieves the right one for the evaluation questions and needs no model download.
**Cost:** it only matches on shared words, so "punctual" finds nothing unless that word is in the doc. If the corpus grows, switch to embeddings (`nomic-embed-text` in Ollama); only `DefinitionIndex` would change.
