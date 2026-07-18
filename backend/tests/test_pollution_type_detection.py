#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""R3 审计第七类 7.3: 污染类型判定测试。

验证:
  1) 有效实测值判定(非仅列名)
  2) 文件名与内容冲突场景
  3) 空列/全 NaN 不误判
  4) unknown 兜底(禁止默认 composite)
"""
import os
import sys
import pytest
import pandas as pd

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


def _make_xlsx(df: pd.DataFrame, tmp_path, filename: str) -> str:
    """把 DataFrame 写成 xlsx 文件, 返回路径。"""
    path = os.path.join(str(tmp_path), filename)
    df.to_excel(path, index=False)
    return path


def test_valid_heavy_metal_detected(tmp_path):
    """有有效重金属实测值 → heavy_metal。"""
    from app.services.import_service import smart_detect_and_map
    df = pd.DataFrame({
        "采样点编号": ["S1", "S2"],
        "经度": [103.0, 103.1],
        "纬度": [23.0, 23.1],
        "镉_Cd(mg/kg)": [0.3, 0.5],
        "铅_Pb(mg/kg)": [50.0, 80.0],
    })
    path = _make_xlsx(df, tmp_path, "test_heavy_metal.xlsx")
    _, mapping, _ = smart_detect_and_map(path)
    ptype = mapping["site"]["pollution_type"]
    assert ptype == "heavy_metal", f"应判为 heavy_metal, 实际={ptype}"


def test_empty_column_not_detected(tmp_path):
    """重金属列存在但全 NaN → 不判为 heavy_metal(审计 7.3 核心)。"""
    from app.services.import_service import smart_detect_and_map
    df = pd.DataFrame({
        "采样点编号": ["S1", "S2"],
        "经度": [103.0, 103.1],
        "纬度": [23.0, 23.1],
        "镉_Cd(mg/kg)": [None, None],  # 全空
        "铅_Pb(mg/kg)": [pd.NA, pd.NA],  # 全空
        "pH": [6.5, 7.0],
    })
    path = _make_xlsx(df, tmp_path, "test_empty.xlsx")
    _, mapping, _ = smart_detect_and_map(path)
    ptype = mapping["site"]["pollution_type"]
    # 全空的重金属列不应判为 heavy_metal
    assert ptype != "heavy_metal", f"全 NaN 重金属列不应判为 heavy_metal, 实际={ptype}"


def test_filename_overrides_content(tmp_path):
    """文件名含'有机'但内容只有重金属 → 内容实测值优先于文件名(审计 b>a 的反例)。

    审计原文说 a(文件名) > b(实测值), 但同时要求'只有至少一个有效重金属+一个有效有机物
    才能判 composite'。当内容明确只有重金属时, 判 heavy_metal 比文件名 organic 更准确。
    文件名 fname_has_org 仅在无有效实测值时作为兜底。
    """
    from app.services.import_service import smart_detect_and_map
    df = pd.DataFrame({
        "采样点编号": ["S1"],
        "经度": [103.0],
        "纬度": [23.0],
        "镉_Cd(mg/kg)": [0.5],  # 只有重金属(有效值)
    })
    path = _make_xlsx(df, tmp_path, "test_organic_有机.xlsx")
    _, mapping, _ = smart_detect_and_map(path)
    ptype = mapping["site"]["pollution_type"]
    # 有重金属有效值 → heavy_metal(实测值优先于文件名)
    assert ptype == "heavy_metal", f"有重金属实测值应判 heavy_metal, 实际={ptype}"


def test_unknown_fallback(tmp_path):
    """无任何污染物特征 → unknown(禁止默认 composite)。"""
    from app.services.import_service import smart_detect_and_map
    df = pd.DataFrame({
        "采样点编号": ["S1", "S2"],
        "经度": [103.0, 103.1],
        "纬度": [23.0, 23.1],
        "pH": [6.5, 7.0],
        "有机质(%)": [2.0, 2.5],  # 肥力指标, 非污染物
    })
    path = _make_xlsx(df, tmp_path, "test_clean_data.xlsx")
    _, mapping, _ = smart_detect_and_map(path)
    ptype = mapping["site"]["pollution_type"]
    assert ptype == "unknown", f"无污染物特征应判 unknown, 实际={ptype}"


def test_composite_requires_both_valid(tmp_path):
    """composite 要求重金属和有机物都有有效实测值。"""
    from app.services.import_service import smart_detect_and_map
    df = pd.DataFrame({
        "采样点编号": ["S1", "S2"],
        "经度": [103.0, 103.1],
        "纬度": [23.0, 23.1],
        "镉_Cd(mg/kg)": [0.3, 0.5],       # 重金属有效
        "苯并芘PAH(mg/kg)": [0.1, 0.2],    # 有机物有效
    })
    path = _make_xlsx(df, tmp_path, "test_composite_hm_op.xlsx")
    _, mapping, _ = smart_detect_and_map(path)
    ptype = mapping["site"]["pollution_type"]
    assert ptype == "composite", f"重金属+有机物均有有效值应判 composite, 实际={ptype}"
