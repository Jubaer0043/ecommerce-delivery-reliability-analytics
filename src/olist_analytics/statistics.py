"""Effect sizes and uncertainty; inference describes association, not causality."""
import numpy as np
import pandas as pd
from scipy import stats


def wilson_interval(successes, totals, confidence: float = 0.95):
    """Wilson score interval; zero denominators yield NaN, never a zero rate."""
    k, n = np.broadcast_arrays(np.asarray(successes, dtype=float), np.asarray(totals, dtype=float))
    if np.any(k < 0) or np.any(n < 0) or np.any(k > n):
        raise ValueError("Expected 0 <= successes <= totals")
    z = stats.norm.ppf((1 + confidence) / 2)
    p = np.divide(k, n, out=np.full_like(k, np.nan), where=n > 0)
    safe_n = np.where(n > 0, n, np.nan)
    center = (p + z*z / (2*safe_n)) / (1 + z*z / safe_n)
    half = z * np.sqrt(p*(1-p)/safe_n + z*z/(4*safe_n**2)) / (1 + z*z/safe_n)
    return np.maximum(0, center-half), np.minimum(1, center+half)


def association(frame: pd.DataFrame) -> dict:
    cohort = frame.loc[frame.delivery_eligible.eq(1) & frame.review_score.notna()]
    late = cohort.loc[cohort.is_late.eq(1), "review_score"]
    on_time = cohort.loc[cohort.is_late.eq(0), "review_score"]
    if late.empty or on_time.empty:
        raise ValueError("Association requires reviewed orders in both delivery groups")
    late_low, on_low = int(late.le(2).sum()), int(on_time.le(2).sum())
    p_late, p_on = late_low / len(late), on_low / len(on_time)
    return {
        "reviewed_orders": len(cohort), "late_reviewed_orders": len(late),
        "on_time_reviewed_orders": len(on_time), "late_low_review_orders": late_low,
        "on_time_low_review_orders": on_low,
        "late_low_review_rate": p_late, "on_time_low_review_rate": p_on,
        "risk_difference": p_late-p_on,
        "risk_ratio": p_late/p_on if p_on > 0 else None,
        "late_mean_score": float(late.mean()), "on_time_mean_score": float(on_time.mean()),
        "late_median_score": float(late.median()), "on_time_median_score": float(on_time.median()),
    }


def cluster_bootstrap_difference(frame: pd.DataFrame, repetitions: int = 2000, seed: int = 42) -> dict:
    """Resample customer_unique_id clusters, retaining all orders in each sampled cluster."""
    cohort = frame.loc[frame.delivery_eligible.eq(1) & frame.review_score.notna()].copy()
    if cohort.customer_unique_id.isna().any():
        raise ValueError("Missing customer cluster identifier")
    late, low = cohort.is_late.eq(1), cohort.review_score.le(2)
    cohort["n_late"], cohort["low_late"] = late.astype(int), (late & low).astype(int)
    cohort["n_on"], cohort["low_on"] = (~late).astype(int), (~late & low).astype(int)
    values = cohort.groupby("customer_unique_id")[["n_late", "low_late", "n_on", "low_on"]].sum().to_numpy()
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repetitions):
        n_late, low_late, n_on, low_on = values[rng.integers(0, len(values), size=len(values))].sum(axis=0)
        if n_late and n_on:
            estimates.append(low_late/n_late - low_on/n_on)
    if len(estimates) < repetitions * 0.95:
        raise ValueError("Too many bootstrap replicates lack a delivery group")
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return {"method": "Customer cluster percentile bootstrap, 95% CI",
            "customer_clusters": len(values), "repetitions": repetitions,
            "valid_repetitions": len(estimates), "seed": seed,
            "lower": float(lower), "upper": float(upper)}


def independent_customer_diagnostics(frame: pd.DataFrame) -> dict:
    """Use earliest eligible reviewed order per customer to reduce repeated-customer dependence."""
    cohort = frame.loc[frame.delivery_eligible.eq(1) & frame.review_score.notna()].copy()
    cohort = cohort.sort_values(["order_purchase_timestamp", "order_id"]).drop_duplicates("customer_unique_id")
    effect = association(cohort)
    late = cohort.loc[cohort.is_late.eq(1), "review_score"].to_numpy()
    on_time = cohort.loc[cohort.is_late.eq(0), "review_score"].to_numpy()
    contingency = np.array([[effect["late_low_review_orders"], len(late)-effect["late_low_review_orders"]],
                            [effect["on_time_low_review_orders"], len(on_time)-effect["on_time_low_review_orders"]]])
    chi2, p_chi, _, expected = stats.chi2_contingency(contingency, correction=False)
    mw = stats.mannwhitneyu(late, on_time, alternative="two-sided", method="asymptotic")
    return {**effect, "sample_rule": "Earliest eligible reviewed order per customer_unique_id",
            "chi_square": float(chi2), "chi_square_p": float(p_chi),
            "chi_square_min_expected_cell": float(expected.min()),
            "cramers_v": float(np.sqrt(chi2/len(cohort))),
            "mann_whitney_u": float(mw.statistic), "mann_whitney_p": float(mw.pvalue),
            "cliffs_delta_late_minus_on_time": float(2*mw.statistic/(len(late)*len(on_time))-1)}
