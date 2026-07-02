"""P1-4: 字段泄露审计。训练前强制执行, 发现禁止字段入X_all直接报错终止。"""
import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 禁止进入模型的字段模式(B/R/W/KOS/OI/threshold/exceedance等目标派生)
FORBIDDEN_PATTERNS = [
    "标签", "超标", "severity", "rule_", "B_", "R_", "KOS", "OI_",
    "threshold", "exceedance", "_label", "_target", "_score"
]
# 禁止的精确字段名
FORBIDDEN_EXACT = {
    "标签_生产", "标签_生态", "标签", "label", "label_prod", "label_eco",
    "id_DOI", "id_Source",  # 分组键, 不是特征
}


def audit_features(feature_cols: list, verbose: bool = True) -> dict:
    """审计特征列, 返回 {passed, forbidden_found, details}。
    如果发现禁止字段, passed=False, 调用方应终止训练。"""
    found = []
    for c in feature_cols:
        if c in FORBIDDEN_EXACT:
            found.append({"column": c, "reason": "精确匹配禁止字段(目标/分组/规则派生)"})
            continue
        for p in FORBIDDEN_PATTERNS:
            if p in c:
                found.append({"column": c, "reason": f"匹配禁止模式 '{p}'"})
                break
    result = {"passed": len(found) == 0, "n_checked": len(feature_cols),
              "n_forbidden": len(found), "forbidden": found}
    if verbose:
        status = "✅ 通过" if result["passed"] else "🔴 失败"
        print(f"[泄露审计] {status}: 检查{result['n_checked']}列, 发现{result['n_forbidden']}个禁止字段")
        for f in found[:10]:
            print(f"  禁止: {f['column']} ({f['reason']})")
    return result


if __name__ == "__main__":
    # 测试: 用model_ready_schema的列做审计
    schema_path = os.path.join(ROOT, "data", "reports", "model_ready_schema.json")
    if os.path.exists(schema_path):
        schema = json.load(open(schema_path, encoding="utf-8"))
        # 模拟: 用schema的sample列做测试
        test_cols = schema.get("model_ready_sample", [])
        result = audit_features(test_cols)
        if not result["passed"]:
            print("\n🔴 审计失败! 禁止字段进入模型, 训练必须终止。")
            sys.exit(1)
        else:
            print("\n✅ 审计通过, 可进入训练。")
    else:
        print("未找到 model_ready_schema.json, 跳过测试")
