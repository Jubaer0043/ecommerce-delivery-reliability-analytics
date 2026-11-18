"""Build a constrained SQLite database in a temporary file, then validate it."""
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DB, PROCESSED, REPORTS, ROOT
from .intake import verify_raw, write_json
from .quality import load_and_audit

LOAD_ORDER = ["customers", "products", "sellers", "category_translation", "orders",
              "order_items", "order_payments", "order_reviews", "geolocation"]


def connect(path: Path = DB) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def check_database(con: sqlite3.Connection) -> dict:
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
    fact = pd.read_sql_query("SELECT * FROM order_fact", con)
    orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    money = {}
    for source, column, fact_column in [
        ("order_items", "price", "merchandise_value_brl"),
        ("order_items", "freight_value", "freight_value_brl"),
        ("order_payments", "payment_value", "payment_value_brl"),
    ]:
        original = con.execute(f"SELECT SUM({column}) FROM {source}").fetchone()[0]
        derived = float(fact[fact_column].sum())
        money[fact_column] = {"source_total": original, "fact_total": derived,
                              "absolute_difference": abs(original - derived)}
    eligible = fact.loc[fact.delivery_eligible.eq(1)].copy()
    actual = pd.to_datetime(eligible.order_delivered_customer_date)
    expected = pd.to_datetime(eligible.order_estimated_delivery_date)
    python_late = actual.dt.normalize().gt(expected.dt.normalize()).astype(int)
    checks = {
        "sqlite_integrity": integrity == "ok", "foreign_keys": not foreign_keys,
        "one_row_per_order": len(fact) == orders and fact.order_id.is_unique,
        "money_reconciles_to_cent": all(v["absolute_difference"] < 0.01 for v in money.values()),
        "sql_python_late_flags_agree": np.array_equal(python_late.to_numpy(), eligible.is_late.to_numpy()),
        "ineligible_orders_have_null_outcomes": fact.loc[fact.delivery_eligible.eq(0), ["is_late", "delivery_days", "signed_delay_days"]].isna().all().all().item(),
        "eligible_durations_nonnegative": bool(eligible.delivery_days.ge(0).all()),
    }
    result = {"checks": {k: bool(v) for k, v in checks.items()}, "order_count": orders,
              "money_reconciliation": money, "passed": bool(all(checks.values()))}
    if not result["passed"]:
        raise ValueError(f"Database gate failed: {result}")
    return result


def build_database() -> dict:
    tables, _ = load_and_audit()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    temporary = PROCESSED / "olist.build.sqlite3"
    temporary.unlink(missing_ok=True)  # Derived staging artifact only.
    try:
        with closing(connect(temporary)) as con:
            con.executescript((ROOT / "sql/01_schema.sql").read_text())
            for name in LOAD_ORDER:
                tables[name].to_sql(name, con, if_exists="append", index=False, chunksize=10000)
            con.executescript((ROOT / "sql/02_order_fact.sql").read_text())
            checks = check_database(con)
            con.commit()
        verify_raw()
        temporary.replace(DB)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(REPORTS / "model_validation.json", checks)
    return checks


def export_queries() -> dict[str, pd.DataFrame]:
    (REPORTS / "tables").mkdir(parents=True, exist_ok=True)
    with closing(connect()) as con:
        check_database(con)
        outputs = {}
        for path in sorted((ROOT / "sql").glob("*.sql")):
            if int(path.name[:2]) < 3:
                continue
            frame = pd.read_sql_query(path.read_text(), con)
            name = path.stem[3:]
            frame.to_csv(REPORTS / "tables" / f"{name}.csv", index=False)
            outputs[name] = frame
    return outputs
