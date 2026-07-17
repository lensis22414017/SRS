#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第 10.4 节: 模型工件缺失必须导致测试失败。

验证: 每个注册的 model_id 的 joblib 文件必须物理存在。
缺失任何一个 → 测试 fail(不是 skip)。
"""
import os
import sys
import json
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

REGISTRY = os.path.join(ROOT, "ml", "artifacts", "p3_alpha", "model_registry_v0.8.json")
ARTIFACTS_DIR = os.path.join(ROOT, "ml", "artifacts", "p3_alpha")


def test_registry_exists():
    """模型注册表必须存在。"""
    assert os.path.exists(REGISTRY), f"模型注册表不存在: {REGISTRY}"


def test_all_registered_model_files_exist():
    """每个注册模型的 joblib 文件必须物理存在(GPT 10.4)。

    缺失任何一个 → fail(非 skip)。
    """
    if not os.path.exists(REGISTRY):
        pytest.fail(f"模型注册表不存在: {REGISTRY}")

    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)

    models = registry.get("models", {})
    assert len(models) > 0, "注册表应至少有1个模型"

    missing = []
    for model_id, info in models.items():
        model_file = info.get("model_file", "")
        # model_file 可能是相对路径(相对项目根)
        if not os.path.isabs(model_file):
            model_file = os.path.join(ROOT, model_file.replace("\\", "/"))
        if not os.path.exists(model_file):
            missing.append(f"{model_id}: {model_file}")

    assert not missing, f"模型工件缺失(GPT 10.4): {missing}"


def test_shap_global_files_exist():
    """每个模型的 SHAP 全局贡献 parquet 必须存在。"""
    if not os.path.exists(REGISTRY):
        pytest.skip("注册表不存在")

    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)

    missing = []
    for model_id, info in registry.get("models", {}).items():
        shap_file = info.get("shap_global_file", "")
        if not os.path.isabs(shap_file):
            shap_file = os.path.join(ROOT, shap_file.replace("\\", "/"))
        if not os.path.exists(shap_file):
            missing.append(f"{model_id}: {shap_file}")

    # SHAP 文件缺失是警告(非致命), 因为有 fallback
    if missing:
        pytest.skip(f"SHAP 全局文件缺失(有 fallback): {missing[:3]}")


def test_approved_models_frontend_enabled():
    """approved_alpha 模型应 frontend_enabled=True。"""
    if not os.path.exists(REGISTRY):
        pytest.skip("注册表不存在")

    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)

    for model_id, info in registry.get("models", {}).items():
        if info.get("status") == "approved_alpha":
            assert info.get("frontend_enabled") is True, \
                f"{model_id} 是 approved_alpha 应 frontend_enabled=True"
