"""Maintain readable notebook source; executing this resets notebook outputs."""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]


def write(name, cells):
    notebook = nbf.v4.new_notebook()
    notebook.metadata.kernelspec = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook.metadata.language_info = {"name": "python"}
    notebook.cells = []
    for index, (kind, source) in enumerate(cells):
        cell = (nbf.v4.new_markdown_cell if kind == "md" else nbf.v4.new_code_cell)(
            source.strip()
        )
        cell.id = f"cell-{index:02d}"
        notebook.cells.append(cell)
    nbf.validate(notebook)
    nbf.write(notebook, ROOT / "notebooks" / name)


write(
    "00_source_and_relational_schema.ipynb",
    [
        (
            "md",
            """# 00 · Source and relational schema

Operations wants to know where orders miss their promised date and how lateness relates to customer feedback. This first notebook maps the nine Olist CSVs and identifies the join grain needed for both questions. The displayed data comes from the verified local pipeline. Run the [reproduction steps](../README.md#reproduce) to execute the cells.

[Notebook guide](../README.md#notebook-guide) · [Next](01_data_quality_and_sql.ipynb)
""",
        ),
        (
            "code",
            """import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
from IPython.display import display

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
assert (ROOT / "src/olist_analytics").is_dir(), (
    "Open from the project root or notebooks directory."
)
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"


DB = ROOT / "data/processed/olist.sqlite3"
DB_URI = DB.as_uri() + "?mode=ro"
""",
        ),
        (
            "md",
            """## What does each source row represent?

Review the recorded import counts against each table’s role. Orders carry promise and delivery timestamps. Items, payments and reviews can contribute several rows to the same order. Customer location joins through customer_id. Customer clustering uses customer_unique_id across orders.
""",
        ),
        (
            "code",
            """quality = json.loads((REPORTS / "data_quality.json").read_text())
audit_tables = pd.DataFrame.from_dict(
    {
        name: info
        for name, info in quality.items()
        if isinstance(info, dict) and "raw_rows" in info
    },
    orient="index",
)[["raw_rows", "clean_rows", "exact_duplicate_rows_removed"]]
manifest = json.loads((REPORTS / "source_manifest.json").read_text())
print(f"Source archive SHA-256 {manifest['archive_sha256']}")
display(audit_tables)
""",
        ),
        (
            "md",
            """## How could a join inflate counts?

Count repeated order keys in each child table with GROUP BY and HAVING. These are normal relational multiplicities. Joining several children directly on order_id would form combinations of their rows.
""",
        ),
        (
            "code",
            '''with closing(sqlite3.connect(DB_URI, uri=True)) as connection:
    for table in ("order_items", "order_payments", "order_reviews"):
        sql = f"""
        SELECT COUNT(*) AS orders_with_multiple_rows
        FROM (
            SELECT order_id
            FROM {table}
            GROUP BY order_id
            HAVING COUNT(*) > 1
        )
        """
        print(sql.strip())
        display(pd.read_sql_query(sql, connection).assign(source=table))
''',
        ),
        (
            "md",
            """Child tables need a defined reduction before the order join. Geolocation can also repeat at postal-prefix grain and has no role in the state join. The next notebook checks which records and fields can support an order-level model.
""",
        ),
        (
            "md",
            """[Notebook guide](../README.md#notebook-guide) · [Next](01_data_quality_and_sql.ipynb)
""",
        ),
    ],
)

write(
    "01_data_quality_and_sql.ipynb",
    [
        (
            "md",
            """# 01 · Data quality, cleaning, and SQL modeling

Build an order-level analysis that preserves financial totals and handles missing dates and repeat reviews consistently. The previous notebook established why the raw child tables need pre-aggregation.

[Previous](00_source_and_relational_schema.ipynb) · [Notebook guide](../README.md#notebook-guide) · [Next](02_delivery_and_satisfaction.ipynb)
""",
        ),
        (
            "code",
            """import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
from IPython.display import display

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
assert (ROOT / "src/olist_analytics").is_dir(), (
    "Open from the project root or notebooks directory."
)
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"


DB = ROOT / "data/processed/olist.sqlite3"
DB_URI = DB.as_uri() + "?mode=ro"
""",
        ),
        (
            "md",
            """## Which missing fields affect the analysis?

The pipeline removes exact duplicates in derived data, checks keys and preserves null source values. Use the recorded field-level counts to distinguish relevant missing dates from optional review text.
""",
        ),
        (
            "code",
            """quality = json.loads((REPORTS / "data_quality.json").read_text())
missing = pd.DataFrame(
    (name, field, count, count / info["raw_rows"])
    for name, info in quality.items()
    if isinstance(info, dict) and "missing_raw" in info
    for field, count in info["missing_raw"].items()
    if count
)
missing.columns = ["table", "field", "missing_rows", "missing_share"]
display(missing.nlargest(10, "missing_share"))
assert quality["passed"]
""",
        ),
        (
            "md",
            """Optional review comments account for substantial missingness. Scores and their timestamps govern the review analysis. Delivery eligibility depends on the three date fields and delivery status.

## How does the model preserve one row per order?

The CTEs aggregate payments and items before joining. ROW_NUMBER selects one review with deterministic tie-breaking. CASE WHEN defines an eligible delivery, compares calendar dates and assigns null lateness outside the cohort. Read the complete SQL and check the stored view.
""",
        ),
        (
            "code",
            '''print((ROOT / "sql/02_order_fact.sql").read_text())
with closing(sqlite3.connect(DB_URI, uri=True)) as connection:
    counts = pd.read_sql_query(
        """
        SELECT COUNT(*) AS rows, COUNT(DISTINCT order_id) AS orders
        FROM order_fact
    """,
        connection,
    )
assert counts.at[0, "rows"] == counts.at[0, "orders"]
display(counts)
model = json.loads((REPORTS / "model_validation.json").read_text())
assert model["passed"]
display(pd.DataFrame(model["money_reconciliation"]).T)
''',
        ),
        (
            "md",
            """The model retains 99,441 unique orders. Product price, freight and payment totals each reconcile within a cent. Treat the promised date as inclusive through the calendar day.

## Who enters the delivery denominator?
""",
        ),
        (
            "code",
            """exclusions_sql = (ROOT / "sql/08_audit.sql").read_text()
print(exclusions_sql)
with closing(sqlite3.connect(DB_URI, uri=True)) as connection:
    exclusions = pd.read_sql_query(exclusions_sql, connection)
display(exclusions)
""",
        ),
        (
            "md",
            """The eligibility audit retains 96,470 orders for delivery comparisons. Cancellations and other undelivered statuses remain visible in the wider order population. Next, compare the verified KPI and investigate where late deliveries are concentrated.
""",
        ),
        (
            "md",
            """[Previous](00_source_and_relational_schema.ipynb) · [Notebook guide](../README.md#notebook-guide) · [Next](02_delivery_and_satisfaction.ipynb)
""",
        ),
    ],
)

write(
    "02_delivery_and_satisfaction.ipynb",
    [
        (
            "md",
            """# 02 · Delivery KPIs and operational patterns

Use the verified order mart to measure reliability and locate the late-order burden across purchase cohorts and states. The following notebook connects these delivery outcomes to reviews.

[Previous](01_data_quality_and_sql.ipynb) · [Notebook guide](../README.md#notebook-guide) · [Next](03_reviews_and_sensitivity.ipynb)
""",
        ),
        (
            "code",
            """import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Image, display

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
assert (ROOT / "src/olist_analytics").is_dir(), (
    "Open from the project root or notebooks directory."
)
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"


DB = ROOT / "data/processed/olist.sqlite3"
DB_URI = DB.as_uri() + "?mode=ro"
""",
        ),
        (
            "md",
            """## What share of eligible deliveries missed the promised date?

Use the validated conditional aggregate and explicitly reconcile its denominator and saved export.
""",
        ),
        (
            "code",
            """kpis_sql = (ROOT / "sql/03_kpis.sql").read_text()
print(kpis_sql)
with closing(sqlite3.connect(DB_URI, uri=True)) as connection:
    kpis = pd.read_sql_query(kpis_sql, connection)
saved_kpis = pd.read_csv(TABLES / "kpis.csv")
pd.testing.assert_frame_equal(kpis, saved_kpis, check_dtype=False)
display(kpis[["total_orders", "eligible_delivered_orders", "late_orders", "late_rate"]])
""",
        ),
        (
            "md",
            """6,534 of 96,470 eligible orders arrived late (6.77%). Comparing time and geography requires keeping the number of orders at risk of being counted late alongside the rate.

## Does lateness vary across purchase cohorts?

Use the verified monthly view. Its rate panel applies the minimum of 200 eligible deliveries and its volume panel retains every cohort.
""",
        ),
        (
            "code",
            """display(Image(filename=str(REPORTS / "figures/01_monthly_reliability.png"), width=900))
""",
        ),
        (
            "md",
            """Read spikes with their cohort size and interval. The historical sample and partial edge periods limit comparisons across months.

## Which states have the highest counts and highest rates?

Use the same eligibility rule in every state. The rate screen requires at least 200 eligible orders. The chart highlights the 12 highest-volume states.
""",
        ),
        (
            "code",
            """states_sql = (ROOT / "sql/05_states.sql").read_text()
print(states_sql)
with closing(sqlite3.connect(DB_URI, uri=True)) as connection:
    states = pd.read_sql_query(states_sql, connection)
columns = ["customer_state", "eligible_orders", "late_orders", "late_rate"]
display(states.nlargest(3, "late_orders")[columns])
display(states.loc[states["eligible_orders"].ge(200)].nlargest(3, "late_rate")[columns])
assert np.isclose(states["late_orders"].sum(), kpis.at[0, "late_orders"])
display(Image(filename=str(REPORTS / "figures/02_state_reliability.png"), width=900))
""",
        ),
        (
            "md",
            """SP accounts for the highest late-order volume. AL leads the rate screen. Those are distinct operational priorities, and the chart’s volume selection may omit states with high rates.

## How do elapsed delivery times compare?
""",
        ),
        (
            "code",
            """display(Image(filename=str(REPORTS / "figures/05_delivery_time_ecdf.png"), width=900))
""",
        ),
        (
            "md",
            """The empirical cumulative distribution shows that the late group generally takes longer to receive orders. The calendar deadline depends on the promised date, so elapsed days alone cannot define lateness. Next, check whether customer feedback tells the same story.
""",
        ),
        (
            "md",
            """[Previous](01_data_quality_and_sql.ipynb) · [Notebook guide](../README.md#notebook-guide) · [Next](03_reviews_and_sensitivity.ipynb)
""",
        ),
    ],
)

write(
    "03_reviews_and_sensitivity.ipynb",
    [
        (
            "md",
            """# 03 · Review scores and timing sensitivity

Estimate the size of the association between late delivery and low reviews, then test what happens when responses must follow recorded delivery.

[Previous](02_delivery_and_satisfaction.ipynb) · [Notebook guide](../README.md#notebook-guide) · [Next](04_findings_and_recommendations.ipynb)
""",
        ),
        (
            "code",
            """import json
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Image, display
from olist_analytics.statistics import cluster_bootstrap_difference

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
assert (ROOT / "src/olist_analytics").is_dir(), (
    "Open from the project root or notebooks directory."
)
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"


DB = ROOT / "data/processed/olist.sqlite3"
DB_URI = DB.as_uri() + "?mode=ro"
""",
        ),
        (
            "md",
            """## How large is the low-score gap?

Read the relevant order-level columns once. Keep eligible deliveries with an observed chosen review. Score 1 or 2 counts as low. The table reports both the low-score count and the reviewed denominator.
""",
        ),
        (
            "code",
            '''with closing(sqlite3.connect(DB_URI, uri=True)) as connection:
    reviewed = pd.read_sql_query(
        """
        SELECT customer_unique_id, delivery_eligible, is_late, review_score,
               review_answered_after_delivery
        FROM order_fact
        WHERE delivery_eligible = 1 AND review_score IS NOT NULL
    """,
        connection,
    )

reviewed["low_score"] = reviewed["review_score"].le(2)
rates = reviewed.groupby("is_late")["low_score"].agg(
    reviewed_orders="size", low_scores="sum", low_score_rate="mean"
)
display(rates.rename(index={0: "On time", 1: "Late"}))
gap = rates.at[1, "low_score_rate"] - rates.at[0, "low_score_rate"]
print(f"Late minus on time {gap * 100:.2f} percentage points")
display(Image(filename=str(REPORTS / "figures/03_low_review_rates.png"), width=900))
''',
        ),
        (
            "md",
            """Low scores occur in 62.42% of late reviewed orders and 9.27% of on-time reviewed orders. The chart’s descriptive intervals compare rates. For the gap, resample customers to account for repeat orders within customers.

## How uncertain is the gap, and what do the ordinal scores show?

Use 2,000 seeded cluster resamples. Each draw keeps a customer’s orders together. The exploratory ordinal diagnostics use the earliest eligible reviewed order per customer. The percentile interval approximates sampling variability under this approach and leaves confounding and response selection unresolved.
""",
        ),
        (
            "code",
            """stats = json.loads((REPORTS / "statistics.json").read_text())
interval = cluster_bootstrap_difference(reviewed)
assert np.isclose(gap, stats["primary"]["risk_difference"])
np.testing.assert_allclose(
    [interval["lower"], interval["upper"]],
    [stats["risk_difference_ci"]["lower"], stats["risk_difference_ci"]["upper"]],
)
lower, upper = interval["lower"] * 100, interval["upper"] * 100
print(f"Customer-cluster 95% interval {lower:.2f} to {upper:.2f} points")
diagnostics = stats["independent_customer_diagnostics"]
display(
    pd.Series(
        {
            key: diagnostics[key]
            for key in ("cramers_v", "cliffs_delta_late_minus_on_time")
        }
    )
)
display(Image(filename=str(REPORTS / "figures/04_review_distribution.png"), width=900))
""",
        ),
        (
            "md",
            """The interval spans 51.88 to 54.36 percentage points. The ordinal distribution also shifts toward low scores in the late group. Order mix, seller, carrier and survey timing can all affect the observed association.

## Does the gap persist when reviews follow delivery?

Use on-or-after delivery timestamps to form a separate cohort. Recompute its gap and compare it with the saved timing and definition sensitivity scenarios.
""",
        ),
        (
            "code",
            """after_delivery = reviewed.loc[reviewed["review_answered_after_delivery"].eq(1)]
rates_after = after_delivery.groupby("is_late")["low_score"].mean()
gap_after = rates_after.loc[1] - rates_after.loc[0]
sensitivity = pd.read_csv(TABLES / "sensitivity.csv")
timing = sensitivity.loc[
    sensitivity["scenario"].eq("Review answered on/after actual delivery")
].iloc[0]
assert len(after_delivery) == timing["reviewed_orders"]
assert np.isclose(gap_after, timing["risk_difference"])
print(f"On or after delivery, {len(after_delivery):,} reviewed orders")
display(
    sensitivity[["scenario", "reviewed_orders", "risk_difference"]]
    .assign(risk_difference=lambda frame: frame["risk_difference"].mul(100))
    .rename(columns={"risk_difference": "gap_pp"})
)
display(Image(filename=str(REPORTS / "figures/06_sensitivity.png"), width=900))
""",
        ),
        (
            "md",
            """The gap drops from 53.15 to 10.19 percentage points. The restricted cohort excludes feedback submitted while customers were still waiting and changes the composition of the groups. These historical comparisons motivate a follow-up test of communication and delivery interventions.
""",
        ),
        (
            "md",
            """[Previous](02_delivery_and_satisfaction.ipynb) · [Notebook guide](../README.md#notebook-guide) · [Next](04_findings_and_recommendations.ipynb)
""",
        ),
    ],
)

write(
    "04_findings_and_recommendations.ipynb",
    [
        (
            "md",
            """# 04 · Findings and operational next steps

Bring together the validated delivery KPI, geographic priorities and review-timing result. Translate the historical estimates into checks an operations team can run before acting.

[Previous](03_reviews_and_sensitivity.ipynb) · [Notebook guide](../README.md#notebook-guide)
""",
        ),
        (
            "code",
            """from pathlib import Path

import pandas as pd
from IPython.display import display

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
assert (ROOT / "src/olist_analytics").is_dir(), (
    "Open from the project root or notebooks directory."
)
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"
""",
        ),
        (
            "md",
            """## Evidence for the decision

Put each headline estimate next to its denominator. The review gap compares late and on-time orders among orders with a selected score.
""",
        ),
        (
            "code",
            """kpis = pd.read_csv(TABLES / "kpis.csv").iloc[0]
sensitivity = pd.read_csv(TABLES / "sensitivity.csv").iloc[:2]
delivery = pd.DataFrame(
    {
        "metric": ["Late delivery share"],
        "eligible_orders": [int(kpis["eligible_delivered_orders"])],
        "late_orders": [int(kpis["late_orders"])],
        "rate_pct": [kpis["late_rate"] * 100],
    }
)
display(delivery.round(2))
display(
    sensitivity[["scenario", "reviewed_orders"]].assign(
        low_review_gap_pp=sensitivity["risk_difference"].mul(100).round(2)
    )
)
""",
        ),
        (
            "md",
            """## Recommended follow-up

- Start with SP for workload reduction and use high-rate states to investigate unusually unreliable routes. Compare seller, carrier and product mix before attributing the differences to operations.
- Split feedback reporting by whether customers had received their order. Monitor missing scores and timestamp completeness in each cohort.
- Pilot proactive deadline communication and specify comparison groups, review measurement dates and eligible orders in advance. Estimate impact prospectively.

The data describes the historical marketplace. Missing reviews, differing customer and order mix, and potentially imperfect timestamps limit generalization and attribution. The [analytical report](../reports/analytical_report.md) contains the original figures and findings.
""",
        ),
        (
            "md",
            """[Previous](03_reviews_and_sensitivity.ipynb) · [Notebook guide](../README.md#notebook-guide)
""",
        ),
    ],
)
