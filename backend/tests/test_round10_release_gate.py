"""Round10 源码与构建门禁的不可跳过回归测试。"""
from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import sys

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


def test_windowed_launcher_redirects_missing_stdio_to_appdata(tmp_path: Path, monkeypatch):
    """console=False 时启动器不得因 print 写入 None 而静默退出。"""
    module_path = ROOT / "packaging" / "launcher.py"
    spec = importlib.util.spec_from_file_location("srs_launcher_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    log_handle = None
    try:
        monkeypatch.setenv("APPDATA", str(tmp_path))
        sys.stdout = None
        sys.stderr = None
        module._ensure_windowed_stdio()
        log_handle = sys.stdout
        assert log_handle is not None
        assert sys.stderr is log_handle
        print("windowed-launcher-smoke", flush=True)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if log_handle is not None:
            log_handle.close()

    log_path = tmp_path / "SRS" / "launcher.log"
    assert log_path.is_file()
    assert "windowed-launcher-smoke" in log_path.read_text(encoding="utf-8")


def test_packaging_gate_checks_missing_flow_directory_and_all_enabled_models():
    spec = (ROOT / "packaging" / "srs.spec").read_text(encoding="utf-8")
    assert "if not _flows_in_dist.is_dir()" in spec
    assert 'info.get("frontend_enabled") is True' in spec
    assert "_joblib.load" in spec
    assert "_pd.read_parquet" in spec
    assert "--distpath dist_new" in spec


def test_packaging_keeps_pdf_fallback_dependencies_and_html_report_mime():
    """打包后 PDF 备用链路需要 Pillow；公开支持的 HTML 报告必须可保存。"""
    from app.services.file_service import _validate_upload

    spec = (ROOT / "packaging" / "srs.spec").read_text(encoding="utf-8")
    excluded = spec.split("excluded_imports = [", 1)[1].split("]", 1)[0]
    assert '"PIL"' not in excluded
    assert '"PIL.Image"' in spec
    assert '"PIL._imaging"' in spec
    _validate_upload(b"<html><body>SRS</body></html>", "report.html", "text/html")


def test_installer_keeps_admin_default_but_allows_isolated_current_user_validation():
    installer = (ROOT / "packaging" / "srs_setup.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=admin" in installer
    assert "PrivilegesRequiredOverridesAllowed=commandline" in installer
    assert "AppId={{B8F3E2A1-2026-0716-SRSO-000000000001}" in installer
    assert "OutputBaseFilename=SRS-Setup-1.0.1-Windows-x64" in installer


def test_visual_regressions_keep_track_map_and_zero_state_consistent():
    """实机审计发现的轨道串线、地图卸载竞态和零数据漏斗不得回归。"""
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    obstacle = (ROOT / "frontend" / "src" / "pages" / "ObstacleAnalysis.tsx").read_text(encoding="utf-8")
    site_map = (ROOT / "frontend" / "src" / "components" / "SiteMap.tsx").read_text(encoding="utf-8")
    screen = (ROOT / "frontend" / "src" / "pages" / "DashboardScreen.tsx").read_text(encoding="utf-8")

    assert "污染场地监管系统" not in app
    assert 'item.track === expectedTrack' in obstacle
    assert 'item.diagnosis_method === "kos"' in obstacle
    assert "诊断已完成,请注意以下数据质量提示" not in obstacle
    assert "展开其余" in obstacle
    assert "coordPane" not in site_map
    assert "mapRef.current !== map" in site_map
    assert "window.clearTimeout(fitTimer)" in site_map
    assert 'scope === "overview"' in site_map
    assert "map.setView([34, 104], zoom" in site_map
    assert "maxZoom: 18" in site_map
    assert "hasFunnelData" in screen
    assert 'description="暂无工作流数据"' in screen


def test_ssui_controls_and_economic_form_remain_readable():
    analysis = (ROOT / "frontend" / "src" / "pages" / "SSUIAnalysis.tsx").read_text(encoding="utf-8")
    drawer = (ROOT / "frontend" / "src" / "components" / "EconomicDataDrawer.tsx").read_text(encoding="utf-8")
    picker = (ROOT / "frontend" / "src" / "components" / "SitePicker.tsx").read_text(encoding="utf-8")

    assert "selectWidth={360}" in analysis
    assert "评价用途：" in analysis
    assert "允许区域代理（参考评价）" in analysis
    assert "selectWidth?: number" in picker
    assert "width={860}" in drawer
    assert "<Row gutter={[12, 0]}>" in drawer


def test_method_indicator_counts_do_not_mix_reconstruction_with_ssui():
    """方法文件表2.10/2.11为28/110项；第三章SSUI才是25项。"""
    params = json.loads((ROOT / "ml" / "params" / "evaluation_params.json").read_text(encoding="utf-8"))
    reconstruction = params["reconstruction"]
    assert len(reconstruction["production"]["indicator_weights"]) == 28
    assert len(reconstruction["ecology"]["indicator_weights"]) == 110
    assert len(params["ssui"]["production"]["meta_weights_25"]) == 25
    assert len(params["ssui"]["ecology"]["meta_weights_25"]) == 25
