-- An order can appear in multiple categories. Category rows are NOT additive.
-- Review/delivery outcomes belong to the whole order, not to an individual item.
WITH order_categories AS (
 SELECT DISTINCT i.order_id, COALESCE(t.product_category_name_english,
       p.product_category_name, 'Unknown') AS category
 FROM order_items i JOIN products p USING(product_id)
 LEFT JOIN category_translation t USING(product_category_name)
)
SELECT c.category, COUNT(*) AS orders_containing_category,
 SUM(f.delivery_eligible) AS eligible_orders, SUM(f.is_late) AS late_orders,
 1.0 * SUM(f.is_late) / NULLIF(SUM(f.delivery_eligible), 0) AS late_rate,
 AVG(CASE WHEN f.delivery_eligible = 1 THEN f.review_score END) AS mean_review_score
FROM order_categories c JOIN order_fact f USING(order_id)
GROUP BY c.category ORDER BY eligible_orders DESC;
