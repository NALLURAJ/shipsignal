# Dashboard (Tableau Public)

The dashboard is built in Tableau Public on csv extracts of the warehouse. Tableau Public only connects to files, not to postgres.

- Workbook: `shipsignal.twbx` (add it here once it's saved)
- Public link: _add after publishing_
- Screenshots: `screenshots/`

## 1. Get the data

```bash
python -m bi.export_for_tableau     # writes bi/extracts/*.csv
```

## 2. Data model

In Tableau Public: **Connect → Text file → `fct_orders.csv`**, then drag in the other files and set up **relationships** (not joins):

| From | To | Fields |
|---|---|---|
| fct_orders | fct_order_items | Order Id = Order Id |
| fct_order_items | dim_seller | Seller Id = Seller Id |
| fct_orders | dim_date | Purchase Date = Date Day |
| fct_orders | dim_customer | Customer Unique Id = Customer Unique Id |

Set `Purchase Date` and `Date Day` to type **Date**. Relationships keep each table at its own grain, so order-level measures aren't duplicated by the item rows. With a plain join, revenue would be double counted on multi-item orders.

## 3. Calculated fields

These match `docs/definitions.md`. Field names below are how Tableau displays the csv column names.

| # | Name | Formula |
|---|---|---|
| 1 | Revenue | `SUM(IF [Order Status] <> 'canceled' AND [Order Status] <> 'unavailable' THEN [Items Value] END)` |
| 2 | Orders | `COUNTD(IF [Order Status] <> 'canceled' AND [Order Status] <> 'unavailable' THEN [Order Id] END)` |
| 3 | Average Order Value | `[Revenue] / [Orders]` |
| 4 | Delivered Orders | `SUM([Is Delivered])` |
| 5 | On-time Rate | `SUM(IF [Is Delivered] = 1 AND [Is Late] = 0 THEN 1 ELSE 0 END) / [Delivered Orders]` |
| 6 | Late Orders | `SUM(IF [Is Delivered] = 1 THEN [Is Late] END)` |
| 7 | Avg Days Late (late orders) | `AVG(IF [Is Late] = 1 THEN [Delay Days] END)` |
| 8 | Avg Delivery Days | `AVG([Delivery Days])` |
| 9 | Avg Review | `AVG([Review Score])` |
| 10 | Bad Review Rate | `SUM(IF [Review Score] <= 2 THEN 1 ELSE 0 END) / COUNT([Review Score])` |
| 11 | Freight Share | `SUM([Freight Value (fct_orders)]) / (SUM([Items Value]) + SUM([Freight Value (fct_orders)]))` |
| 12 | Item Revenue | `SUM(IF [Order Status (fct_order_items)] <> 'canceled' AND [Order Status (fct_order_items)] <> 'unavailable' THEN [Price] END)` |
| 13 | Revenue Prior Year | `LOOKUP([Revenue], -12)` (table calculation, compute along month of Purchase Date) |
| 14 | Revenue YoY % | `([Revenue] - LOOKUP([Revenue], -12)) / ABS(LOOKUP([Revenue], -12))` (same) |

Notes:
- 13 and 14 need a continuous **month** of Purchase Date on the view. Set *Compute Using → Purchase Date*. The first 12 months come out empty because there is no prior year to compare with. That's correct, not a bug.
- If both tables have a column with the same name, Tableau adds the table name in brackets, e.g. `Freight Value (fct_orders)`. Pick the right one when you type the formula.

## 4. Pages

**Executive summary**
- KPI tiles: Revenue, Orders, Average Order Value, On-time Rate, Avg Review
- Line: Revenue by month, with Revenue YoY % in the tooltip
- Bar: Orders by weekday (dim_date)
- Filters: Purchase Date range, Customer State

**Category deep-dive**
- Bar: Item Revenue by Category (top 15, sorted)
- Line: Item Revenue by month for the selected category
- Table: category, Item Revenue, items, Avg Review, Bad Review Rate
- **Drill-through:** a dashboard *Filter action* from the category bar to the detail sheets (Dashboard → Actions → Add Action → Filter, source = category bar, run on Select)

**Delivery performance** (the notebook 1 finding)
- Map or bar: On-time Rate by Customer State
- Line: On-time Rate and Avg Delivery Days by month (dual axis)
- Bar: Avg Review by delay bucket. Create a group or bins on Delay Days: early, 1-3, 4-7, 8-14, 15+ days late
- Text box with the result from notebook 1 (repeat rate after a late vs on-time first order, with the confidence interval)

**Seller quality**
- Scatter: sellers, x = Orders, y = On-time Rate, size = Revenue, colour = Avg Review
- Table: worst 20 sellers with at least 30 orders by Bad Review Rate
- Filter: Seller State

Formatting: one colour for revenue measures, one for delivery, red used only for "bad" (late, 1-2 stars). R$ number format with no decimals on tiles.

## 5. Publish

File → Save to Tableau Public (you need a free Tableau Public account). Then:
1. Paste the link at the top of this file and in the main README.
2. Export each dashboard as an image (Dashboard → Export Image) into `bi/screenshots/`.
3. File → Export Packaged Workbook to save `shipsignal.twbx` in this folder.
