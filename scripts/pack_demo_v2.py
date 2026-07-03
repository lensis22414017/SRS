#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pack_demo_v2.py — 第二阶段演示包 v2 打包
====================================================================
收集以下产物 → 桌面 第二阶段演示包_v2_YYYYMMDD.zip

1. 演示路线截图(round6, 15 张 + README)
2. 大屏截图(含在 round6)
3. 15+3 批量验证结果(md + csv)
4. 6 PDF + 6 DOCX 报告(带地图, demo_reports_v2)
5. 地图嵌入验证报告
6. EDA 组件验证报告
7. 甲方演示路线/禁区/README/BLOCKERS
====================================================================
"""
import os, sys, zipfile, shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = Path.home() / "Desktop"
NOW = datetime.now().strftime("%Y%m%d")
OUT_ZIP = DESKTOP / f"第二阶段演示包_v2_{NOW}.zip"

# 待收集清单: (仓库内路径, zip 内路径)
COLLECT = [
    # 1. round6 截图
    ("docs/audit/screenshots_round6", "01_截图_round6"),
    # 2. 报告(带地图)
    ("artifacts/demo_reports_v2_20260703", "02_报告_带地图"),
    # 3. 验证文档
    ("docs/reports/round6_15plus3_batch_validation.md", "03_验证/15+3批量验证.md"),
    ("docs/reports/round6_15plus3_batch_validation.csv", "03_验证/15+3批量验证.csv"),
    ("docs/reports/report_map_embedding_validation.md", "03_验证/报告地图嵌入验证.md"),
    ("docs/reports/eda_component_validation.md", "03_验证/EDA组件验证.md"),
    ("docs/reports/round6_final_acceptance.md", "03_验证/最终验收口径.md"),
    # 4. 演示文档(若存在)
    ("docs/demo_package_20260703", "04_演示文档"),
]


def add_to_zip(zf, src: Path, arcname: str):
    """安全添加文件/目录到 zip"""
    if not src.exists():
        print(f"  ⚠ 跳过(不存在): {src}")
        return 0
    n = 0
    if src.is_file():
        zf.write(src, arcname)
        n = 1
    else:
        for root, _, files in os.walk(src):
            for f in files:
                fp = Path(root) / f
                rel = Path(arcname) / fp.relative_to(src)
                zf.write(fp, str(rel))
                n += 1
    return n


def write_readme(zf):
    """写入 zip 内总 README"""
    readme = f"""# 第二阶段演示包 v2

> 打包时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
> 来源: SRS 污染场地土壤生态-生产功能重构监管系统

## 目录结构

```
01_截图_round6/          # 15 张演示路线截图 + README(每张证明什么)
02_报告_带地图/          # 6 PDF + 6 DOCX 全流程追溯报告(嵌入 matplotlib 地图)
03_验证/
  ├── 15+3批量验证.md    # 3 真实 + 15 内部场地 × 11 环节
  ├── 15+3批量验证.csv
  ├── 报告地图嵌入验证.md
  ├── EDA组件验证.md
  └── 最终验收口径.md    # 四分类: 已完成/Alpha/待完善/勿触碰
04_演示文档/             # 账号/数据/路线/禁区/话术
```

## 账号
- admin / Demo@2026 (全权限)
- enterprise / Demo@2026 (企业, 仅本企业场地)
- regulator / Demo@2026 (监管只读)

## 重要诚实声明
- 报告地图为离线 matplotlib 散点(无真实瓦片底图), 水印标注。
- OP 有机污染模型仍为探索性, 相关结论需人工复核。
- 15 内部场地仅验证 KOS 链路, 重构/SSUI/报告用真实 3 场地。
- 全程不写"全部完成", 详见 03_验证/最终验收口径.md。
"""
    zf.writestr("README.md", readme)


def main():
    print("=" * 60)
    print(f"打包第二阶段演示包 v2 → {OUT_ZIP}")
    print("=" * 60)
    total = 0
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for src_rel, arc in COLLECT:
            src = ROOT / src_rel
            n = add_to_zip(zf, src, arc)
            total += n
            mark = "✅" if n else "⚠"
            print(f"  {mark} {src_rel} → {arc} ({n} 文件)")
        write_readme(zf)
        total += 1
    size_mb = OUT_ZIP.stat().st_size / 1024 / 1024
    print(f"\n完成: {OUT_ZIP} ({size_mb:.1f} MB, {total} 文件)")


if __name__ == "__main__":
    main()
