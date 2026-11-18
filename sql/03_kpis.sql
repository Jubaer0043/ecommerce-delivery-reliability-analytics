-- Each KPI exports its denominator. Non-delivered and invalid-date orders are not "on time".
SELECT COUNT(*) AS total_orders,
 SUM(order_status = 'delivered') AS delivered_status_orders,
 SUM(delivery_eligible) AS eligible_delivered_orders,
 SUM(CASE WHEN delivery_eligible = 1 THEN is_late ELSE 0 END) AS late_orders,
 SUM(delivery_eligible) - SUM(CASE WHEN delivery_eligible = 1 THEN is_late ELSE 0 END) AS on_time_orders,
 1.0 * SUM(is_late) / NULLIF(SUM(delivery_eligible), 0) AS late_rate,
 AVG(delivery_days) AS mean_delivery_days,
 AVG(CASE WHEN delivery_eligible = 1 THEN review_score END) AS mean_review_score_eligible,
 SUM(delivery_eligible = 1 AND review_score IS NOT NULL) AS eligible_reviewed_orders
FROM order_fact;
