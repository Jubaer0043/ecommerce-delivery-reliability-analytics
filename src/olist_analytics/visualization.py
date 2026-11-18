"""Publication-style charts with explicit cohorts, denominators, and scales."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter
import numpy as np
import pandas as pd
import seaborn as sns

from .analysis import read_fact
from .config import REPORTS

BLUE, ORANGE = "#2166AC", "#B35806"


def save(fig, name):
    fig.savefig(REPORTS / "figures" / f"{name}.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_figures() -> list[str]:
    (REPORTS / "figures").mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans"})
    tables = REPORTS / "tables"
    monthly = pd.read_csv(tables / "monthly.csv")
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    x = np.arange(len(monthly))
    # Tiny cohorts remain in CSVs and the volume panel; suppress their unstable rate estimates here.
    enough = monthly.eligible_orders.ge(200)
    axes[0].plot(x, monthly.late_rate.where(enough), color=ORANGE, marker="o", markersize=4)
    axes[0].fill_between(x, monthly.late_rate_ci_low.where(enough), monthly.late_rate_ci_high.where(enough), color=ORANGE, alpha=.18)
    axes[0].set(ylabel="Late delivery rate", title="Delivery reliability by purchase month")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_ylim(bottom=0)
    axes[1].bar(x, monthly.eligible_orders, color=BLUE)
    axes[1].set(ylabel="Eligible orders", xlabel="Purchase month")
    axes[1].set_xticks(x[::2], monthly.purchase_month.iloc[::2], rotation=45, ha="right")
    fig.text(.06, .01, "Rates shown for months with n ≥ 200; shading: pointwise Wilson 95% intervals. All cohort volumes retained below.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    save(fig, "01_monthly_reliability")

    states = pd.read_csv(tables / "states.csv").query("eligible_orders >= 200").nlargest(12, "eligible_orders").sort_values("late_rate")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(np.arange(len(states)), states.late_rate, color=BLUE, alpha=.85)
    ax.errorbar(states.late_rate, np.arange(len(states)),
        xerr=np.vstack([states.late_rate-states.late_rate_ci_low, states.late_rate_ci_high-states.late_rate]),
        fmt="none", ecolor="#333333", capsize=3)
    ax.set_yticks(np.arange(len(states)), [f"{r.customer_state}  (n={r.eligible_orders:,})" for r in states.itertuples()])
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set(xlabel="Late delivery rate · Wilson 95% interval", title="Late deliveries in the 12 highest-volume customer states")
    fig.text(.05, .01, "Eligible delivered orders; minimum 200 per state. Descriptive comparison, unadjusted for order mix.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    save(fig, "02_state_reliability")

    review = pd.read_csv(tables / "reviews.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(review.delivery_group, review.low_review_rate, color=[BLUE, ORANGE], width=.55)
    ax.errorbar(np.arange(len(review)), review.low_review_rate,
        yerr=np.vstack([review.low_review_rate-review.low_rate_ci_low, review.low_rate_ci_high-review.low_review_rate]),
        fmt="none", color="#222222", capsize=5)
    for bar, row in zip(bars, review.itertuples()):
        ax.text(bar.get_x()+bar.get_width()/2, row.low_review_rate+.04,
                f"{row.low_review_rate:.1%}\nn={row.reviewed_orders:,}", ha="center", fontsize=11)
    ax.set(ylim=(0, 1), ylabel="Share of reviewed orders scoring 1–2", title="Low review scores are more frequent among late orders")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.text(.04, .01, "Eligible reviewed orders; order-level Wilson intervals. Customer-cluster CI for the difference is in the report.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    save(fig, "03_low_review_rates")

    fact = read_fact()
    eligible = fact.loc[fact.delivery_eligible.eq(1)].copy()
    reviewed = eligible.loc[eligible.review_score.notna()].copy()
    labels = ["On time / early", "1–3 days late", "4–7 days late", "8–14 days late", "15+ days late"]
    reviewed["delay_band"] = pd.cut(reviewed.signed_delay_days, [-np.inf, 0, 3, 7, 14, np.inf], labels=labels)
    distribution = pd.crosstab(reviewed.delay_band, reviewed.review_score).reindex(index=labels, columns=[1,2,3,4,5], fill_value=0)
    normalized = distribution.div(distribution.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(11, 6))
    normalized.plot.bar(stacked=True, ax=ax, color=["#A6611A", "#DFC27D", "#EEEEEE", "#80CDC1", "#018571"], width=.7)
    ax.set_xticklabels([f"{label}\n(n={int(n):,})" for label,n in zip(labels, distribution.sum(axis=1))], rotation=0, fontsize=9)
    ax.set(xlabel="Delay beyond estimated calendar date", ylabel="Review-score composition", title="Review-score distribution across delivery-delay bands", ylim=(0,1))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.legend(title="Review score", bbox_to_anchor=(1.01,1), loc="upper left")
    fig.text(.05, .01, "Eligible reviewed orders; one latest answered review per order. Association does not establish causation.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    save(fig, "04_review_distribution")
    distribution.to_csv(tables / "review_delay_bands.csv", index_label="delay_band")

    fig, ax = plt.subplots(figsize=(10, 5))
    eligible["delivery_group"] = np.where(eligible.is_late.eq(1), "Late", "On time")
    sns.ecdfplot(data=eligible, x="delivery_days", hue="delivery_group", hue_order=["On time", "Late"], palette=[BLUE, ORANGE], ax=ax)
    ax.get_legend().set_title("Delivery outcome")
    ax.set(xlabel="Elapsed days from purchase to delivery", ylabel="Cumulative proportion", title="Delivery time distribution · full observed range", xlim=(0, eligible.delivery_days.max()))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.text(.05, .01, "Eligible delivered orders; no outliers removed. Timestamps have no documented timezone.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    save(fig, "05_delivery_time_ecdf")

    sensitivity = pd.read_csv(tables / "sensitivity.csv")
    short_labels = ["Primary: all review timings", "Reviews answered after delivery", "Exclude carrier date anomalies",
                    "One order per customer", "Strict timestamp deadline", "Earliest review per order"]
    fig, ax = plt.subplots(figsize=(11, 6))
    positions = np.arange(len(sensitivity))
    ax.barh(positions, sensitivity.risk_difference, color=[ORANGE, BLUE, BLUE, BLUE, BLUE, BLUE])
    ax.set_yticks(positions, short_labels)
    for pos, row in zip(positions, sensitivity.itertuples()):
        ax.text(row.risk_difference+.01, pos, f"{100*row.risk_difference:.1f} pp", va="center", fontsize=10)
    ax.invert_yaxis()
    ax.set(xlim=(0,.65), xlabel="Late minus on-time low-review rate · percentage points", title="Review timing changes the size of the association")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{100*value:.0f}"))
    fig.text(.04, .01, "Descriptive effects across different cohorts; no causal interpretation. Full definitions and denominators: sensitivity.csv.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    save(fig, "06_sensitivity")
    return [path.name for path in sorted((REPORTS / "figures").glob("*.png"))]
