#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CONFIG: dict[str, Any] = {
    "product_name": "目标商品",
    "low_price_cny": None,
    "target_terms": [],
    "exclude_terms": [],
    "required_term_groups": [],
    "accessory_terms": [],
    "adult_or_generic_terms": [],
    "required_columns": ["商品标题", "商品链接", "时间"],
}

CATEGORY_COLUMNS = ["1级类目名", "2级类目名", "3级类目名", "4级类目名", "叶子类目名"]
NUMERIC_COLUMNS = ["销售额", "销量", "价格"]


def load_config(path: Path | None) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if path:
        user_config = json.loads(path.read_text(encoding="utf-8"))
        for key, value in user_config.items():
            config[key] = value
    return config


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, terms: list[str]) -> bool:
    text_norm = normalize_text(text)
    return any(normalize_text(term) in text_norm for term in terms if str(term).strip())


def matched_terms(text: str, terms: list[str], limit: int = 12) -> list[str]:
    text_norm = normalize_text(text)
    matches: list[str] = []
    seen: set[str] = set()
    for term in terms:
        term_norm = normalize_text(term)
        if term_norm and term_norm in text_norm and term not in seen:
            matches.append(term)
            seen.add(term)
        if len(matches) >= limit:
            break
    return matches


def configured_terms(config: dict[str, Any], key: str) -> list[str]:
    return [str(item) for item in config.get(key, []) if str(item).strip()]


def configured_groups(config: dict[str, Any]) -> list[dict[str, Any]]:
    groups = config.get("required_term_groups", [])
    if groups:
        normalized_groups = []
        for index, group in enumerate(groups, start=1):
            if isinstance(group, dict):
                name = group.get("name") or f"必需词组{index}"
                terms = group.get("terms", [])
            else:
                name = f"必需词组{index}"
                terms = group
            terms = [str(term) for term in terms if str(term).strip()]
            if terms:
                normalized_groups.append({"name": name, "terms": terms})
        return normalized_groups

    legacy_groups = [
        ("目标人群", configured_terms(config, "audience_terms")),
        ("产品形态", configured_terms(config, "form_terms")),
        ("核心功能", configured_terms(config, "function_terms")),
    ]
    return [{"name": name, "terms": terms} for name, terms in legacy_groups if terms]


def first_nonempty(values: pd.Series) -> Any:
    for value in values:
        if pd.notna(value) and str(value).strip():
            return value
    return ""


def join_unique(values: pd.Series, limit: int | None = None) -> str:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        output.append(text)
        seen.add(text)
    if limit is not None:
        output = output[:limit]
    return " | ".join(output)


def source_platform(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("shopee"):
        return "Shopee"
    if name.startswith("tiktok"):
        return "TikTok"
    if "lazada" in name:
        return "Lazada"
    if name.startswith("amazon") or "amazon" in name:
        return "Amazon"
    return "Unknown"


def product_id(url: Any) -> str:
    text = str(url or "")
    match = re.search(r"/product/(\d+)", text)
    if match:
        return f"tiktok_{match.group(1)}"
    match = re.search(r"L-i\.(\d+)\.(\d+)", text)
    if match:
        return f"shopee_{match.group(1)}_{match.group(2)}"
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{8,14})", text, re.I)
    if match:
        return f"amazon_{match.group(1).upper()}"
    return text


def find_input_files(input_paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_path in input_paths:
        if input_path.is_file() and input_path.suffix.lower() in {".xlsx", ".xls"}:
            files.append(input_path)
        elif input_path.is_dir():
            files.extend(
                p for p in input_path.rglob("*.xlsx")
                if "outputs" not in {part.lower() for part in p.parts}
                and not p.name.startswith("~$")
            )
            files.extend(
                p for p in input_path.rglob("*.xls")
                if "outputs" not in {part.lower() for part in p.parts}
                and not p.name.startswith("~$")
            )
    return sorted(set(files))


def validate_columns(frame: pd.DataFrame, required: list[str], source: Path) -> None:
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise ValueError(f"{source} missing required columns: {', '.join(missing)}")


def read_raw(files: list[Path], root: Path, config: dict[str, Any]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for file in files:
        frame = pd.read_excel(file)
        validate_columns(frame, config["required_columns"], file)
        relative = file.relative_to(root) if file.is_relative_to(root) else file
        frame["来源文件"] = str(relative)
        frame["搜索词"] = file.parent.name
        frame["平台"] = source_platform(file)
        frame["商品ID"] = frame["商品链接"].map(product_id)
        frame["原始行号"] = range(2, len(frame) + 2)
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    raw["时间"] = pd.to_datetime(raw["时间"], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in NUMERIC_COLUMNS:
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
    return raw


def build_monthly(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw["_销售额排序"] = pd.to_numeric(raw.get("销售额"), errors="coerce").fillna(0)
    raw["_销量排序"] = pd.to_numeric(raw.get("销量"), errors="coerce").fillna(0)
    raw = raw.sort_values(
        ["商品链接", "时间", "_销售额排序", "_销量排序"],
        ascending=[True, True, False, False],
        kind="mergesort",
    )

    agg: dict[str, Any] = {
        "商品ID": ("商品ID", first_nonempty),
        "商品标题": ("商品标题", first_nonempty),
        "平台": ("平台", join_unique),
        "品牌": ("品牌", first_nonempty) if "品牌" in raw.columns else ("商品链接", lambda _: ""),
        "店铺名": ("店铺名", first_nonempty) if "店铺名" in raw.columns else ("商品链接", lambda _: ""),
        "价格_CNY": ("价格", "median") if "价格" in raw.columns else ("商品链接", lambda _: None),
        "销售额_CNY": ("销售额", "max") if "销售额" in raw.columns else ("商品链接", lambda _: None),
        "销量": ("销量", "max") if "销量" in raw.columns else ("商品链接", lambda _: None),
        "搜索词": ("搜索词", join_unique),
        "来源文件": ("来源文件", join_unique),
        "重复来源行数": ("商品链接", "size"),
    }
    for col in CATEGORY_COLUMNS:
        if col in raw.columns:
            agg[col] = (col, first_nonempty)

    return raw.groupby(["商品链接", "时间"], dropna=False).agg(**agg).reset_index()


def classify_product(row: pd.Series, config: dict[str, Any]) -> tuple[str, str]:
    evidence = " ".join(
        str(row.get(col, ""))
        for col in ["商品标题", *CATEGORY_COLUMNS]
        if col in row.index
    )
    reasons: list[str] = []
    price = pd.to_numeric(row.get("中位价_CNY"), errors="coerce")
    low_price_cny = config.get("low_price_cny")

    if low_price_cny is not None and pd.notna(price) and price < float(low_price_cny):
        reasons.append(f"低价异常：商品级中位价低于 {low_price_cny} CNY")

    exclude_terms = configured_terms(config, "exclude_terms")
    if exclude_terms and contains_any(evidence, exclude_terms):
        reasons.append("非目标商品：命中本次配置的排除词")

    accessory_terms = configured_terms(config, "accessory_terms")
    if accessory_terms and contains_any(evidence, accessory_terms):
        reasons.append("非目标商品：标题或类目含配件/耗材/非整机语义")

    groups = configured_groups(config)
    for group in groups:
        if not contains_any(evidence, group["terms"]):
            reasons.append(f"非目标商品：缺少{group['name']}语义")

    target_terms = configured_terms(config, "target_terms")
    if target_terms and not groups and not contains_any(evidence, target_terms):
        reasons.append("非目标商品：未命中本次配置的目标词")

    adult_terms = configured_terms(config, "adult_or_generic_terms")
    function_terms = configured_terms(config, "function_terms")
    has_function = contains_any(evidence, function_terms) if function_terms else True
    if adult_terms and contains_any(evidence, adult_terms) and not has_function:
        reasons.append("非目标商品：更像成人/泛人群商品且缺少核心功能")

    if reasons:
        return "剔除", "；".join(dict.fromkeys(reasons))
    if not groups and not target_terms and not exclude_terms and not accessory_terms and low_price_cny is None:
        return "保留", "未配置品类清洗词，仅完成合并、去重和汇总"
    return "保留", f"符合{config['product_name']}目标商品规则"


def review_signals(row: pd.Series, config: dict[str, Any]) -> tuple[int, str, str]:
    evidence = " ".join(
        str(row.get(col, ""))
        for col in ["商品标题", *CATEGORY_COLUMNS]
        if col in row.index
    )
    status = str(row.get("清洗状态", ""))
    reason = str(row.get("剔除原因", ""))
    sales = pd.to_numeric(row.get("总销售额_CNY"), errors="coerce")
    sales_value = 0 if pd.isna(sales) else float(sales)
    median_price = pd.to_numeric(row.get("中位价_CNY"), errors="coerce")
    low_price_cny = config.get("low_price_cny")
    score = 0
    signals: list[str] = []

    target_terms = configured_terms(config, "target_terms")
    exclude_terms = configured_terms(config, "exclude_terms")
    accessory_terms = configured_terms(config, "accessory_terms")
    groups = configured_groups(config)

    if status == "剔除":
        score += 40
        signals.append("已剔除")
    if status == "剔除" and sales_value > 0:
        score += 30
        signals.append("剔除商品有销售额")
    if "低价异常" in reason:
        score += 15
        signals.append("低价规则命中")
    if low_price_cny is not None and pd.notna(median_price):
        threshold = float(low_price_cny)
        if threshold and threshold <= float(median_price) <= threshold * 1.25:
            score += 10
            signals.append("价格接近低价阈值")

    matched_target = matched_terms(evidence, target_terms)
    matched_exclude = matched_terms(evidence, exclude_terms)
    matched_accessory = matched_terms(evidence, accessory_terms)
    if matched_target and (matched_exclude or matched_accessory):
        score += 25
        signals.append("同时命中目标词和排除/配件词")

    missing_groups = []
    matched_group_parts = []
    for group in groups:
        group_matches = matched_terms(evidence, group["terms"], limit=5)
        if group_matches:
            matched_group_parts.append(f"{group['name']}={','.join(group_matches)}")
        else:
            missing_groups.append(str(group["name"]))
    if status == "剔除" and len(missing_groups) == 1 and groups:
        score += 20
        signals.append(f"仅缺少一个必需词组：{missing_groups[0]}")
    if status == "保留" and not groups and not target_terms:
        score += 10
        signals.append("未配置品类规则")

    if sales_value > 0:
        score += min(30, int(sales_value // 10000))

    matched_summary = []
    if matched_target:
        matched_summary.append("target=" + ",".join(matched_target))
    if matched_exclude:
        matched_summary.append("exclude=" + ",".join(matched_exclude))
    if matched_accessory:
        matched_summary.append("accessory=" + ",".join(matched_accessory))
    matched_summary.extend(matched_group_parts)

    if not signals:
        signals.append("按销售额抽样复核")
    return score, "；".join(signals), "；".join(matched_summary)


def build_review_products(products: pd.DataFrame, config: dict[str, Any], limit: int) -> pd.DataFrame:
    if limit <= 0 or products.empty:
        return pd.DataFrame()
    review = products.copy()
    signals = review.apply(lambda row: review_signals(row, config), axis=1, result_type="expand")
    review.insert(0, "复核优先级", signals[0])
    review.insert(1, "复核原因", signals[1])
    review.insert(2, "命中词摘要", signals[2])
    review.insert(3, "人工判断", "")
    review.insert(4, "人工备注", "")
    return review.sort_values(
        ["复核优先级", "总销售额_CNY"],
        ascending=[False, False],
        kind="mergesort",
    ).head(limit)


def build_products(monthly: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    agg: dict[str, Any] = {
        "商品ID": ("商品ID", first_nonempty),
        "商品标题": ("商品标题", first_nonempty),
        "平台": ("平台", join_unique),
        "品牌": ("品牌", first_nonempty),
        "店铺名": ("店铺名", first_nonempty),
        "中位价_CNY": ("价格_CNY", "median"),
        "最低价_CNY": ("价格_CNY", "min"),
        "最高价_CNY": ("价格_CNY", "max"),
        "总销售额_CNY": ("销售额_CNY", "sum"),
        "总销量": ("销量", "sum"),
        "月份数": ("时间", "nunique"),
        "首次月份": ("时间", "min"),
        "最近月份": ("时间", "max"),
        "搜索词": ("搜索词", join_unique),
        "来源文件": ("来源文件", join_unique),
        "原始重复行数": ("重复来源行数", "sum"),
    }
    for col in CATEGORY_COLUMNS:
        if col in monthly.columns:
            agg[col] = (col, first_nonempty)

    products = monthly.groupby("商品链接", dropna=False).agg(**agg).reset_index()
    classed = products.apply(lambda row: classify_product(row, config), axis=1, result_type="expand")
    products.insert(0, "清洗状态", classed[0])
    products.insert(1, "剔除原因", classed[1])
    return products.sort_values(["清洗状态", "总销售额_CNY"], ascending=[True, False])


def make_summary(files: list[Path], raw: pd.DataFrame, monthly: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    kept = products[products["清洗状态"].eq("保留")]
    removed = products[products["清洗状态"].eq("剔除")]
    rows = [
        ["源文件数", len(files)],
        ["原始行数", len(raw)],
        ["商品链接+月份去重后行数", len(monthly)],
        ["商品链接去重后商品数", len(products)],
        ["保留商品数", len(kept)],
        ["剔除商品数", len(removed)],
        ["保留商品总销售额_CNY", round(float(kept["总销售额_CNY"].sum()), 2) if len(kept) else 0],
        ["保留商品总销量", int(kept["总销量"].sum()) if len(kept) else 0],
    ]
    return pd.DataFrame(rows, columns=["指标", "数值"])


def make_rules(config: dict[str, Any], review_limit: int) -> pd.DataFrame:
    group_names = "；".join(group["name"] for group in configured_groups(config)) or "未配置"
    low_price_rule = (
        f"商品级中位价 < {config['low_price_cny']} CNY 时剔除。"
        if config.get("low_price_cny") is not None
        else "未配置低价阈值，不按价格自动剔除。"
    )
    rows = [
        ["产品名称", config["product_name"]],
        ["去重粒度", "同一 商品链接 + 时间（月） 只保留一条，优先保留销售额更高、销量更高的记录。"],
        ["商品级聚合", "按 商品链接 聚合月度去重结果，汇总销售额/销量，计算价格中位数和月份数。"],
        ["目标商品判断", f"按配置词判断；必需词组：{group_names}。若未配置词组但配置 target_terms，则至少命中一个目标词。"],
        ["排除词", "命中 exclude_terms 时剔除；命中 accessory_terms 时按配件/耗材/非整机剔除。"],
        ["低价异常", low_price_rule],
        ["类目处理", "平台类目仅作为辅助证据，不单独决定保留或剔除。"],
        ["规则校准模式", f"输出 待人工复核Top商品，最多 {review_limit} 行，优先展示高销售额剔除、边界价格、目标/排除词冲突、仅缺少一个必需词组的商品。"],
    ]
    return pd.DataFrame(rows, columns=["规则", "说明"])


def write_workbook(output: Path, summary: pd.DataFrame, rules: pd.DataFrame, monthly: pd.DataFrame, products: pd.DataFrame, review_products: pd.DataFrame) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    kept_products = products[products["清洗状态"].eq("保留")].copy()
    removed_products = products[products["清洗状态"].eq("剔除")].copy()
    kept_links = set(kept_products["商品链接"])
    removed_links = set(removed_products["商品链接"])
    kept_monthly = monthly[monthly["商品链接"].isin(kept_links)].sort_values(["商品链接", "时间"])
    removed_monthly = monthly[monthly["商品链接"].isin(removed_links)].sort_values(["商品链接", "时间"])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="清洗汇总", index=False)
        rules.to_excel(writer, sheet_name="清洗规则", index=False)
        review_products.to_excel(writer, sheet_name="待人工复核Top商品", index=False)
        kept_products.to_excel(writer, sheet_name="清洗后商品汇总", index=False)
        kept_monthly.to_excel(writer, sheet_name="清洗后月度明细", index=False)
        removed_products.to_excel(writer, sheet_name="剔除商品", index=False)
        removed_monthly.to_excel(writer, sheet_name="剔除月度明细", index=False)
        monthly.to_excel(writer, sheet_name="原始去重后月度", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge, dedupe, clean, and summarize ecommerce sales .xlsx exports.")
    parser.add_argument("--input", nargs="+", default=["."], help="Input files or folders. Directories are scanned recursively.")
    parser.add_argument("--output", default="outputs/cleaned_sales.xlsx", help="Output .xlsx workbook path.")
    parser.add_argument("--config", help="Optional JSON config path.")
    parser.add_argument("--product-name", help="Override product name used in output rules.")
    parser.add_argument("--low-price-cny", type=float, help="Override low-price threshold.")
    parser.add_argument("--review-top-n", type=int, default=50, help="Number of high-impact products to include in the manual review sheet.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path.cwd()
    config = load_config(Path(args.config)) if args.config else load_config(None)
    if args.product_name:
        config["product_name"] = args.product_name
    if args.low_price_cny is not None:
        config["low_price_cny"] = args.low_price_cny

    input_paths = [Path(value).expanduser().resolve() for value in args.input]
    files = find_input_files(input_paths)
    if not files:
        raise SystemExit("No .xlsx/.xls files found outside outputs folders.")

    raw = read_raw(files, root, config)
    monthly = build_monthly(raw)
    products = build_products(monthly, config)
    summary = make_summary(files, raw, monthly, products)
    rules = make_rules(config, args.review_top_n)
    review_products = build_review_products(products, config, args.review_top_n)
    write_workbook(Path(args.output), summary, rules, monthly, products, review_products)

    print(json.dumps({
        "source_files": len(files),
        "raw_rows": int(len(raw)),
        "deduped_monthly_rows": int(len(monthly)),
        "products": int(len(products)),
        "kept_products": int(products["清洗状态"].eq("保留").sum()),
        "removed_products": int(products["清洗状态"].eq("剔除").sum()),
        "review_products": int(len(review_products)),
        "output": str(Path(args.output).resolve()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
