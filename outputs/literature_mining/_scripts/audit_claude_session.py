"""从指定 Claude 会话中提取 SOIL_CLEAN 数据质量的可核查证据。"""
from __future__ import annotations

import json
import re
from pathlib import Path


SESSION = Path(r"C:\Users\曾鸿\.claude\projects\C--Users---\256efec4-085c-4e28-a198-da065f46a8b0.jsonl")
OUT = Path(__file__).resolve().parents[1] / "CLAUDE_SESSION_AUDIT_256efec4.md"
TARGETS = ("phase14_extract_batch2.py", "phase14_batch2_pipeline.py")
KEY_RE = re.compile(
    r"unit|detect_unit|matrix|is_valid_value|by_paper|has_hm|has_op|"
    r"pollution_type|sample_id|return .soil.|\(\"soil\", \"default\"\)",
    re.I,
)


def main() -> None:
    type_counts: dict[str, int] = {}
    sources: dict[str, str] = {}
    for line in SESSION.open(encoding="utf-8"):
        record = json.loads(line)
        record_type = record.get("type", "unknown")
        type_counts[record_type] = type_counts.get(record_type, 0) + 1
        if record_type != "assistant":
            continue
        for item in record.get("message", {}).get("content", []):
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            tool_input = item.get("input", {})
            file_path = str(tool_input.get("file_path", ""))
            for target in TARGETS:
                if file_path.endswith(target) and tool_input.get("content"):
                    sources.setdefault(target, tool_input["content"])

    lines = [
        "# Claude 会话数据提取审计",
        "",
        "## 审计结论",
        "",
        "结论不是二选一：现有稀疏性同时来自原文/SI缺失和提取实现缺陷。实现缺陷曾系统性放大缺失、误分类与伪配对，因此旧表不能直接视为可信训练真值。",
        "",
        "| 类别 | 会话内可复核证据 | 影响 | 当前处置 |",
        "|---|---|---|---|",
        "| 单位实现缺陷 | `phase14_extract_batch2.py` 定义了 `detect_unit()`，但三处记录输出硬编码 `unit = Unknown` | 可转换浓度被误记为未知单位，制造结构性缺失 | 已改为单位传播并加测试 |",
        "| HM+OP语义缺陷 | `phase14_batch2_pipeline.py` 先按 `paper_id` 聚合，只要同一论文分别出现HM和OP就整体进入 `hm_op` | 不同样点被伪配对，复合污染标签失真 | 已改为 `sample_id` 级交集判定 |",
        "| 介质实现缺陷 | 无目录、无MD、异常或无关键词时均返回/回退 `soil` | 水体、沉积物等可能被误纳入土壤训练集 | 已取消缺失介质默认soil |",
        "| 值域实现缺陷 | HM浓度 `-1 <= v <= 1` 被整体删除以规避相关系数 | 合法低浓度HM被系统删除 | 已改为基于表语义过滤，不按低值一刀切 |",
        "| 来源客观限制 | 会话多次记录主文只有汇总统计、样点表在SI、部分SI物理缺失 | 即便修复提取器，样点级完整协变量仍不足 | 只纳入可追溯原生SI；不足部分降级参考 |",
        "",
        "因此：旧数据‘看起来很稀疏’不能证明原文天然稀疏；修复后仍缺的字段，才可归入来源限制。",
        "",
        "## 会话元数据",
        "",
        f"- 会话文件：`{SESSION}`",
        f"- 文件大小：{SESSION.stat().st_size:,} bytes",
        f"- 记录类型计数：`{type_counts}`",
        "",
        "## 原始实现证据（行号为会话首次写入版本）",
        "",
    ]
    for target in TARGETS:
        source = sources.get(target, "")
        lines.extend([f"### `{target}`", "", "```text"])
        for number, source_line in enumerate(source.splitlines(), start=1):
            if KEY_RE.search(source_line):
                lines.append(f"{number}: {source_line}")
        lines.extend(["```", ""])
    if len(sources) != len(TARGETS):
        missing = sorted(set(TARGETS) - set(sources))
        raise RuntimeError(f"会话中未找到首次写入内容: {missing}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"records={sum(type_counts.values())} sources={len(sources)} output={OUT}")


if __name__ == "__main__":
    main()
