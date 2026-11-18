"""Independent checks against raw bytes, real-data outputs, and executed notebooks."""
import json
from contextlib import closing

import numpy as np
import pandas as pd

from .config import REPORTS, ROOT
from .database import check_database, connect
from .intake import verify_raw, write_json
from .notebooks import NOTEBOOK_NAMES
from .statistics import association


def validate_outputs() -> dict:
    hashes = verify_raw()
    with closing(connect()) as con:
        model = check_database(con)
        fact = pd.read_sql_query("SELECT * FROM order_fact", con)
    quality = json.loads((REPORTS / "data_quality.json").read_text())
    statistics = json.loads((REPORTS / "statistics.json").read_text())
    kpi = pd.read_csv(REPORTS / "tables/kpis.csv").iloc[0]
    eligible = fact.loc[fact.delivery_eligible.eq(1)]
    # Independent Python definitions instead of trusting the exported SQL aggregate.
    actual = pd.to_datetime(eligible.order_delivered_customer_date)
    expected = pd.to_datetime(eligible.order_estimated_delivery_date)
    late = actual.dt.normalize().gt(expected.dt.normalize())
    python_effect = association(fact)
    checks = {
        "source_checksums_unchanged": len(hashes) == 9,
        "quality_gate_passed": quality["passed"],
        "database_gate_passed": model["passed"],
        "kpi_order_count": int(kpi.total_orders) == len(fact),
        "kpi_eligible_count": int(kpi.eligible_delivered_orders) == len(eligible),
        "kpi_late_count": int(kpi.late_orders) == int(late.sum()),
        "kpi_late_rate": bool(np.isclose(kpi.late_rate, late.mean())),
        "statistics_match_model": all(np.isclose(statistics["primary"][key], value) for key,value in python_effect.items() if value is not None),
    }
    for dimension in ["monthly", "states"]:
        frame = pd.read_csv(REPORTS / "tables" / f"{dimension}.csv")
        checks[f"{dimension}_totals_reconcile"] = int(frame.total_orders.sum()) == len(fact) and int(frame.eligible_orders.sum()) == len(eligible) and int(frame.late_orders.sum()) == int(late.sum())
    cohort = pd.read_csv(REPORTS / "tables/audit.csv")
    checks["cohort_exclusions_reconcile"] = int(cohort.orders.sum()) == len(fact)
    reports = ["analytical_report.md", "statistics.json", "source_manifest.json", "environment.json"]
    figures = ["01_monthly_reliability", "02_state_reliability", "03_low_review_rates", "04_review_distribution", "05_delivery_time_ecdf", "06_sensitivity"]
    checks["reports_present"] = all((REPORTS / name).is_file() for name in reports)
    checks["six_figures_present"] = all((REPORTS / "figures" / f"{name}.png").is_file() for name in figures)
    import nbformat
    notebooks = sorted((ROOT / "notebooks").glob("*.ipynb"))
    executed = True
    for path in notebooks:
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                executed &= cell.execution_count is not None and not any(out.output_type == "error" for out in cell.outputs)
    checks["notebook_sequence_executed_without_errors"] = (
        tuple(path.name for path in notebooks) == NOTEBOOK_NAMES and bool(executed)
    )
    result = {"checks": {key: bool(value) for key,value in checks.items()}, "passed": bool(all(checks.values()))}
    write_json(REPORTS / "final_validation.json", result)
    if not result["passed"]:
        raise ValueError(f"Final validation failed: {result}")
    return result
