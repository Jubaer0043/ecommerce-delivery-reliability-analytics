SELECT CASE is_late WHEN 1 THEN 'Late' ELSE 'On time' END AS delivery_group,
 COUNT(*) AS eligible_orders, COUNT(review_score) AS reviewed_orders,
 1.0 * COUNT(review_score) / COUNT(*) AS review_coverage,
 AVG(review_score) AS mean_review_score, SUM(low_review) AS low_review_orders,
 1.0 * SUM(low_review) / NULLIF(COUNT(review_score), 0) AS low_review_rate
FROM order_fact WHERE delivery_eligible = 1
GROUP BY is_late ORDER BY is_late;
