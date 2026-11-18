SELECT customer_state, COUNT(*) AS total_orders,
 SUM(delivery_eligible) AS eligible_orders, SUM(is_late) AS late_orders,
 1.0 * SUM(is_late) / NULLIF(SUM(delivery_eligible), 0) AS late_rate,
 AVG(delivery_days) AS mean_delivery_days,
 AVG(CASE WHEN delivery_eligible = 1 THEN review_score END) AS mean_review_score
FROM order_fact GROUP BY customer_state ORDER BY eligible_orders DESC;
