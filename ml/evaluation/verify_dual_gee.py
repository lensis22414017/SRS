"""验证(模块6): 防泄漏自检 + AUC区间 + load_latest路由 + SHAP可追溯。

项目组铁律验证: X_barrier 0污染物列(红线) / AUC 0.8-0.95(绿) / load_latest返回_barrier_gee(非旧_lake_full泄漏)。
17真实场地回归用 scripts/test_dual_track_diagnosis_e2e.py(已有waveF脚本, 需backend启动)。
"""
import os
import sys
import json
import glob

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
sys.path.insert(0, os.path.join(ROOT, "ml", "etl"))
sys.path.insert(0, os.path.join(ROOT, "ml", "explain"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from build_dual_track_training import _is_pollutant_col  # noqa: E402


def _auc_flag(auc):
    """AUC区间标记: <0.70随机 / >0.98疑泄漏 / 0.8-0.95目标绿 / 其他黄。"""
    if auc < 0.70:
        return "RED_TOO_LOW_RANDOM"
    if auc > 0.98:
        return "RED_SUSPECT_LEAKAGE"
    if 0.80 <= auc <= 0.95:
        return "GREEN_TARGET"
    return "YELLOW_BORDERLINE"

SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")
ARTIFACTS = os.path.join(ROOT, "ml", "artifacts")


def verify_leakage_free():
    """防泄漏自检: X_barrier 0污染物列(红线)。"""
    print("\n[1] 防泄漏自检")
    path = os.path.join(SPLIT_DIR, "train_X_barrier.csv")
    if not os.path.exists(path):
        print(f"  ⚠️ 未找到 {path}, 跳过(先跑build_dual_track)")
        return None
    x_cols = list(pd.read_csv(path, nrows=0).columns)
    violations = [c for c in x_cols if _is_pollutant_col(c)]
    passed = len(violations) == 0
    print(f"  X_barrier 特征数: {len(x_cols)}")
    print(f"  污染物列检出: {len(violations)} {'✅ 通过' if passed else '🔴 失败:' + str(violations)}")
    return passed


def verify_auc_range():
    """AUC区间: 用CV AUC(防泄漏训练集内性能)作主判断, 测试集AUC作跨文献泛化参考。
    CV 0.8-0.95绿/<0.7红随机/>0.98红泄漏; 测试集低=跨文献group-split泛化弱(诚实, 非泄漏)。"""
    print("\n[2] AUC区间检查(CV=防泄漏训练集内主指标, 测试集=跨文献泛化参考)")
    results = {}
    for track in ["prod", "eco"]:
        metas = sorted(glob.glob(os.path.join(
            ARTIFACTS, f"rf_barrier_factor_zzv0.2_*_dual_{track}_barrier_gee.meta.json")))
        if not metas:
            print(f"  {track}: 未找到模型meta(先跑train_dual_gee)")
            results[track] = None
            continue
        with open(metas[-1], encoding="utf-8") as f:
            m = json.load(f)
        cv = m["metrics"]["cv_auc_mean"]
        test_auc = m["metrics"]["auc"]
        flag = _auc_flag(cv)
        print(f"  {track}: CV AUC={cv} ({flag}) | 测试集AUC={test_auc}(跨文献泛化参考)")
        results[track] = m["metrics"]
    return results


def verify_load_latest_route():
    """load_latest(track) 返回 _barrier_gee 模型(非旧_lake_full泄漏)。"""
    print("\n[3] load_latest 路由验证")
    try:
        from rf_barrier import load_latest
    except ImportError:
        print("  ⚠️ rf_barrier 不可导入, 跳过")
        return None
    results = {}
    for track in ["prod", "eco"]:
        b = load_latest(track=track)
        ver = b.get("version", "")
        is_gee = "_barrier_gee" in ver
        print(f"  {track}: version={ver} {'✅ _barrier_gee' if is_gee else '🔴 非GEE模型'}")
        results[track] = {"version": ver, "is_barrier_gee": is_gee}
    return results


def verify_shap_traceable():
    """SHAP top因子绑定特征值(可追溯)。"""
    print("\n[4] SHAP可追溯")
    path = os.path.join(SPLIT_DIR, "test_X_barrier.csv")
    if not os.path.exists(path):
        print(f"  ⚠️ 未找到 {path}, 跳过")
        return None
    try:
        from rf_barrier import load_latest
        from shap_service import explain
    except ImportError:
        print("  ⚠️ 模块不可导入, 跳过")
        return None
    X = pd.read_csv(path).head(50)
    b = load_latest(track="prod")
    sh = explain(b["model"], X)
    g = sh["global"]
    print(f"  global SHAP 因子数: {len(g)}")
    print(f"  top5: {[(x['feature'], round(x['mean_abs_shap'], 4)) for x in g[:5]]}")
    local0 = sh["local"].get(0, [])
    traced = all("feature_value" in x for x in local0[:5]) if local0 else False
    print(f"  local top5 特征值可追溯: {'✅' if traced else '🔴'}")
    return traced


def main():
    print("=" * 64)
    print("双轨防泄漏模型验证")
    print("=" * 64)
    ok = verify_leakage_free()
    aucs = verify_auc_range()
    routes = verify_load_latest_route()
    shap_ok = verify_shap_traceable()

    print("\n" + "=" * 64)
    print("验证总结")
    print("=" * 64)
    print(f"  防泄漏自检: {'✅' if ok else '🔴'}")
    for t, m in (aucs or {}).items():
        if m:
            print(f"  {t} CV AUC: {m['cv_auc_mean']} ({_auc_flag(m['cv_auc_mean'])}) | 测试集{m['auc']}(跨文献)")
    if routes:
        for t, r in routes.items():
            print(f"  {t} 路由: {'✅_barrier_gee' if r['is_barrier_gee'] else '🔴'}")
    print(f"  SHAP可追溯: {'✅' if shap_ok else '🔴'}")
    print("\n17真实场地回归: 运行 scripts/test_dual_track_diagnosis_e2e.py(需backend启动)")


if __name__ == "__main__":
    main()
