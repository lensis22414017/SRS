"""Round10 源码与构建门禁的不可跳过回归测试。"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]


def _write_artifacts(root: Path, model_id: str, *, metrics: bool = True) -> dict:
    artifact_dir = root / "ml" / "artifacts" / "p3_alpha"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model = artifact_dir / f"{model_id}.joblib"
    shap = artifact_dir / f"{model_id}_shap_global.parquet"
    metric = artifact_dir / f"{model_id}_metrics.json"
    joblib.dump({"model": "fixture", "feature_list": ["pH"]}, model)
    pd.DataFrame({"group": ["pH"], "mean_abs_shap": [1.0]}).to_parquet(shap)
    if metrics:
        metric.write_text(json.dumps({"test_spearman": 0.8}), encoding="utf-8")
    return {
        "model_file": model.relative_to(root).as_posix(),
        "shap_global_file": shap.relative_to(root).as_posix(),
        "metrics_file": metric.relative_to(root).as_posix(),
        "frontend_enabled": True,
    }


def test_model_health_requires_every_frontend_enabled_artifact(tmp_path: Path):
    """任一启用模型缺工件时整体健康状态必须失败。"""
    from app.main import _check_model_integrity

    first = _write_artifacts(tmp_path, "first")
    second = _write_artifacts(tmp_path, "second", metrics=False)
    first["metrics_file"] = first["metrics_file"].replace("/", "\\")
    registry = tmp_path / "ml" / "artifacts" / "p3_alpha" / "model_registry_v0.8.json"
    registry.write_text(
        json.dumps({"models": {"first": first, "second": second}}),
        encoding="utf-8",
    )

    failed = _check_model_integrity(str(tmp_path))
    assert failed["ok"] is False
    assert "second/metrics" in failed["missing"]

    _write_artifacts(tmp_path, "second", metrics=True)
    passed = _check_model_integrity(str(tmp_path))
    assert passed["ok"] is True
    assert passed["n_models_ok"] == passed["n_models_checked"] == 2


def test_regulatory_workflow_is_valid_yaml_without_dynamic_needs_expression():
    """GitHub Actions 不允许 needs.${JOB} 这种动态表达式。"""
    path = ROOT / ".github" / "workflows" / "regulatory-redteam-validation.yml"
    text = path.read_text(encoding="utf-8")
    assert "needs.${JOB}" not in text
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict)
    assert "jobs" in parsed
    assert "redteam-summary" in parsed["jobs"]


def test_ci_downloads_lfs_models_and_scopes_postgres_to_concurrency():
    """真实模型由 LFS 管理；数据库专项作业只验证 PostgreSQL 并发锁。"""
    path = ROOT / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    backend_checkout = jobs["backend"]["steps"][0]
    assert backend_checkout["uses"] == "actions/checkout@v4"
    assert backend_checkout["with"]["lfs"] is True
    assert any(
        "_check_model_integrity" in step.get("run", "")
        for step in jobs["backend"]["steps"]
    )

    postgres_test = jobs["backend-postgres"]["steps"][-1]["run"]
    assert 'setup_real_concurrent' in postgres_test
    assert ' or kos' not in postgres_test
    assert ' or stale' not in postgres_test


def test_packaging_gate_checks_missing_flow_directory_and_all_enabled_models():
    spec = (ROOT / "packaging" / "srs.spec").read_text(encoding="utf-8")
    assert "if not _flows_in_dist.is_dir()" in spec
    assert 'info.get("frontend_enabled") is True' in spec
    assert "_joblib.load" in spec
    assert "_pd.read_parquet" in spec
    assert "--distpath dist_new" in spec
