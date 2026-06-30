"""验证 load_latest 双轨路由修复(2026-06-26 裴总打通要求)。

修复前(实测): track='prod'→op_prod(旧+错块), track='eco'→op_eco ✗
修复后预期: track='prod'→lake_prod_full, track='eco'→lake_eco_full ✓
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml", "models")))
from rf_barrier import load_latest  # noqa: E402

print("=== load_latest 双轨路由修复验证 ===")
all_ok = True
for t in [None, "prod", "eco"]:
    b = load_latest(track=t)
    if b is None:
        print(f"track={t!r:6} → None (无模型)")
        all_ok = False
        continue
    v, blk = b["version"], b.get("block")
    strat = b.get("feature_strategy", "?")
    if t is None:
        ok, expect = True, "(字典序最后, 兼容旧调用)"
    else:
        ok = bool(blk and f"_{t}_" in blk and "_full" in blk and "_lake_" in ("_" + blk + "_"))
        expect = f"lake_{t}_full"
        if not ok:
            all_ok = False
    flag = "✓" if ok else "✗"
    print(f"track={t!r:6} → {flag}  version={v}")
    print(f"           block={blk}  strategy={strat}  预期:{expect}")

print(f"\n{'✓ 双轨路由修复验证通过' if all_ok else '✗ 仍有路由问题'}")
