"""Audit original data, then clean copies with an explicit duplicate policy."""
import pandas as pd

from .config import DATES, FILES, KEYS, RAW, REPORTS, SCHEMAS
from .intake import verify_raw, write_json


def load_and_audit() -> tuple[dict[str, pd.DataFrame], dict]:
    verify_raw()
    tables, audit, errors = {}, {}, []
    for name, filename in FILES.items():
        # Read identifiers and zip prefixes as strings, preserving leading zeros.
        frame = pd.read_csv(RAW / filename, dtype="string", keep_default_na=False, na_values=[""])
        if list(frame.columns) != SCHEMAS[name]:
            errors.append(f"{name}: unexpected schema {list(frame.columns)}")
            continue
        original = len(frame)
        exact_duplicates = int(frame.duplicated().sum())
        missing = frame.isna().sum().astype(int).to_dict()
        frame = frame.drop_duplicates().copy()
        entry = {
            "raw_rows": original, "columns": len(frame.columns),
            "exact_duplicate_rows_removed": exact_duplicates,
            "clean_rows": len(frame), "missing_raw": missing,
            "invalid_dates": {}, "invalid_numeric": {},
        }
        for col in DATES.get(name, []):
            parsed = pd.to_datetime(frame[col], format="%Y-%m-%d %H:%M:%S", errors="coerce")
            bad = int((frame[col].notna() & parsed.isna()).sum())
            entry["invalid_dates"][col] = bad
            if bad:
                errors.append(f"{name}.{col}: {bad} invalid dates")
            frame[col] = parsed
        numeric = {
            "order_items": ["order_item_id", "price", "freight_value"],
            "order_payments": ["payment_sequential", "payment_installments", "payment_value"],
            "order_reviews": ["review_score"],
            "products": SCHEMAS["products"][2:],
            "geolocation": ["geolocation_lat", "geolocation_lng"],
        }.get(name, [])
        for col in numeric:
            parsed = pd.to_numeric(frame[col], errors="coerce")
            bad = int((frame[col].notna() & parsed.isna()).sum())
            entry["invalid_numeric"][col] = bad
            if bad:
                errors.append(f"{name}.{col}: {bad} invalid numbers")
            frame[col] = parsed
        if name in KEYS:
            key = KEYS[name]
            entry["null_key_rows"] = int(frame[key].isna().any(axis=1).sum())
            entry["duplicate_key_rows"] = int(frame.duplicated(key, keep=False).sum())
            if entry["null_key_rows"] or entry["duplicate_key_rows"]:
                errors.append(f"{name}: null or conflicting primary keys")
        elif name == "order_reviews":
            # review_id alone is not assumed unique. Selection happens at order grain in SQL.
            entry["orders_with_multiple_reviews"] = int(frame.groupby("order_id").size().gt(1).sum())
            if frame[["review_id", "order_id"]].isna().any().any():
                errors.append("order_reviews: missing identifiers")
        elif name == "geolocation":
            entry["zip_prefixes_with_multiple_locations"] = int(frame.groupby("geolocation_zip_code_prefix").size().gt(1).sum())
        tables[name], audit[name] = frame, entry

    if not errors:
        relationships = [
            ("orders", "customer_id", "customers", "customer_id"),
            ("order_items", "order_id", "orders", "order_id"),
            ("order_items", "product_id", "products", "product_id"),
            ("order_items", "seller_id", "sellers", "seller_id"),
            ("order_payments", "order_id", "orders", "order_id"),
            ("order_reviews", "order_id", "orders", "order_id"),
        ]
        audit["foreign_keys"] = {}
        for child, column, parent, parent_column in relationships:
            key = f"{child}.{column}->{parent}.{parent_column}"
            orphan = int((~tables[child][column].isin(tables[parent][parent_column])).sum())
            audit["foreign_keys"][key] = orphan
            if orphan:
                errors.append(f"{key}: {orphan} orphan rows")
        reviews = tables["order_reviews"]["review_score"]
        if (reviews.isna() | ~reviews.isin([1, 2, 3, 4, 5])).any():
            errors.append("Review scores must be observed integers 1–5")
        for table, cols in {"order_items": ["price", "freight_value"], "order_payments": ["payment_value"]}.items():
            if tables[table][cols].isna().any().any() or tables[table][cols].lt(0).any().any():
                errors.append(f"{table}: missing or negative monetary values")
    audit["errors"] = errors
    audit["passed"] = not errors
    write_json(REPORTS / "data_quality.json", audit)
    if errors:
        raise ValueError("Data quality gate failed: " + "; ".join(errors))
    verify_raw()
    return tables, audit
