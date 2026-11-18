"""Explicit source contract and paths shared by the pipeline and checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
EXTERNAL = ROOT / "data/external"
PROCESSED = ROOT / "data/processed"
REPORTS = ROOT / "reports"
DB = PROCESSED / "olist.sqlite3"
SOURCE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"

# All columns are required, including the publisher's original spellings.
SCHEMAS = {
    "customers": "customer_id customer_unique_id customer_zip_code_prefix customer_city customer_state".split(),
    "geolocation": "geolocation_zip_code_prefix geolocation_lat geolocation_lng geolocation_city geolocation_state".split(),
    "order_items": "order_id order_item_id product_id seller_id shipping_limit_date price freight_value".split(),
    "order_payments": "order_id payment_sequential payment_type payment_installments payment_value".split(),
    "order_reviews": "review_id order_id review_score review_comment_title review_comment_message review_creation_date review_answer_timestamp".split(),
    "orders": "order_id customer_id order_status order_purchase_timestamp order_approved_at order_delivered_carrier_date order_delivered_customer_date order_estimated_delivery_date".split(),
    "products": "product_id product_category_name product_name_lenght product_description_lenght product_photos_qty product_weight_g product_length_cm product_height_cm product_width_cm".split(),
    "sellers": "seller_id seller_zip_code_prefix seller_city seller_state".split(),
    "category_translation": "product_category_name product_category_name_english".split(),
}
FILES = {name: f"olist_{name}_dataset.csv" for name in SCHEMAS}
FILES["category_translation"] = "product_category_name_translation.csv"
KEYS = {
    "customers": ["customer_id"], "orders": ["order_id"],
    "products": ["product_id"], "sellers": ["seller_id"],
    "order_items": ["order_id", "order_item_id"],
    "order_payments": ["order_id", "payment_sequential"],
    "category_translation": ["product_category_name"],
}
DATES = {
    "orders": SCHEMAS["orders"][3:],
    "order_items": ["shipping_limit_date"],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
}
