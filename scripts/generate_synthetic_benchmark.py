"""生成 50 个中国区域化半合成场地 benchmark。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "synthetic"))

from monte_carlo import DEFAULT_REAL, generate_from_csv  # noqa: E402


if __name__ == "__main__":
    real_csv = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REAL
    res = generate_from_csv(real_csv)
    print("已生成:", os.path.relpath(res["sites"], ROOT))
    print("已生成:", os.path.relpath(res["samples"], ROOT))
    print("已生成:", os.path.relpath(res["manifest"], ROOT))
    print("场地数:", res["site_count"], "样点数:", res["sample_count"])
