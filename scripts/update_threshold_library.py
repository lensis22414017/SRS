#!/usr/bin/env python3
"""update_threshold_library.py — 批量补充标准阈值到 standard_thresholds 表

来源：
- NY/T 1749-2009 南方耕地土壤肥力
- 全国第二次土壤普查养分分级
- CJ/T 340-2016 绿化种植土壤
- TD/T1036-2013 土壤复垦质量
- EPA RSL 2024（DoD PFAS）
- GB36600 交叉轨补充（生产轨也能用的建设用地有机物限值）
"""

import sqlite3, os, sys

DB_PATH = os.path.join(os.environ['APPDATA'], 'SRS', 'srs.db')

def connect():
    return sqlite3.connect(str(DB_PATH))

def get_fd_map(db):
    """构建 {factor_name_lower: factor_id} 和 {factor_code: factor_id}"""
    m = {}
    for r in db.execute('SELECT id, factor_name, factor_code FROM factor_dictionary'):
        for key in [str(r[1]).strip().lower(), str(r[2]).strip().lower()]:
            if key:
                m[key] = r[0]
    return m

def insert_standard(db, fd_map, factor_query: str, standard_code: str, standard_name: str,
                    land_use_type: str, screening_value: float, unit: str,
                    intervention_value=None, ph_condition="not_applicable",
                    exposure_scenario="通用", version="2018"):
    """幂等插入一条标准阈值。factor_query 是中文因子名或 canonical code。"""
    fid = fd_map.get(factor_query.lower().strip())
    if not fid:
        print(f"  [SKIP] 因子 '{factor_query}' 不在 factor_dictionary 中")
        return False

    # 检查是否已存在
    existing = db.execute(
        'SELECT id FROM standard_thresholds WHERE factor_id=? AND standard_code=? AND land_use_type=?',
        (fid, standard_code, land_use_type)
    ).fetchone()
    if existing:
        return False  # 幂等跳过

    db.execute(
        'INSERT INTO standard_thresholds '
        '(factor_id, factor_name, land_use_type, standard_code, standard_name, '
        'screening_value, intervention_value, unit, pH_condition, exposure_scenario, version) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (fid, factor_query, land_use_type, standard_code, standard_name,
         screening_value, intervention_value, unit, ph_condition, exposure_scenario, version)
    )
    return True

def main():
    db = connect()
    fd_map = get_fd_map(db)

    n_total = 0

    # ════════════════════════════════════════════
    # A. NY/T 1749-2009 南方耕地土壤肥力
    # ════════════════════════════════════════════
    print("=== A. NY/T 1749-2009 肥力标准 ===")
    fertility = [
        # (因子名, 用地类型, 筛选值, 单位)
        ("全氮", "旱地", 1.0, "g/kg"),
        ("全氮", "水田", 1.2, "g/kg"),
        ("有效磷", "旱地", 7.5, "mg/kg"),
        ("有效磷", "水田", 12.5, "mg/kg"),
        ("速效钾", "旱地", 80.0, "mg/kg"),
        ("速效钾", "水田", 100.0, "mg/kg"),
        ("阳离子交换量", "旱地", 12.0, "cmol(+)/kg"),
        ("阳离子交换量", "水田", 15.0, "cmol(+)/kg"),
    ]
    for fn, lu, sv, u in fertility:
        ok = insert_standard(db, fd_map, fn,
                             "NY/T 1749-2009", "南方地区耕地土壤肥力诊断与评价",
                             lu, sv, u, version="2009")
        if ok:
            print(f"  + {fn} ({lu}): {sv} {u}")
            n_total += 1

    # ════════════════════════════════════════════
    # B. 全国第二次土壤普查养分分级
    # ════════════════════════════════════════════
    print("\n=== B. 全国二普养分分级 ===")
    npk = [
        ("全磷", "通用", 0.4, "g/kg", "中等下限 (0.4 g/kg)"),
        ("全钾", "通用", 10.0, "g/kg", "中等下限 (10 g/kg)"),
        ("水解性氮", "通用", 60.0, "mg/kg", "贫乏上限 (<60 mg/kg 为贫乏)"),
        ("有机质", "通用", 6.0, "g/kg", "贫乏下限 (SOM=6 g/kg, OC≈0.35%)"),
    ]
    for fn, lu, sv, u, note in npk:
        ok = insert_standard(db, fd_map, fn,
                             "全国二普", f"全国第二次土壤普查养分分级 — {note}",
                             lu, sv, u, version="1979")
        if ok:
            print(f"  + {fn}: {sv} {u} ({note})")
            n_total += 1

    # ════════════════════════════════════════════
    # C. CJ/T 340-2016 绿化种植土壤
    # ════════════════════════════════════════════
    print("\n=== C. CJ/T 340-2016 绿化种植土壤 ===")
    cjt = [
        ("有机质", "普通绿化区", 12.0, "g/kg", "下限 (12-80 g/kg)"),
        ("水解性氮", "普通绿化区", 40.0, "mg/kg", "下限 (40-200 mg/kg)"),
        ("有效磷", "普通绿化区", 5.0, "mg/kg", "下限 (5-60 mg/kg)"),
        ("速效钾", "普通绿化区", 60.0, "mg/kg", "下限 (60-300 mg/kg)"),
        ("阳离子交换量", "普通绿化区", 10.0, "cmol(+)/kg", "下限 (≥10)"),
        ("电导率", "普通绿化区", 0.15, "mS/cm", "下限 (0.15-3.0 mS/cm)"),
        ("电导率", "普通绿化区", 3.0, "mS/cm", "上限 (0.15-3.0 mS/cm)"),
    ]
    for fn, lu, sv, u, note in cjt:
        ok = insert_standard(db, fd_map, fn,
                             "CJ/T 340-2016", f"绿化种植土壤 — {note}",
                             lu, sv, u, version="2016")
        if ok:
            print(f"  + {fn} ({lu}): {sv} {u}")
            n_total += 1

    # ════════════════════════════════════════════
    # D. TD/T1036-2013 土壤复垦质量
    # ════════════════════════════════════════════
    print("\n=== D. TD/T1036-2013 土壤复垦 ===")
    tdt = [
        ("容重", "通用", 1.5, "g/cm³", "上限 (≤1.5, 多数区域通用)"),
        ("电导率", "通用", 2.0, "mS/cm", "上限 (≤2 dS/m, 多数区域通用)"),
    ]
    for fn, lu, sv, u, note in tdt:
        ok = insert_standard(db, fd_map, fn,
                             "TD/T1036-2013", f"土地复垦质量控制标准 — {note}",
                             lu, sv, u, version="2013")
        if ok:
            print(f"  + {fn}: {sv} {u}")
            n_total += 1

    # ════════════════════════════════════════════
    # E. EPA RSL 2024 国际参考
    # ════════════════════════════════════════════
    print("\n=== E. EPA RSL 2024 国际参考 ===")
    epa = [
        ("全氟化合物", "住宅用地", 0.00007, "mg/kg", "EPA RSL 2024 PFOA DoD 筛选值 (0.07 μg/kg)"),
    ]
    for fn, lu, sv, u, note in epa:
        ok = insert_standard(db, fd_map, fn,
                             "EPA RSL 2024", f"美国 EPA 区域筛选水平 — {note}",
                             lu, sv, u, version="2024")
        if ok:
            print(f"  + {fn}: {sv} {u}")
            n_total += 1

    # ════════════════════════════════════════════
    # F. GB36600 交叉轨补充（让生产轨也能用建设用地有机物阈值）
    # ════════════════════════════════════════════
    print("\n=== F. GB36600 交叉轨补充（生产用地也可参考的建设用地限值）===")
    cross = [
        ("苯并[a]芘", "生产用地参考", 0.55, "mg/kg"),
        ("DDT类", "生产用地参考", 1.0, "mg/kg"),
        ("六六六", "生产用地参考", 0.4, "mg/kg"),
        ("多氯联苯", "生产用地参考", 0.2, "mg/kg"),
        ("多环芳烃总量", "生产用地参考", 0.55, "mg/kg"),
        ("石油烃", "生产用地参考", 826.0, "mg/kg"),
        ("有机氯农药", "生产用地参考", 1.0, "mg/kg"),
    ]
    for fn, lu, sv, u in cross:
        ok = insert_standard(db, fd_map, fn,
                             "GB 36600-2018", "建设用地土壤污染风险管控标准（一类用地筛选值，交叉轨参考）",
                             lu, sv, u,
                             ph_condition="not_applicable",
                             exposure_scenario="一类用地（敏感）")
        if ok:
            print(f"  + {fn}: {sv} {u}")
            n_total += 1

    db.commit()
    print(f"\n=== 完成: 新增 {n_total} 条阈值记录 ===")

    # ════════════════════════════════════════════
    # 重建 threshold_rules
    # ════════════════════════════════════════════
    print("\n=== 重建 threshold_rules ===")
    db.execute('DELETE FROM threshold_rules')
    n_tr = 0

    for r in db.execute(
        'SELECT id, factor_id, factor_name, land_use_type, standard_code, standard_name, '
        'screening_value, intervention_value, unit, pH_condition, exposure_scenario '
        'FROM standard_thresholds WHERE screening_value IS NOT NULL'
    ):
        fid = r[1] or 0
        fn = r[2] or ''
        lu = r[3] or ''
        sc = r[4] or ''
        sn = r[5] or ''
        sv = r[6]
        iv = r[7]
        unit = r[8] or ''
        ph = r[9] or ''
        exp = r[10] or ''

        scope = 'ecology' if '生态' in str(lu) or '36600' in str(sc) else 'production'
        land = lu

        try:
            db.execute(
                'INSERT INTO threshold_rules '
                '(factor_id, application_scenario, applicable_scope, land_type, '
                'threshold_min, threshold_max, unit, threshold_original, standard_source, version) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (fid, exp, scope, land, sv, iv, unit,
                 f'{fn} [{sn}] pH{ph}',
                 sc, 'V1.0')
            )
            n_tr += 1
        except Exception as e:
            pass

    db.commit()
    total_st = db.execute('SELECT COUNT(*) FROM standard_thresholds').fetchone()[0]
    print(f"standard_thresholds: {total_st} 条")
    print(f"threshold_rules: {n_tr} 条 (重建)")
    db.close()

if __name__ == '__main__':
    main()
