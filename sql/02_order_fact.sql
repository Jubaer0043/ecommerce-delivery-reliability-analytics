-- Aggregate each one-to-many relationship BEFORE joining. One row per order.
CREATE VIEW order_fact AS
WITH item_totals AS (
 SELECT order_id, COUNT(*) AS item_count, COUNT(DISTINCT seller_id) AS seller_count,
        SUM(price) AS merchandise_value_brl, SUM(freight_value) AS freight_value_brl
 FROM order_items GROUP BY order_id
), payment_totals AS (
 SELECT order_id, COUNT(*) AS payment_record_count, SUM(payment_value) AS payment_value_brl
 FROM order_payments GROUP BY order_id
), ranked_reviews AS (
 SELECT *, ROW_NUMBER() OVER (
   PARTITION BY order_id
   ORDER BY review_answer_timestamp DESC, review_creation_date DESC, review_id DESC,
            review_score DESC, COALESCE(review_comment_title, '') DESC,
            COALESCE(review_comment_message, '') DESC
 ) AS review_rank, COUNT(*) OVER (PARTITION BY order_id) AS review_count
 FROM order_reviews
), base AS (
 SELECT o.*, c.customer_unique_id, c.customer_state, c.customer_city,
        STRFTIME('%Y-%m', o.order_purchase_timestamp) AS purchase_month,
        i.item_count, i.seller_count, i.merchandise_value_brl, i.freight_value_brl,
        p.payment_record_count, p.payment_value_brl,
        r.review_score, r.review_answer_timestamp, r.review_creation_date, r.review_count,
        CASE WHEN o.order_status = 'delivered'
               AND o.order_delivered_customer_date IS NOT NULL
               AND o.order_estimated_delivery_date IS NOT NULL
               AND JULIANDAY(o.order_delivered_customer_date) >= JULIANDAY(o.order_purchase_timestamp)
               AND DATE(o.order_estimated_delivery_date) >= DATE(o.order_purchase_timestamp)
             THEN 1 ELSE 0 END AS delivery_eligible,
        CASE WHEN o.order_delivered_customer_date < o.order_delivered_carrier_date
             THEN 1 ELSE 0 END AS carrier_chronology_anomaly,
        CASE WHEN o.order_delivered_carrier_date < o.order_purchase_timestamp
             THEN 1 ELSE 0 END AS carrier_before_purchase
 FROM orders o
 JOIN customers c USING(customer_id)
 LEFT JOIN item_totals i USING(order_id)
 LEFT JOIN payment_totals p USING(order_id)
 LEFT JOIN ranked_reviews r ON o.order_id = r.order_id AND r.review_rank = 1
)
SELECT *,
 CASE WHEN delivery_eligible = 1 THEN
   CASE WHEN DATE(order_delivered_customer_date) > DATE(order_estimated_delivery_date)
        THEN 1 ELSE 0 END END AS is_late,
 CASE WHEN delivery_eligible = 1
      THEN JULIANDAY(order_delivered_customer_date) - JULIANDAY(order_purchase_timestamp)
      END AS delivery_days,
 CASE WHEN delivery_eligible = 1
      THEN JULIANDAY(DATE(order_delivered_customer_date)) - JULIANDAY(DATE(order_estimated_delivery_date))
      END AS signed_delay_days,
 CASE WHEN review_score IS NOT NULL THEN CASE WHEN review_score <= 2 THEN 1 ELSE 0 END END AS low_review,
 CASE WHEN review_answer_timestamp IS NOT NULL AND order_delivered_customer_date IS NOT NULL
      THEN CASE WHEN review_answer_timestamp >= order_delivered_customer_date THEN 1 ELSE 0 END
      END AS review_answered_after_delivery
FROM base;
