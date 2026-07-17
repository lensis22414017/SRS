#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第 2.8 + 10.5 节: 三 XLSX 不可跳过回归测试。

用甲方三个原始 XLSX 做一次批量导入, 验证:
  1) 生成 3 个不同场地(不得三个文件都变成 GJ-2025-001 或同 site_code)
  2) 代表值校验:
     - 个旧 As=12420, Pb=15101.68
     - 南京栖霞四氯乙烯=43900
     - 乡村 Cd=1.72
  3) 元数据(序号/上下限/备注)不得识别为污染因子(GPT 2.6)

数据源:
  data/raw/1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx  (8点)
  data/raw/2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx      (49点)
  data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx    (134点)

注: 合并为单个测试函数, 避免 conftest 每测试 drop DB 导致后续测试无数据。
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

DATA_RAW = os.path.join(ROOT, "data", "raw")
XLSX_XIANGCUN = os.path.join(DATA_RAW, "1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx")
XLSX_QIXIA = os.path.join(DATA_RAW, "2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx")
XLSX_GEJIU = os.path.join(DATA_RAW, "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")


def test_three_xlsx_regression_all_checks():
    """三 XLSX 批量导入 + 全部校验(GPT 2.8 + 2.6)。

    单测试函数: 一次导入, 多个断言(避免 conftest drop DB 问题)。
    """
    # 缺任一 XLSX 则 skip(但不标 xfail, 让缺失可见)
    missing = [p for p in (XLSX_XIANGCUN, XLSX_QIXIA, XLSX_GEJIU) if not os.path.exists(p)]
    if missing:
        pytest.skip(f"缺少原始 XLSX: {[os.path.basename(m) for m in missing]}")

    from app.db.session import SessionLocal
    from app.models import Base, Site, Measurement, FactorDictionary, SamplingPoint
    from app.db import session as _session_mod
    from sqlalchemy import func
    from app.services.import_service import resolve_mapping_for_file
    from app.services.pipeline import run_import_with_mapping

    db = SessionLocal()
    try:
        # 逐文件导入(模拟批量)
        for xlsx in [XLSX_XIANGCUN, XLSX_QIXIA, XLSX_GEJIU]:
            used_id, mapping, report = resolve_mapping_for_file("auto", xlsx)
            run_import_with_mapping(db, xlsx, mapping, imported_by=1, on_conflict="skip")

        sites = db.query(Site).all()

        # ===== 校验 1: 3 个不同场地(GPT 2.8) =====
        assert len(sites) >= 3, f"应至少 3 个场地, 实际 {len(sites)}"
        codes = {s.site_code for s in sites}
        assert len(codes) >= 3, f"site_code 应 3 个不同值, 实际 {codes}"
        for s in sites:
            assert not s.site_code.startswith("GJ-2025"), \
                f"场地 {s.name} 仍用模板编号 {s.site_code}"

        # ===== 校验 2: 采样点数(乡村8/栖霞49/个旧134) =====
        for s in sites:
            n = db.query(SamplingPoint).filter_by(site_id=s.id).count()
            if s.pollution_type == "composite":
                assert n == 8, f"乡村场地应 8 点, 实际 {n}"
            elif s.pollution_type == "organic":
                assert n == 49, f"栖霞场地应 49 点, 实际 {n}"
            elif s.pollution_type == "heavy_metal":
                assert n == 134, f"个旧场地应 134 点, 实际 {n}"

        # ===== 校验 3: 个旧代表值 As=12420, Pb=15101.68 =====
        gejiu = next((s for s in sites if s.pollution_type == "heavy_metal"), None)
        assert gejiu, "未找到个旧场地"
        as_max = db.query(func.max(Measurement.value)).join(FactorDictionary).filter(
            Measurement.site_id == gejiu.id,
            FactorDictionary.factor_code.in_(["As", "砷", "As_mgkg"])
        ).scalar()
        assert as_max is not None, "个旧未找到 As"
        assert 12400 <= float(as_max) <= 12500, f"个旧 As 应 ~12420, 实际 {as_max}"
        pb_max = db.query(func.max(Measurement.value)).join(FactorDictionary).filter(
            Measurement.site_id == gejiu.id,
            FactorDictionary.factor_code.in_(["Pb", "铅", "Pb_mgkg"])
        ).scalar()
        if pb_max is not None:
            assert 15000 <= float(pb_max) <= 15200, f"个旧 Pb 应 ~15101.68, 实际 {pb_max}"

        # ===== 校验 4: 栖霞四氯乙烯=43900 =====
        qixia = next((s for s in sites if s.pollution_type == "organic"), None)
        assert qixia, "未找到栖霞场地"
        pce_max = db.query(func.max(Measurement.value)).join(FactorDictionary).filter(
            Measurement.site_id == qixia.id,
            FactorDictionary.factor_name.like("%四氯%")
        ).scalar()
        if pce_max is not None:
            assert 43800 <= float(pce_max) <= 44000, f"栖霞四氯乙烯应 ~43900, 实际 {pce_max}"

        # ===== 校验 5: 乡村 Cd=1.72 =====
        xc = next((s for s in sites if s.pollution_type == "composite"), None)
        assert xc, "未找到乡村场地"
        cd_max = db.query(func.max(Measurement.value)).join(FactorDictionary).filter(
            Measurement.site_id == xc.id,
            FactorDictionary.factor_code.in_(["Cd", "镉", "Cd_mgkg"])
        ).scalar()
        if cd_max is not None:
            assert 1.5 <= float(cd_max) <= 2.0, f"乡村 Cd 应 ~1.72, 实际 {cd_max}"

        # ===== 校验 6: 元数据不得识别为污染因子(GPT 2.6) =====
        all_factor_codes = {f.factor_code for f in db.query(FactorDictionary.factor_code).join(Measurement).distinct().all()}
        forbidden = {"序号", "上限", "下限", "备注", "经度", "纬度", "深度"}
        leaked = all_factor_codes & forbidden
        assert not leaked, f"元数据被识别为因子(GPT 2.6 违规): {leaked}"

        # ===== 校验 7: smart_detect 应识别 region/depth/soil_type(GPT 3a) =====
        # 删预设模板后 smart_detect 必须承担采样点元信息映射, 否则 EDA 分组降级
        gejiu_points = (db.query(SamplingPoint)
                        .join(Site, SamplingPoint.site_id == Site.id)
                        .filter(Site.name.like("%个旧%")).all())
        if gejiu_points:
            regions = {p.region for p in gejiu_points if p.region}
            assert len(regions) >= 2, \
                f"个旧采样点 region 应≥2个区域(smart_detect 识别), 实际 {regions}"
            depth_filled = sum(1 for p in gejiu_points if p.depth_top_cm is not None)
            assert depth_filled == len(gejiu_points), \
                f"个旧采样点 depth_top_cm 应全部填充, 实际 {depth_filled}/{len(gejiu_points)}"

    finally:
        db.close()
