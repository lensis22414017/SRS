# OP 因子命名对齐表: ORG_COLS_MAP(merged 中文名) → 新阈值库 factor 名
# B(OCR交叉验证+OP二类命名对齐, 2026-06-24)
# merged 有机类中文名 vs 阈值库(生产/生态因子名) vs 权威 CSV 命名, 缺项标注

# 字段:
# merged_chinese   merged英文列     库生产factor(一类严)   库生态factor(二类宽)   权威CSV(factor_name)   对齐状态
op_alignment = [
    ("多环芳烃总量",   "Sum_PAH_ngg",    None,                    None,                    "Sum_PAH",             "总量无单体对应,需拆分PAH单体"),
    ("苯并芘",         "BaP_ngg",        "苯并[a]芘",              "苯并[a]芘",              "Benzo[a]pyrene",      "✓ 对齐(命名变异'苯并[a]芘'vs'苯并芘')"),
    ("有机氯农药",     "SumOCP_ngg",     None,                    None,                    None,                  "总量无单体对应"),
    ("DDT类",          "SumDDTs_ngg",    "滴滴涕",                 "滴滴涕",                  "DDT",                 "✓ 对齐(命名'滴滴涕'vs'DDT类')"),
    ("多氯联苯",       "SumPCB_ngg",     "多氯联苯(总量)",         "多氯联苯(总量)",           "PCB_total",           "✓ 对齐(命名'多氯联苯(总量)'vs'多氯联苯')"),
    ("六六六总量",     "SumHCHs_ngg",    "α-六六六",               "α-六六六",                "alpha-HCH",           "⚠ 单体vs总量:库存α-六六六/β/γ单体,无总量; 取最严单体当总阈值(保守)"),
    ("邻苯二甲酸酯",   "SumPAE_ugkg",    "邻苯二甲酸二(2-乙基己基)酯", None,                "DEHP",                "⚠ 单体vs总量,ugkg→ngg需单位转换"),
    ("多溴二苯醚",     "SumPBDE_ngg",    "多溴联苯(总量)",         "多溴联苯(总量)",           "PBDE_total",          "⚠ 命名不对齐(多溴二苯醚vs多溴联苯,同类不同族)"),
    ("全氟化合物",     "SumPFAS_ngg",    None,                    None,                    None,                  "✗ 缺-库无PFAS阈值,需补充(PFOA/PFOS)"),
    ("石油烃",         "TPH_ngg",        "石油烃(C10-C40)",        "石油烃(C10-C40)",        "TPH_C10C40",          "✓ 对齐(命名带碳数)"),
    ("高分子量PAH",    "HMWPAH_ngg",     None,                    None,                    None,                  "✗ 缺-无分高分子量/低分子量阈值,需按PAH单体拆分"),
    ("低分子量PAH",    "LMWPAH_ngg",     None,                    None,                    None,                  "✗ 缺-同上"),
]

# 对齐后生产库OP阈值(合并一类+单体):
# pad_factor → threshold_mgkg
# 单体: 苯并[a]芘0.55(一类)/滴滴涕1.0(一类)/多氯联苯0.2/α-六六六0.4/石油烃826等
# 总量(无单体对应): 暂用权威CSV一类ng/g值(生态二类待Wave B OCR原文核定)
# GB15618 补充: 六六六总量0.1/DDT总量0.1/BaP0.55 (农用地, mg/kg, 全国通用)

if __name__ == "__main__":
    aligned = sum(1 for _, _, _, _, _, s in op_alignment if s.startswith("✓"))
    partial = sum(1 for _, _, _, _, _, s in op_alignment if s.startswith("⚠"))
    missing = sum(1 for _, _, _, _, _, s in op_alignment if s.startswith("✗"))
    print(f"OP 命名对齐: {aligned}✓ {partial}⚠ {missing}✗ (共{len(op_alignment)}项)")
