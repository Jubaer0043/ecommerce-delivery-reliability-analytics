# Dataset provenance and acquisition contract

| Field | Value |
| --- | --- |
| Title | Brazilian E-Commerce Public Dataset by Olist |
| Publisher | Olist |
| Official landing page | https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce |
| Download endpoint (GET) | https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce |
| License on the official data card | CC BY-NC-SA 4.0 |
| License text | https://creativecommons.org/licenses/by-nc-sa/4.0/ |
| Source identity / acquisition time | `reports/source_manifest.json` |
| Download size and data coverage | Validate against the actual artifact; do not infer a version from third-party row counts |

The source describes real, anonymized commercial marketplace data. Approximate coverage described by the publisher is 2016–2018. The project's exact observed purchase-date range is calculated from the downloaded orders and recorded in the analytical report. It is not assumed that every source order was fulfilled or received a review.

The verified public GET endpoint succeeded without credentials in this execution. An HTTP HEAD response alone is not a download test: the endpoint returned 404 for HEAD while GET returned a valid archive. If access changes, download manually through the official landing page and pass the archive using `--archive`.

Expected original members:

```text
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

The acquisition gate checks member names, duplicate members, extracted size, ZIP CRCs, and SHA-256 hashes. Extraction copies only expected files, refusing conflicting existing raw content. Every downstream stage verifies original hashes. Raw files are not cleaned, edited, renamed, re-encoded, or committed. Source zip prefixes remain strings, preserving leading zeros.

`data_quality.json` records observed rows, missingness, duplicate handling, invalid date/numeric counts, primary-key checks, and foreign-key coverage. These observed counts come from execution rather than source-card approximations. `source_manifest.json` preserves the first acquisition time on rerun and does not claim an unverified Kaggle version number.

Only aggregate tables, charts, audit metadata, and aggregate notebook outputs are included in Git. No customer identifiers or raw review text are displayed in committed analytical outputs.
