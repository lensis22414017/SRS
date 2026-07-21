"""
从真实数据集采样 + RF 增强，生成 demo_sites 场地数据。
严格按省份分组，保证坐标正确，文件名合理。
"""
import pandas as pd
import numpy as np
import os, glob, random
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer

np.random.seed(42)
random.seed(42)

# === 1. 加载 ===
SRC = r'C:\Users\曾鸿\Desktop\000\论文中真实数据集-merged_std33,zh .xlsx'
DEST = r'C:\Users\曾鸿\Desktop\SRS-round10\data\demo_sites'
df = pd.read_excel(SRC, sheet_name='china', header=0)
print(f"加载: {len(df)}行 x {len(df.columns)}列")

# === 2. 归类 ===
def classify(pt):
    pt = str(pt).strip().upper()
    if pt in ['HM', 'HEAVY_METAL']:
        return 'heavy_metal'
    if pt in ['OP', 'ORGANIC', 'PAH', 'OCP', 'PCN', 'PFAS', 'PBDE',
              'ANTIBIOTICS', 'PAH+PCB', 'PAH+OCP', 'PAH+OCP+PCB']:
        return 'organic'
    if pt in ['HM+OP', 'HM+PAH', 'OP+HM']:
        return 'composite'
    if 'HM' in pt and ('OP' in pt or 'PAH' in pt or 'OCP' in pt):
        return 'composite'
    return 'unknown'

df['type'] = df['Pollution_Type'].apply(classify)
print(f"归类: {df['type'].value_counts().to_dict()}")

# === 3. 省份统一中文 ===
prov_map = {
    'Beijing': '北京', '北京': '北京', 'Tianjin': '天津', '天津': '天津',
    'Hebei': '河北', '河北': '河北', 'Shanxi': '山西', '山西': '山西',
    'Inner Mongolia': '内蒙古', '内蒙古': '内蒙古',
    'Liaoning': '辽宁', '辽宁': '辽宁', 'Jilin': '吉林', '吉林': '吉林',
    'Heilongjiang': '黑龙江', '黑龙江': '黑龙江',
    'Shanghai': '上海', '上海': '上海',
    'Jiangsu': '江苏', '江苏': '江苏', 'Zhejiang': '浙江', '浙江': '浙江',
    'Anhui': '安徽', '安徽': '安徽', 'Fujian': '福建', '福建': '福建',
    'Jiangxi': '江西', '江西': '江西', 'Shandong': '山东', '山东': '山东',
    'Henan': '河南', '河南': '河南', 'Hubei': '湖北', '湖北': '湖北',
    'Hunan': '湖南', '湖南': '湖南', 'Guangdong': '广东', '广东': '广东',
    'Guangxi': '广西', '广西': '广西', 'Hainan': '海南', '海南': '海南',
    'Chongqing': '重庆', '重庆': '重庆', 'Sichuan': '四川', '四川': '四川',
    'Guizhou': '贵州', '贵州': '贵州', 'Yunnan': '云南', '云南': '云南',
    'Tibet (Tibet Autonomous Region)': '西藏', '西藏': '西藏',
    'Shaanxi': '陕西', '陕西': '陕西', 'Gansu': '甘肃', '甘肃': '甘肃',
    'Qinghai': '青海', '青海': '青海', 'Ningxia': '宁夏', '宁夏': '宁夏',
    'Xinjiang': '新疆', '新疆': '新疆',
}
df['prov_cn'] = df['Province'].map(prov_map).fillna(df['Province'])

# === 4. 列定义 ===
CORE_HM = ['Cd_mgkg', 'Pb_mgkg', 'As_mgkg', 'Cu_mgkg', 'Zn_mgkg', 'Ni_mgkg', 'Cr_mgkg', 'Hg_mgkg']
CORE_ORG = ['Sum_PAH_ngg', 'BaP_ngg', 'SumPCB_ngg', 'SumDDTs_ngg', 'SumHCHs_ngg']
META = ['Latitude', 'Longitude', 'pH', 'OC_pct', 'LandUse', 'SamplingDepth', 'City']

COL_RENAME = {
    'Latitude': '纬度', 'Longitude': '经度', 'pH': 'pH', 'OC_pct': '有机质(%)',
    'LandUse': '土地利用', 'SamplingDepth': '采样深度(cm)', 'City': '城市',
    'Cd_mgkg': '镉_Cd(mg/kg)', 'Pb_mgkg': '铅_Pb(mg/kg)', 'As_mgkg': '砷_As(mg/kg)',
    'Cu_mgkg': '铜_Cu(mg/kg)', 'Zn_mgkg': '锌_Zn(mg/kg)', 'Ni_mgkg': '镍_Ni(mg/kg)',
    'Cr_mgkg': '铬_Cr(mg/kg)', 'Hg_mgkg': '汞_Hg(mg/kg)',
    'Sum_PAH_ngg': '多环芳烃_PAHs(ng/g)', 'BaP_ngg': '苯并芘_BaP(ng/g)',
    'SumPCB_ngg': '多氯联苯_PCBs(ng/g)', 'SumDDTs_ngg': '滴滴涕_DDTs(ng/g)',
    'SumHCHs_ngg': '六六六_HCHs(ng/g)',
}

# === 5. RF 插补 ===
def rf_impute(data, target_cols):
    data = data.copy()
    # 保护字符串列
    str_cols = ['City', 'LandUse', 'Province', 'prov_cn', 'Pollution_Type', 'Source', 'DOI', 'Country', 'SampleID', 'SiteDescription']
    str_data = {}
    for c in str_cols:
        if c in data.columns:
            str_data[c] = data[c].copy()
    # 所有数值列强制转 float
    for c in data.columns:
        if c in str_cols:
            continue
        if data[c].dtype == object:
            data[c] = pd.to_numeric(data[c], errors='coerce')
    num_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    available = [c for c in target_cols if c in data.columns]

    for target in available:
        if data[target].isna().sum() == 0:
            continue
        features = [c for c in num_cols if c != target and data[c].notna().sum() > 10]
        if len(features) < 2:
            data[target] = data[target].fillna(data[target].median() if not data[target].isna().all() else 0)
            continue

        train_mask = data[target].notna() & data[features].notna().all(axis=1)
        if train_mask.sum() < 10:
            data[target] = data[target].fillna(data[target].median() if not data[target].isna().all() else 0)
            continue

        X_train = data.loc[train_mask, features]
        y_train = data.loc[train_mask, target]
        imp = SimpleImputer(strategy='median')
        X_train_imp = imp.fit_transform(X_train)

        rf = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
        rf.fit(X_train_imp, y_train)

        predict_mask = data[target].isna()
        if predict_mask.sum() > 0:
            X_pred = data.loc[predict_mask, features]
            X_pred_imp = imp.transform(X_pred.fillna(X_pred.median()))
            data.loc[predict_mask, target] = rf.predict(X_pred_imp)

    # 剩余用中位数
    for c in data.select_dtypes(include=[np.number]).columns:
        if data[c].isna().any():
            data[c] = data[c].fillna(data[c].median() if not data[c].isna().all() else 0)

    # 恢复字符串列
    for c, vals in str_data.items():
        if c in data.columns:
            data[c] = vals

    return data


# === 6. 生成 ===
def gen_sites(df_subset, target_cols, n_sites, type_label):
    generated = []
    all_cols = META + target_cols
    available_cols = [c for c in all_cols if c in df_subset.columns]
    key_cols = [c for c in target_cols if c in df_subset.columns]

    df_clean = df_subset.dropna(subset=key_cols, how='all')
    prov_groups = list(df_clean.groupby('prov_cn'))
    valid_provs = [(p, g) for p, g in prov_groups if len(g) >= 25]
    random.shuffle(valid_provs)

    for i in range(n_sites):
        idx = i % max(len(valid_provs), 1)
        prov, group = valid_provs[idx]

        n_rows = min(random.randint(25, 50), len(group))
        site = group.sample(
            n=n_rows,
            replace=(n_rows > len(group)),
            random_state=42 + i
        ).reset_index(drop=True)

        keep = [c for c in available_cols if c in site.columns]
        site = site[keep].copy()

        # RF 插补
        site = rf_impute(site, key_cols)

        # 坐标验证 (Latitude=纬度 18-54, Longitude=经度 73-136)
        if 'Latitude' in site.columns:
            site['Latitude'] = pd.to_numeric(site['Latitude'], errors='coerce')
            site = site[site['Latitude'].between(15, 55)]
        if 'Longitude' in site.columns:
            site['Longitude'] = pd.to_numeric(site['Longitude'], errors='coerce')
            site = site[site['Longitude'].between(70, 140)]

        if len(site) < 15:
            site = group.sample(n=min(30, len(group)), replace=True, random_state=142 + i * 7).reset_index(drop=True)
            keep2 = [c for c in available_cols if c in site.columns]
            site = site[keep2].copy()
            site = rf_impute(site, key_cols)

        # 序号 + 采样点编号
        site.insert(0, '序号', range(1, len(site) + 1))
        prefix = prov[:2] if len(prov) >= 2 else prov
        site.insert(1, '采样点编号',
                    [f'{prefix}-{type_label[:2]}{i+1:02d}-{j+1:03d}'
                     for j in range(len(site))])

        # 重命名列
        site.rename(
            columns={k: v for k, v in COL_RENAME.items() if k in site.columns},
            inplace=True
        )

        # 城市名
        city_val = prov
        if '城市' in site.columns:
            cvs = site['城市'].dropna()
            city_val = str(cvs.iloc[0]) if len(cvs) > 0 else prov

        # 文件名
        fname = f'{prov}_{city_val}_{type_label}_{i+1:02d}.xlsx'
        fpath = os.path.join(DEST, fname)
        site.to_excel(fpath, index=False)
        generated.append((fname, len(site), len(site.columns)))

    return generated


# === 7. 清空并生成 ===
for f in glob.glob(os.path.join(DEST, '*.xlsx')):
    try:
        os.remove(f)
    except Exception:
        pass
for f in glob.glob(os.path.join(DEST, '~$*')):
    try:
        os.remove(f)
    except Exception:
        pass

total = 0
for ptype, tlabel, tcols, n in [
    ('heavy_metal', '重金属', CORE_HM, 10),
    ('organic', '有机污染', CORE_ORG, 10),
    ('composite', '复合污染', CORE_HM + CORE_ORG, 10),
]:
    subset = df[df['type'] == ptype]
    print(f"\n=== {tlabel} (源{len(subset)}行) ===")
    res = gen_sites(subset, tcols, n, tlabel)
    for name, rows, cols in res:
        print(f"  ✅ {name} ({rows}行 x {cols}列)")
    total += len(res)

print(f"\n总计: {total} 个场地")
