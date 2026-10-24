#!/usr/bin/env python3
"""
compare_deals.py - 对多种麦当劳点餐方案做确定性比价排序

用途：
    当 SKILL.md 第五步产生 2-3 个候选组合时，用本脚本对 calculate-price 的
    返回结果做排序与差价比对，避免在多方案场景下口算出错。

用法：
    python compare_deals.py deals.json
    python compare_deals.py -            # 从 stdin 读入

输入格式（JSON 数组，每个元素是一个方案）：
    [
      {
        "name": "巨无霸套餐 + 中薯",
        "store": "麦当劳(南京东路店)",
        "distance_km": 0.8,
        "items": ["巨无霸套餐 x1", "中薯 x1"],
        "original": 47.0,        # 原价合计，可选；缺省时用优惠前的金额推断
        "discount": 12.5,        # 优惠减免，可选
        "delivery_fee": 0,       # 配送费，可选，默认 0
        "payable": 34.5,         # 应付金额，必填
        "coupon": "满30减8"      # 使用的券，可选
      },
      ...
    ]

    必填字段只有 payable。其余缺失时按 0 或空处理，不影响排序。

输出：
    按实付金额（payable + delivery_fee）升序排列的对比表，
    并给出相对最优方案的差额、节省比例。

退出码：
    0 正常；1 输入错误；2 数据异常（全部方案金额非法）
"""

import json
import sys


def _num(value, default=0.0):
    """把可能是 str/None 的金额字段安全转成 float。"""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _total_cost(deal):
    """实付总额 = 应付 + 配送费。配送费是真实支出，排序必须算进去。"""
    return _num(deal.get("payable")) + _num(deal.get("delivery_fee"))


def normalize(deals):
    """校验并补齐每个方案，返回带计算字段的新列表。"""
    result = []
    for idx, deal in enumerate(deals):
        if not isinstance(deal, dict):
            print(f"警告：第 {idx + 1} 项不是对象，已跳过", file=sys.stderr)
            continue

        payable = deal.get("payable")
        if payable is None:
            print(f"警告：方案「{deal.get('name', idx + 1)}」缺少 payable，已跳过",
                  file=sys.stderr)
            continue

        total = _total_cost(deal)
        original = _num(deal.get("original"))
        discount = _num(deal.get("discount"))

        # 原价缺失时用 应付+优惠 反推，仅用于展示"原价→应付"的落差
        if original <= 0:
            original = _num(payable) + discount

        # 真实节省 = 原价 - 实付总额（含配送费），比单看优惠额更贴近用户感受
        real_saving = original - total if original > 0 else 0.0

        item = dict(deal)
        item["_payable"] = _num(payable)
        item["_delivery"] = _num(deal.get("delivery_fee"))
        item["_total"] = total
        item["_original"] = original
        item["_discount"] = discount
        item["_real_saving"] = real_saving
        result.append(item)

    return result


def render(deals):
    """输出对比表。排序按实付总额升序，差额相对第一行。"""
    deals.sort(key=lambda d: (d["_total"], d.get("distance_km") or float("inf")))
    best_total = deals[0]["_total"]

    lines = []
    lines.append("=" * 78)
    lines.append("麦当劳点餐方案比价")
    lines.append("=" * 78)

    for rank, deal in enumerate(deals, 1):
        name = deal.get("name") or f"方案{rank}"
        store = deal.get("store") or "—"
        distance = deal.get("distance_km")
        dist_text = f"{distance} km" if distance not in (None, "") else "—"
        diff = deal["_total"] - best_total
        diff_text = "最优" if diff <= 0 else f"+¥{diff:.2f}"

        lines.append("")
        lines.append(f"[{rank}] {name}")
        lines.append(f"    门店    {store}（{dist_text}）")
        if deal.get("items"):
            items = deal["items"]
            if isinstance(items, list):
                items = "、".join(str(i) for i in items)
            lines.append(f"    餐品    {items}")
        lines.append(f"    原价    ¥{deal['_original']:.2f}")
        lines.append(f"    优惠    -¥{deal['_discount']:.2f}"
                     + (f"（{deal['coupon']}）" if deal.get("coupon") else ""))
        if deal["_delivery"] > 0:
            lines.append(f"    配送费  ¥{deal['_delivery']:.2f}")
        lines.append(f"    实付    ¥{deal['_total']:.2f}    较最优 {diff_text}")
        if deal["_real_saving"] > 0:
            lines.append(f"    实际省  ¥{deal['_real_saving']:.2f}")

    lines.append("")
    lines.append("-" * 78)

    if len(deals) > 1:
        best = deals[0]
        worst = deals[-1]
        gap = worst["_total"] - best["_total"]
        lines.append(f"最低实付 ¥{best['_total']:.2f}（{best.get('name', '方案1')}）")
        if gap > 0:
            lines.append(f"与最高方案相差 ¥{gap:.2f}")
            if worst["_total"] > 0:
                lines.append(f"最高方案多花 {gap / worst['_total'] * 100:.1f}%")
        # 提示"最便宜"未必等于"最近"，让用户自己权衡
        nearest = min(
            (d for d in deals if d.get("distance_km") not in (None, "")),
            key=lambda d: _num(d.get("distance_km")),
            default=None,
        )
        if nearest is not None and nearest is not best:
            lines.append(
                f"注意：最近门店方案为「{nearest.get('name', '')}」"
                f"（{nearest.get('distance_km')} km，实付 ¥{nearest['_total']:.2f}），"
                f"非最低价方案，需按距离与价格权衡。"
            )
    else:
        lines.append(f"单一方案，实付 ¥{deals[0]['_total']:.2f}")

    lines.append("=" * 78)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    arg = sys.argv[1]
    try:
        if arg == "-":
            raw = sys.stdin.read()
        else:
            with open(arg, "r", encoding="utf-8") as f:
                raw = f.read()
        data = json.loads(raw)
    except FileNotFoundError:
        print(f"错误：找不到文件 {arg}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"错误：JSON 解析失败 - {e}", file=sys.stderr)
        return 1

    # 兼容单个对象输入，包成数组
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        print("错误：输入应为非空的方案数组", file=sys.stderr)
        return 1

    deals = normalize(data)
    if not deals:
        print("错误：没有有效方案（均缺少 payable 字段）", file=sys.stderr)
        return 2

    print(render(deals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
