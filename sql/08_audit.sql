-- Exclusion reasons are hierarchical, so row counts sum to the full orders table.
SELECT CASE
 WHEN order_status <> 'delivered' THEN 'Not delivered status'
 WHEN order_delivered_customer_date IS NULL THEN 'Delivered status; missing actual delivery'
 WHEN order_estimated_delivery_date IS NULL THEN 'Missing estimated delivery'
 WHEN JULIANDAY(order_delivered_customer_date) < JULIANDAY(order_purchase_timestamp)
   THEN 'Actual delivery before purchase'
 WHEN DATE(order_estimated_delivery_date) < DATE(order_purchase_timestamp)
   THEN 'Estimated delivery before purchase date'
 ELSE 'Eligible delivered' END AS cohort,
 COUNT(*) AS orders
FROM order_fact GROUP BY cohort ORDER BY orders DESC;
