# Methodology, assumptions, and limitations

## Analytical unit and join strategy

The business unit is an order. Aggregate item rows and payment rows independently by `order_id`, and select one review per order, before joining. Joining all three source tables directly creates a many-to-many multiplication. The model uses a left join for optional item/payment/review data and a validated customer join. Every order remains present exactly once.

All original files are byte-preserved. SHA-256 checks precede and follow analysis. The SQL database and report artifacts are disposable derivatives; rebuilding them does not edit originals.

## Missing data and duplicates

| Situation | Policy | Rationale |
| --- | --- | --- |
| Exact duplicate source row | Remove from cleaned copy; report count | Prevent repeated identical records without editing source |
| Conflicting known primary key | Stop the pipeline | Do not arbitrarily select a record |
| Multiple review records per order | Select latest answer, then creation time, review ID, score, title, message in descending deterministic order | Preserve order grain; check earliest selection separately |
| Repeated `review_id` | Do not deduplicate on review ID | Source does not support global uniqueness |
| Multiple coordinates per zip prefix | Preserve distinct points; do not join them to orders | Avoid geographic join expansion and inferred route precision |
| Missing actual delivery date | Exclude from delivery outcomes; retain in orders and cohort audit | Missingness cannot be interpreted as on time or late |
| Missing review score / no review record | Exclude only from score comparisons; report coverage | No score imputation or assumed neutrality |
| Missing review title/message | Preserve | Optional text is not required for numeric satisfaction analysis |
| Missing product category | Retain; category context uses `Unknown` | Avoid discarding valid orders |
| Missing English category translation | Fall back to original Portuguese category | Do not fabricate a translation |
| Missing numeric product metadata | Preserve | Not required for core delivery outcomes |
| Invalid nonblank date or numeric value | Stop with audit evidence | Silent coercion could conceal source issues |
| Negative or missing monetary value | Stop for item prices/freight/payments | Require review of source contract |
| Valid extreme duration/value | Retain and summarize percentiles/full range | Do not remove observations merely for being inconvenient |

## Metric definitions

1. **Eligible delivered order:** status `delivered`, observed purchase, actual, and estimated timestamps, actual delivery not before purchase, and estimated calendar date not before purchase date.
2. **Late delivery:** actual **calendar date** strictly after estimated calendar date. The estimated date is treated as an inclusive end-of-day promise because recorded estimates use midnight. Timestamp deadlines are a sensitivity, not the primary rule.
3. **Late rate:** late orders / eligible delivered orders. **On-time rate:** 1 − late rate. Cancellation, non-delivery, and missingness are not included as on time.
4. **Delivery time:** actual timestamp − purchase timestamp in fractional elapsed days. These are not business days.
5. **Low-score rate:** observed selected scores 1 or 2 / observed selected scores 1–5 in the given eligible cohort.
6. **Primary association:** late-group low-score rate − on-time-group low-score rate. Also report a descriptive risk ratio, means, medians, and score distributions. "Risk" here refers to the probability of an observed low score in a selected cohort, not a causal or predictive estimate.
7. **Review coverage:** reviewed eligible orders / all eligible orders in each delivery group.
8. **Monetary totals:** item prices, freight, and payments are separately reconciled, not assumed equal. SQL `REAL` is approximate; comparisons tolerate less than BRL 0.01. These are analytical amounts, not an accounting ledger.

Canceled/unavailable/other statuses remain in status summaries, not delivery KPIs. Carrier chronology flags do not exclude otherwise valid primary delivery outcomes because the core measurement is purchase-to-customer delivery; they are separately audited and excluded in a sensitivity.

## Statistical analysis

The primary effect uses all eligible reviewed orders. Customers may have multiple orders, so its 95% percentile bootstrap interval resamples unique `customer_unique_id` clusters, retaining all orders in each sampled cluster: 2,000 resamples and NumPy seed 42. It describes customer-level resampling uncertainty under an independence assumption between customers. This does not account for correlated operational shocks, missingness mechanisms, or confounding. The dataset is not claimed to be a random sample of a larger market.

Wilson score intervals accompany descriptive binomial rates. Zero denominators remain undefined rather than becoming zero percent. Chart Wilson intervals are pointwise, order-level approximations; use the customer-cluster interval for the primary rate difference. Segment comparisons are descriptive; no multiple-comparison significance ranking is performed. Monthly rate plots require n ≥ 200, state plots show the 12 highest-volume states with n ≥ 200, and the full CSVs retain small cohorts. This display threshold is not a formal power calculation.

As exploratory diagnostics, use the earliest eligible reviewed order per customer for Pearson chi-square (lateness × low-score indicator) and a two-sided asymptotic Mann–Whitney U comparison of score distributions. Report expected cell sizes, Cramér's V, and Cliff's delta. Scores are ordinal; a Mann–Whitney result does not establish a difference in medians without distributional assumptions. Computed p-values that underflow to zero are explicitly described as very small, not mathematically zero. No diagnostic test identifies a causal effect.

## Sensitivity definitions

| Scenario | Change |
| --- | --- |
| Primary | Latest answered review, full eligible reviewed cohort, inclusive estimated calendar date |
| Post-delivery answers | Require selected answer timestamp ≥ recorded actual delivery timestamp; not the same as requiring survey creation after delivery |
| Carrier anomalies removed | Exclude actual delivery before carrier handoff and carrier handoff before purchase |
| One order per customer | Earliest eligible reviewed purchase per `customer_unique_id`; tie on order ID |
| Timestamp deadline | Compare complete actual and estimated timestamps rather than dates |
| Earliest review | Select earliest answered review, with deterministic ascending tie-breaks |

Sensitivity rows are descriptive effects with their own denominators. The primary CI is not transferred to a restricted cohort. Restricting to post-delivery answers changes the selected population and the interpretation of dissatisfaction. It is not a correction that eliminates bias. Survey timing is central because people can answer while waiting for an overdue order.

## Interpretation boundaries

This historical Olist snapshot does not represent all Brazilian e-commerce, today's business, or a randomized intervention. Purchase-month cohorts may be affected by incomplete edge months and fulfillment censoring. State and category comparisons are unadjusted for distance, season, seller mix, and other recorded/unrecorded factors. An order can have multiple items and sellers; a whole-order review cannot attribute responsibility to one seller or category. Category rows overlap.

Timezone is undocumented; all timestamps are assumed to use one consistent clock. No holiday calendar, route distance, delivery carrier identity, loss estimates, or projected financial impact is inferred. Missing reviews and differences in survey timing can change the observed association. Recommendations are operational hypotheses to investigate or test prospectively.
