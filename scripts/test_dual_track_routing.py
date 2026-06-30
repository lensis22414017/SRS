"""测试双轨模型路由(load_latest track)是否正确选 Wave E 模型。

裴总要求: 两套阈值模型和诊断逻辑要打通。
验证: load_latest(track='prod'/'eco') 是否选到 lake_prod_full / lake_eco_full。
发现的疑似 bug: rf_barrier.py:92 过滤 endswith('_prod.joblib'),
但 Wave E 命名为 '_lake_prod_full.joblib' → 不匹配 → 路由失效回退字典序。
"""
import os

ARTIFACTS = os.path.join(os.path.dirname(__file__), "..", "ml", "artifacts")
MODEL_NAME = "rf_barrier_factor"


def list_cands():
    return sorted(f for f in os.listdir(ARTIFACTS)
                  if f.startswith(MODEL_NAME) and f.endswith(".joblib"))


def load_latest_select(cands, track=None):
    """复现 rf_barrier.load_latest 的选择逻辑(不 load 模型,只看选哪个文件)。"""
    if track:
        filt = [f for f in cands if f.endswith(f"_{track}.joblib")]
        cands = filt if filt else cands
    return cands[-1] if cands else None


def main():
    cands = list_cands()
    print(f"=== 全部模型 ({len(cands)}) ===")
    for c in cands:
        print(f"  {c}")
    print(f"\n=== load_latest track 路由测试 (rf_barrier.py:91-93 当前逻辑) ===")
    print("预期: prod→lake_prod_full, eco→lake_eco_full")
    print("实际若选非 _{track}_ 模型 = 路由失效\n")
    for t in [None, "prod", "eco"]:
        sel = load_latest_select(cands, t)
        if t is None:
            ok = True
            note = "(track=None, 字典序最后)"
        else:
            ok = bool(sel and f"_{t}_" in sel)
            note = "✓ 选对轨" if ok else f"✗ 路由失效(endswith _{t}.joblib 不匹配 Wave E 命名)"
        print(f"  track={t!r:6} → {sel}  {note}")


if __name__ == "__main__":
    main()
