---
name: ecommerce-sales-research
description: Plan and process ecommerce product sales research across regions and platforms. Use when a user gives a product/category and needs localized marketplace keywords, a region/platform/date query plan for Amazon, Shopee, TikTok Shop, Lazada, or similar ecommerce sales platforms, manual-download instructions, then .xlsx merging, dedupe, cleaning, and analysis.
---

# Ecommerce Sales Research

## End-To-End Flow

Use this end-to-end flow when the user wants to research ecommerce sales for a product/category across one or more regions and platforms.

1. Collect the research brief from the user:
   - product/category;
   - target regions/countries;
   - target platforms, such as Amazon, Shopee, TikTok Shop, Lazada, or another analytics platform;
   - time period;
   - currency and reporting grain, such as monthly item-level sales.
2. Generate localized keywords:
   - include local-language product names;
   - include English marketplace terms;
   - include common aliases, abbreviations, singular/plural variants, and feature-led phrases;
   - keep the list broad enough for recall, then rely on cleaning rules to remove noise.
3. Ask the user to confirm target platforms when unspecified. If the user gives multiple platforms, plan queries for all selected platforms.
4. Create a query/download plan:
   - one row per region/platform/keyword/date-range combination;
   - include suggested category filters when known;
   - include a destination folder and expected filename pattern;
   - optionally generate `query_plan.xlsx` with `scripts/create_query_plan.py`.
5. Prefer manual authenticated download:
   - the user logs into the data platform;
   - the user runs each query and exports `.xlsx`;
   - the user places exports in the planned folder.
   This is the default because login, CAPTCHA, permissions, session expiry, and UI changes are fragile.
6. Use browser-assisted download only as an optional enhancement:
   - require an already logged-in browser session;
   - do not store credentials;
   - automate only visible, user-authorized clicks and downloads.
7. Run the first merge:
   - if the product/category is new or uncertain, run without `config.json` first;
   - merge all exports, dedupe by `商品链接 + 时间`, and produce product/monthly summaries without removing products.
8. Create or tune `config.json`:
   - define target terms, required term groups, exclude terms, accessory/non-main-unit terms, and optional low-price thresholds;
   - keep rules conservative for unfamiliar categories;
   - save config in the research folder for reproducibility.
9. Run configured cleaning with `scripts/merge_clean_sales.py`.
10. Calibrate rules using `待人工复核Top商品`:
   - ask the user to review only the highest-impact rows;
   - use `人工判断` values such as `保留`, `剔除`, or `待确认`;
   - update `config.json` and rerun until the rule quality is acceptable.
11. Produce the analysis:
   - platform and region sales comparisons;
   - top products, brands, and stores;
   - price bands;
   - monthly trends;
   - keyword overlap and duplicate coverage;
   - notable growth or decline signals.

Responsibility split:

- Codex: keyword planning, query checklist, folder structure, merge/dedupe, rule drafting, calibration workbook, cleaning, and analysis.
- User: authenticated platform login/download, plus quick review of `待人工复核Top商品` for category-specific judgment.

## Workflow

Use this skill for recurring marketplace research where a user starts from a product/category and needs regional marketplace sales data. Keep the skill product-agnostic: infer or request a per-research config instead of hardcoding one category, country, language, or platform.

1. Confirm the product/category, target regions, target platforms, time period, currency, and whether the user already has exports.
2. If regions are known but keywords are not, propose localized marketplace keywords for each region. Include local language names, English shopping terms, common abbreviations, and product-function variants where useful.
3. Ask which platforms to query, unless the user already specified them. Support one or more of Amazon, Shopee, TikTok Shop, Lazada, or the user's analytics platform.
4. Create a query checklist with one row per region/platform/keyword/date-range combination. Include a suggested destination folder.
5. Prefer manual authenticated download: the user logs in, searches each query, exports `.xlsx`, and places files in the destination folder. This is the default because login, CAPTCHA, session expiry, and platform UI changes are fragile.
6. Offer browser-assisted collection only when the user explicitly wants it and is already logged in. Do not store account credentials in the skill; only automate visible, user-authorized clicks/downloads.
7. Inspect one raw `.xlsx` and any prior `outputs/` workbook before changing rules.
8. Use `scripts/merge_clean_sales.py` for deterministic merge, dedupe, optional product classification, and workbook output.
9. Tune product terms and thresholds in a config file for each product/category/market combination.
10. Review `待人工复核Top商品` first, then `清洗规则`, `清洗汇总`, `剔除商品`, and top rows of `清洗后商品汇总` before treating the result as final.

## Keyword And Query Planning

When the user gives only a product/category, produce:

- `产品定义`: what is in-scope and out-of-scope.
- `地区关键词`: 5-12 keywords per region where possible, mixing local language, English marketplace terms, common aliases, singular/plural, and high-intent function phrases.
- `平台选择问题`: ask the user to choose Amazon, Shopee, TikTok Shop, Lazada, or another platform when unspecified.
- `下载任务表`: region, platform, keyword, date range, category filter if known, expected filename/folder.
- `清洗初始规则`: conservative target terms, exclude terms, accessory terms, and uncertain points to review after the first merge.

If precise local keyword habits matter and internet access is available, verify keyword variants with web search or marketplace/autocomplete evidence before finalizing the query plan. If browsing is unavailable, clearly label the keyword list as a first-pass suggestion to validate during search.

Use this folder pattern unless the user gives another one:

```text
<region>-<product>/
  query_plan.xlsx
  config.json
  <keyword-1>/
    raw exports...
  <keyword-2>/
    raw exports...
  outputs/
```

To turn a planned keyword set into an Excel download checklist, create a small JSON plan and run:

```bash
python3 /path/to/skills/ecommerce-sales-research/scripts/create_query_plan.py \
  --plan query_plan.json \
  --output query_plan.xlsx
```

## Default Dedupe And Classification Rules

- Dedupe monthly rows by `商品链接 + 时间`.
- When duplicate monthly rows exist across keyword exports, keep the row with higher `销售额`, then higher `销量`, then earlier source order.
- Track all `搜索词`, `来源文件`, and `重复来源行数` so keyword overlap remains auditable.
- Build product-level rows by grouping on `商品链接`.
- With no config, keep all deduped products and output an auditable merged workbook. This is the safest default for a new product.
- With a config, classify products using `target_terms`, `exclude_terms`, `required_term_groups`, `accessory_terms`, and `low_price_cny`.
- Remove low-price outliers only when `low_price_cny` is configured.
- Do not rely on marketplace category alone. Keep categories as evidence, but classify primarily from product title and product-level signals.
- Always output `待人工复核Top商品` for calibration. This sheet ranks the highest-impact rows to review, prioritizing high-sales removed products, target/exclude term conflicts, low-price boundary cases, and products that miss only one required term group.

## Quick Start

After the user has downloaded exports, run from the research folder:

```bash
python3 /path/to/skills/ecommerce-sales-research/scripts/merge_clean_sales.py \
  --input . \
  --output outputs/cleaned_sales.xlsx \
  --product-name "本次调研产品" \
  --review-top-n 50
```

For real cleaning beyond dedupe, create a JSON config and pass `--config config.json`. See `references/config-guide.md`.

## Expected Input

Raw `.xlsx` exports should contain most of these columns:

`时间`, `商品标题`, `商品链接`, `销售额`, `销量`, `品牌`, `店铺名`, `1级类目名`, `2级类目名`, `3级类目名`, `4级类目名`, `叶子类目名`, `价格`, `上架时间`, `销售额同比`, `销售额环比`

The script skips files under `outputs/` by default so previous cleaned workbooks are not re-ingested.

## Outputs

The generated workbook contains:

- `清洗汇总`: source counts, retained/removed counts, sales totals.
- `清洗规则`: applied dedupe and classification rules.
- `待人工复核Top商品`: highest-impact products to manually check before finalizing rules.
- `清洗后商品汇总`: retained product-level rows sorted by sales.
- `清洗后月度明细`: retained monthly rows after dedupe.
- `剔除商品`: removed product-level rows with reasons.
- `剔除月度明细`: monthly rows belonging to removed products.
- `原始去重后月度`: all deduped monthly rows before product classification.

## Resources

- `scripts/merge_clean_sales.py`: reusable cleaner for marketplace `.xlsx` exports.
- `scripts/create_query_plan.py`: creates an Excel checklist for manual platform searches/downloads.
- `references/config-guide.md`: config fields and examples for adapting terms by market and product.
