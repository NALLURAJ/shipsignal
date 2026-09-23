# Metric definitions

These are the definitions used by the dbt models, the API, the dashboard and the assistant. If a number doesn't match between two of them, one of them is wrong.

## Revenue
Revenue is the sum of item prices (`items_value` in `fct_orders`, `price` in `fct_order_items`). It does **not** include freight. Orders with status `canceled` or `unavailable` are excluded from revenue. Currency is Brazilian reais (R$).

## Orders
An order is one row in `fct_orders`. Order counts used for revenue metrics exclude `canceled` and `unavailable` orders. The forecast counts every order placed, whatever its status, because it forecasts demand rather than revenue.

## Average order value (AOV)
Revenue divided by the number of orders that count toward revenue. Freight is not included.

## Freight
Shipping cost charged to the customer, stored per item in `freight_value`. The freight share of an order is freight divided by items plus freight.

## Customer
A customer is a `customer_unique_id`. Olist also has a `customer_id`, but that one is created fresh for every order, so counting it counts orders, not people.

## Repeat customer
A customer with more than one order (`lifetime_orders > 1` in `dim_customer`). In the late-delivery analysis a stricter version is used: another order placed after the first order was delivered and within 180 days of that delivery.

## On-time delivery
An order is on time when it reached the customer on or before the estimated delivery date that was shown at purchase (`is_late = false`). The on-time rate is the share of delivered orders that were on time. Orders that were never delivered are not part of the on-time rate at all. Also called punctuality, or delivered on schedule; the opposite is a late delivery.

## Late delivery and delay
`delay_days` is the delivered date minus the estimated date. Positive means late, negative means early. `is_late` is true when `delay_days > 0`.

## Delivery time
`delivery_days` is the number of days from purchase to delivery.

## Review score
Customers rate an order from 1 to 5 stars. Some orders have more than one review; the order-level score in `fct_orders.review_score` is the latest one. A bad review is 1 or 2 stars.

## Order status
Possible values: delivered, shipped, canceled, unavailable, invoiced, processing, created, approved. Only `delivered` orders with a delivery date count as delivered.

## Category
The English product category from the Olist translation file. Two categories have no translation and keep their Portuguese name. Products with no category are labelled `unknown`.

## Seller
A merchant selling on the Olist marketplace. One order can contain items from several sellers.

## Time period
Orders run from September 2016 to October 2018. 2016 is mostly test orders and the last weeks of 2018 are incomplete, so trend and forecast work uses January 2017 to August 2018.

## Payment total
What the customer paid, summed across payment methods (credit card, boleto, voucher, debit card). It usually equals items plus freight. The exceptions are counted by a warning-level data test.
