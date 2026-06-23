"""train.py (L2 — agent 迭代研究对象) — 推荐引擎有机匹配。

agent 修改 ml/recommend/engine.py 的有机因子识别/匹配, 由 prepare.evaluate() 评估。
本文件是研究对象的"参数化声明", 真实被服务调用的是 ml/recommend/engine.py。

baseline 关键参数(对应 engine.py 当前值):
  METAL = {"砷","铅","铜","锌","镉","铬","汞","镍","铬(六价)","六价铬"}
  ORGANIC_HINT = ("PAHs","PCBs","OCPs","PAEs","石油烃","TPH","苯","氯")  # ← 缺中文!

缺口: 切片有机因子名为中文(多环芳烃总量/苯并芘/有机氯农药/DDT类/多氯联苯),
      ORGANIC_HINT 无中文 token → _factor_class=other → 不进推荐匹配 → OP 0 推荐。

迭代方向(见 program.md): 扩展 ORGANIC_HINT / 匹配逻辑 / 技术库适用污染物。
"""

# agent 迭代时, 直接改 ml/recommend/engine.py 对应常量/函数;
# 此处仅作 PARAMS 影子记录, 便于 EXPERIMENTS.md 追溯。
PARAMS = {
    "ORGANIC_HINT_baseline": ["PAHs", "PCBs", "OCPs", "PAEs", "石油烃", "TPH", "苯", "氯"],
    "ORGANIC_HINT_target": ["PAHs", "PCBs", "OCPs", "PAEs", "石油烃", "TPH", "苯", "氯",
                            "多环", "芳烃", "苯并芘", "有机氯", "DDT", "多氯联苯", "农药", "菲", "芘"],
}
