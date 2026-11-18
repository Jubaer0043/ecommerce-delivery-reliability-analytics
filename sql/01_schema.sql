-- SQLite; monetary values are BRL. Approximate REAL arithmetic is checked to cents.
PRAGMA foreign_keys = ON;
CREATE TABLE customers (
 customer_id TEXT PRIMARY KEY NOT NULL, customer_unique_id TEXT NOT NULL,
 customer_zip_code_prefix TEXT, customer_city TEXT, customer_state TEXT
);
CREATE TABLE products (
 product_id TEXT PRIMARY KEY NOT NULL, product_category_name TEXT,
 product_name_lenght REAL, product_description_lenght REAL, product_photos_qty REAL,
 product_weight_g REAL, product_length_cm REAL, product_height_cm REAL, product_width_cm REAL
);
CREATE TABLE sellers (
 seller_id TEXT PRIMARY KEY NOT NULL, seller_zip_code_prefix TEXT, seller_city TEXT, seller_state TEXT
);
CREATE TABLE category_translation (
 product_category_name TEXT PRIMARY KEY NOT NULL, product_category_name_english TEXT
);
CREATE TABLE orders (
 order_id TEXT PRIMARY KEY NOT NULL, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
 order_status TEXT NOT NULL, order_purchase_timestamp TEXT NOT NULL, order_approved_at TEXT,
 order_delivered_carrier_date TEXT, order_delivered_customer_date TEXT, order_estimated_delivery_date TEXT
);
CREATE TABLE order_items (
 order_id TEXT NOT NULL REFERENCES orders(order_id), order_item_id INTEGER NOT NULL,
 product_id TEXT NOT NULL REFERENCES products(product_id), seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
 shipping_limit_date TEXT, price REAL NOT NULL CHECK(price >= 0),
 freight_value REAL NOT NULL CHECK(freight_value >= 0), PRIMARY KEY(order_id, order_item_id)
);
CREATE TABLE order_payments (
 order_id TEXT NOT NULL REFERENCES orders(order_id), payment_sequential INTEGER NOT NULL,
 payment_type TEXT, payment_installments INTEGER, payment_value REAL NOT NULL CHECK(payment_value >= 0),
 PRIMARY KEY(order_id, payment_sequential)
);
-- review_id is not a unique key in this source. Do not invent a uniqueness constraint.
CREATE TABLE order_reviews (
 review_id TEXT NOT NULL, order_id TEXT NOT NULL REFERENCES orders(order_id),
 review_score INTEGER NOT NULL CHECK(review_score BETWEEN 1 AND 5),
 review_comment_title TEXT, review_comment_message TEXT,
 review_creation_date TEXT, review_answer_timestamp TEXT
);
-- Zip prefixes have multiple points; never join this directly to order-level metrics.
CREATE TABLE geolocation (
 geolocation_zip_code_prefix TEXT, geolocation_lat REAL, geolocation_lng REAL,
 geolocation_city TEXT, geolocation_state TEXT
);
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_items_seller ON order_items(seller_id);
CREATE INDEX idx_reviews_order ON order_reviews(order_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
