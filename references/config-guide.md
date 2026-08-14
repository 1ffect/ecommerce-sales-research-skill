# Config Guide

Use a JSON config for each product/category/market combination. Without a config, the script only merges, dedupes, and summarizes so it will not accidentally remove valid products from an unfamiliar category.

Generic example:

```json
{
  "product_name": "便携式投影仪",
  "low_price_cny": 120,
  "target_terms": ["projector", "portable projector", "mini projector", "投影仪", "โปรเจคเตอร์"],
  "exclude_terms": ["screen", "stand", "tripod", "remote control", "lamp", "幕布", "支架", "遥控器"],
  "required_term_groups": [
    {
      "name": "产品形态",
      "terms": ["projector", "投影仪", "โปรเจคเตอร์"]
    }
  ],
  "accessory_terms": ["screen", "stand", "tripod", "case", "bag", "remote", "幕布", "支架", "收纳包"]
}
```

Fields:

- `product_name`: appears in the output summary and rule sheet.
- `low_price_cny`: optional. Product-level median price below this value is removed. Use `null` or omit when unsure.
- `target_terms`: optional broad target words. If `required_term_groups` is empty, a product must match at least one target term.
- `exclude_terms`: optional hard negative words. If matched, the product is removed.
- `required_term_groups`: optional list of named term groups. A product must match at least one term in every group. Use this for stricter definitions such as "audience + product form + core function".
- `accessory_terms`: optional words that indicate accessories, consumables, parts, or non-main-unit products.
- `adult_or_generic_terms`: optional words for likely adult/generic products; these only remove a product when no strong function term is present.
- `audience_terms`, `form_terms`, `function_terms`: backward-compatible shortcut fields. If present and `required_term_groups` is absent, they are treated as required groups named target audience, product form, and core function.
- `required_columns`: optional list of required input columns. By default, the script requires `商品标题`, `商品链接`, and `时间`.

Recommended process:

1. Before download, create a first-pass config from the product definition and planned keywords.
2. Run once without a config if the category is unfamiliar or high-risk.
3. Open high-sales products in `清洗后商品汇总` or `原始去重后月度`.
4. Add a config with only obvious target/exclude terms.
5. Open `待人工复核Top商品` first. Fill `人工判断` and `人工备注` for the highest-impact rows.
6. Open `剔除商品` and check high-sales removed products when more detail is needed.
7. Add stricter required groups only after reviewing false positives.
8. Keep the config in the research folder so future runs are reproducible.

Manual review mode:

- Use `--review-top-n 50` for normal projects.
- Increase to `100` or `200` for messy categories with many accessories, bundles, refurbished items, or ambiguous local names.
- Prioritize rows with high `复核优先级`; they are usually high-sales removals, target/exclude conflicts, low-price boundary products, or near-misses against required term groups.
- Use the `人工判断` column for quick labels such as `保留`, `剔除`, `待确认`, then update `config.json` and rerun.

Query planning checklist:

```text
product:
regions:
platforms:
date_range:
currency:
keywords_by_region:
category_filters:
download_folder:
notes_for_manual_download:
```

Child smartwatch style example:

```json
{
  "product_name": "儿童智能手表",
  "low_price_cny": 50,
  "required_term_groups": [
    {
      "name": "儿童/学生",
      "terms": ["kid", "kids", "child", "children", "student", "儿童", "เด็ก", "tre em", "kanak"]
    },
    {
      "name": "手表形态",
      "terms": ["watch", "smartwatch", "smart watch", "手表", "นาฬิกา", "dong ho"]
    },
    {
      "name": "智能功能",
      "terms": ["gps", "location", "sim", "call", "sos", "video", "camera", "定位", "通话"]
    }
  ],
  "accessory_terms": ["strap", "band", "charger", "cable", "protector", "film", "case", "battery", "表带", "贴膜"]
}
```
