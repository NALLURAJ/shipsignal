# Findings

Short summaries of the four analyses. The full working is in `analysis/`.

## Late delivery and repeat purchase
Customers whose first order arrived late ordered again within 180 days 1.22% of the time, against 1.80% for on-time first orders. That is 0.58 percentage points lower (95% CI 0.24 to 0.92, p = 0.004), or a relative risk of 0.68. Controlling for state, category and order value gives an odds ratio of 0.69 (95% CI 0.53 to 0.91). The data is observational, so this is an association, not proof that lateness causes customers to leave. Sample: 63,681 first orders.

## Category growth and market share
From January 2017 to August 2018, only watches_gifts clearly gained share of revenue (6.7% to 10.3%). cool_stuff (6.7% to 2.9%) and garden_tools (4.9% to 2.9%) lost share. The other top categories grew at about the same pace as the marketplace. Tests: Mann-Kendall on monthly revenue share, Holm-adjusted across the top 10 categories.

## Drivers of review scores
Each extra day late lowers the review score by about 0.06 stars and raises the odds of a bad (1-2 star) review by about 18%. 9% of orders delivered a week or more early got a bad review, compared with 68% of orders 4-7 days late and about 80% of orders more than a week late. Multi-seller orders score about 1 star lower. The model explains 12% of the variation (R-squared 0.12), on 95,824 reviewed and delivered orders.

## Order forecast
Daily orders, SARIMA(2,1,1)(1,0,1,7) on log orders, against a seasonal naive baseline, on a 91-day hold-out. Daily MAPE: SARIMA 25.1%, seasonal naive 32.5%. Error on the quarter's total: SARIMA -13.4%, seasonal naive +2.3%. Forecast for 22 Aug to 20 Nov 2018: about 27,700 orders. Holidays are not modelled.
