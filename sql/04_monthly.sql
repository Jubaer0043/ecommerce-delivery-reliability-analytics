-- Purchase cohorts. First/last months may be partial; these are historical snapshot outcomes.
SELECT purchase_month, COUNT(*) AS total_orders, SUM(delivery_eligible) AS eligible_orders,
 SUM(is_late) AS late_orders,
 1.0 * SUM(is_late) / NULLIF(SUM(delivery_eligible), 0) AS late_rate,
 AVG(delivery_days) AS mean_delivery_days
FROM order_fact GROUP BY purchase_month ORDER BY purchase_month;
