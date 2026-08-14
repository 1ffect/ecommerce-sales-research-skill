#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    product = plan.get("product", "")
    date_range = plan.get("date_range", "")
    currency = plan.get("currency", "")
    default_category = plan.get("category_filter", "")
    rows: list[dict[str, Any]] = []

    regions = plan.get("regions", [])
    platforms = plan.get("platforms", [])
    keywords_by_region = plan.get("keywords_by_region", {})
    category_filters = plan.get("category_filters", {})

    for region in regions:
        keywords = keywords_by_region.get(region, [])
        for platform in platforms:
            category = category_filters.get(region, category_filters.get(platform, default_category))
            for keyword in keywords:
                rows.append({
                    "产品": product,
                    "地区": region,
                    "平台": platform,
                    "关键词": keyword,
                    "时间段": date_range,
                    "币种": currency,
                    "类目筛选": category,
                    "建议文件夹": f"{region}-{product}/{keyword}",
                    "下载状态": "",
                    "备注": "",
                })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Excel query/download checklist for ecommerce sales research.")
    parser.add_argument("--plan", required=True, help="JSON plan with product, regions, platforms, date_range, and keywords_by_region.")
    parser.add_argument("--output", default="query_plan.xlsx", help="Output .xlsx path.")
    args = parser.parse_args()

    plan = load_json(Path(args.plan))
    rows = rows_from_plan(plan)
    if not rows:
        raise SystemExit("No query rows generated. Check regions, platforms, and keywords_by_region.")

    summary = pd.DataFrame([
        ["产品", plan.get("product", "")],
        ["地区", ", ".join(plan.get("regions", []))],
        ["平台", ", ".join(plan.get("platforms", []))],
        ["时间段", plan.get("date_range", "")],
        ["币种", plan.get("currency", "")],
        ["任务数", len(rows)],
        ["下载说明", "逐行在数据平台检索并导出 .xlsx，放入建议文件夹或同一研究目录。"],
    ], columns=["字段", "内容"])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="下载任务表", index=False)
        summary.to_excel(writer, sheet_name="任务概览", index=False)

    print(json.dumps({"rows": len(rows), "output": str(output.resolve())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
