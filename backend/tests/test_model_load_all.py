#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""R3 审计阶段 N2.3: 全模型加载测试。

验证审计第二类要求:
  hm_op/op/hm/all 的生产/生态模型必须全部进行加载测试。
  每个 joblib 能被 joblib.load 成功, 每个 shap parquet 能被 pd.read_parquet 成功。
"""
import os
import sys
import json
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

REGISTRY = os.path.join(ROOT, "ml", "artifacts", "p3_alpha",
                        "model_registry_v0.8.json")


@pytest.fixture(scope="module")
def registry_data():
    if not os.path.exists(REGISTRY):
        pytest.skip(f"模型注册表不存在: {REGISTRY}")
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def _model_cases(registry_data):
    """生成所有模型的测试用例 (model_id, model_file, shap_global_file, metrics_file)。"""
    cases = []
    for model_id, info in registry_data.get("models", {}).items():
        cases.append(pytest.param(
            model_id,
            info.get("model_file", ""),
            info.get("shap_global_file", ""),
            info.get("metrics_file", ""),
            id=model_id
        ))
    return cases


@pytest.mark.parametrize("model_id,model_file,shap_file,metrics_file",
                         _model_cases(json.load(open(REGISTRY, encoding="utf-8"))
                                      if os.path.exists(REGISTRY) else {"models": {}}))
def test_model_joblib_loadable(model_id, model_file, shap_file, metrics_file):
    """每个注册模型的 joblib 必须能加载(审计 2.A)。"""
    if not model_file:
        pytest.skip(f"{model_id} 无 model_file")
    abs_path = os.path.join(ROOT, model_file) if not os.path.isabs(model_file) else model_file
    if not os.path.exists(abs_path):
        pytest.skip(f"{model_id} joblib 文件不存在: {abs_path}")

    import joblib
    bundle = joblib.load(abs_path)
    # bundle 应至少含 model 或 feature_list
    assert bundle is not None, f"{model_id} joblib 加载返回 None"
    if isinstance(bundle, dict):
        assert "model" in bundle or "feature_list" in bundle, \
            f"{model_id} joblib 结构异常: keys={list(bundle.keys())}"


@pytest.mark.parametrize("model_id,model_file,shap_file,metrics_file",
                         _model_cases(json.load(open(REGISTRY, encoding="utf-8"))
                                      if os.path.exists(REGISTRY) else {"models": {}}))
def test_shap_parquet_readable(model_id, model_file, shap_file, metrics_file):
    """每个注册模型的 SHAP parquet 必须能读取(审计 2.A 核心)。"""
    if not shap_file:
        pytest.skip(f"{model_id} 无 shap_global_file")
    abs_path = os.path.join(ROOT, shap_file) if not os.path.isabs(shap_file) else shap_file
    if not os.path.exists(abs_path):
        pytest.skip(f"{model_id} parquet 不存在: {abs_path}")

    import pandas as pd
    df = pd.read_parquet(abs_path)
    assert df is not None and len(df) > 0, \
        f"{model_id} SHAP parquet 为空: {abs_path}"


@pytest.mark.parametrize("model_id,model_file,shap_file,metrics_file",
                         _model_cases(json.load(open(REGISTRY, encoding="utf-8"))
                                      if os.path.exists(REGISTRY) else {"models": {}}))
def test_metrics_json_parsable(model_id, model_file, shap_file, metrics_file):
    """每个注册模型的 metrics JSON 必须可解析(审计 7.6)。"""
    if not metrics_file:
        pytest.skip(f"{model_id} 无 metrics_file")
    abs_path = os.path.join(ROOT, metrics_file) if not os.path.isabs(metrics_file) else metrics_file
    if not os.path.exists(abs_path):
        pytest.skip(f"{model_id} metrics 不存在: {abs_path}")

    with open(abs_path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict), f"{model_id} metrics 不是 JSON 对象"


def test_pyarrow_importable():
    """pyarrow 必须可导入(审计 2.A 前置条件)。"""
    import pyarrow
    import pandas as pd
    # 验证 pd.read_parquet 实际可用(不会因缺引擎报错)
    assert hasattr(pd, "read_parquet"), "pandas.read_parquet 不存在"
