"""Execute SQL exploration and pre-specified statistical/sensitivity analyses."""
from contextlib import closing

import numpy as np
import pandas as pd

from .config import REPORTS
from .database import connect, export_queries
from .intake import verify_raw, write_json
from .statistics import association, cluster_bootstrap_difference, independent_customer_diagnostics, wilson_interval


def read_fact() -> pd.DataFrame:
    with closing(connect()) as con:
        return pd.read_sql_query("SELECT * FROM order_fact", con)


def run_analysis() -> dict:
    verify_raw()
    outputs = export_queries()
    fact = read_fact()
    if not fact.delivery_eligible.sum():
        raise ValueError("No eligible orders; cannot produce delivery analysis")
    for name in ["states", "monthly", "category_context"]:
        table = outputs[name]
        low, high = wilson_interval(table.late_orders.fillna(0), table.eligible_orders)
        table["late_rate_ci_low"], table["late_rate_ci_high"] = low, high
        table.to_csv(REPORTS / "tables" / f"{name}.csv", index=False)
    reviewed = outputs["reviews"]
    reviewed["low_rate_ci_low"], reviewed["low_rate_ci_high"] = wilson_interval(reviewed.low_review_orders, reviewed.reviewed_orders)
    reviewed.to_csv(REPORTS / "tables/reviews.csv", index=False)
    summaries = fact.loc[fact.delivery_eligible.eq(1), ["delivery_days", "signed_delay_days", "item_count", "seller_count", "merchandise_value_brl", "freight_value_brl"]].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]).T
    summaries.to_csv(REPORTS / "tables/distributions.csv", index_label="metric")
    fact.groupby("order_status").size().rename("orders").to_csv(REPORTS / "tables/order_status.csv")

    result = {
        "primary": association(fact),
        "risk_difference_ci": cluster_bootstrap_difference(fact),
        "independent_customer_diagnostics": independent_customer_diagnostics(fact),
    }
    rows = []

    def sensitivity(label, sample):
        effect = association(sample)
        rows.append({"scenario": label, "eligible_orders": int(sample.delivery_eligible.sum()), **effect})

    sensitivity("Primary: latest answered review; calendar-day deadline", fact)
    sensitivity("Review answered on/after actual delivery", fact.loc[fact.review_answered_after_delivery.eq(1)])
    sensitivity("Exclude carrier chronology anomalies", fact.loc[fact.carrier_chronology_anomaly.eq(0) & fact.carrier_before_purchase.eq(0)])
    single = fact.loc[fact.delivery_eligible.eq(1) & fact.review_score.notna()].sort_values(["order_purchase_timestamp", "order_id"]).drop_duplicates("customer_unique_id")
    sensitivity("Earliest eligible reviewed order per customer", single)
    strict = fact.copy()
    strict["is_late"] = np.where(strict.delivery_eligible.eq(1),
        pd.to_datetime(strict.order_delivered_customer_date).gt(pd.to_datetime(strict.order_estimated_delivery_date)).astype(int), np.nan)
    sensitivity("Alternative: strict timestamp deadline", strict)
    with closing(connect()) as con:
        earliest = pd.read_sql_query("""
          WITH ranked AS (
            SELECT order_id, review_score, ROW_NUMBER() OVER (
              PARTITION BY order_id ORDER BY review_answer_timestamp, review_creation_date,
              review_id, review_score, COALESCE(review_comment_title,''), COALESCE(review_comment_message,'')
            ) AS rn FROM order_reviews
          ) SELECT order_id, review_score FROM ranked WHERE rn = 1
        """, con)
        range_row = con.execute("SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp) FROM orders").fetchone()
    first_review = fact.drop(columns=["review_score"]).merge(earliest, on="order_id", how="left", validate="one_to_one")
    sensitivity("Earliest answered review instead of latest", first_review)
    pd.DataFrame(rows).to_csv(REPORTS / "tables/sensitivity.csv", index=False)
    result["context"] = {
        "purchase_timestamp_min": range_row[0], "purchase_timestamp_max": range_row[1],
        "eligible_orders": int(fact.delivery_eligible.sum()),
        "carrier_chronology_anomalies": int(fact.carrier_chronology_anomaly.sum()),
        "carrier_before_purchase": int(fact.carrier_before_purchase.sum()),
        "eligible_review_answers_before_delivery": int((fact.delivery_eligible.eq(1) & fact.review_answered_after_delivery.eq(0)).sum()),
        "eligible_orders_without_review": int((fact.delivery_eligible.eq(1) & fact.review_score.isna()).sum()),
        "eligible_median_delivery_days": float(fact.loc[fact.delivery_eligible.eq(1), "delivery_days"].median()),
    }
    if not (result["risk_difference_ci"]["lower"] <= result["primary"]["risk_difference"] <= result["risk_difference_ci"]["upper"]):
        raise ValueError("Unexpected bootstrap interval; inspect before reporting")
    write_json(REPORTS / "statistics.json", result)
    verify_raw()
    return result
