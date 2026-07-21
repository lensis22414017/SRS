"""
v2: 完整指标体系（参考障碍因子集）
- 所有场地: pH, 有机质, CEC, 粒径, 容重, 土地利用 等通用指标
- HM 场地: + 8项重金属 | 有机物列→NaN
- OP 场地: + 5项有机物 | 重金属列→NaN  
- composite: + 全部
- RF 插补稀疏值
- 高德 API 不可用，但源数据坐标=省份已验证
"""
import pandas as pd
import numpy as np
import os, glob, random
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer

np.random.seed(42)
random.seed(42)

SRC = r'C:\Users\曾鸿\Desktop\000\论文中真实数据集-merged_std33,zh .xlsx'
DEST = r'C:\Users\曾鸿\Desktop\SRS-round10\data\demo_sites'

# === 1. 加载 ===
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

# 使用全部有效数据（不限类型）
all_valid = df[df['type'] != 'unknown']
print(f"有效数据: {len(all_valid)}行")
prov_map = {
    'Beijing':'北京','北京':'北京','Tianjin':'天津','天津':'天津',
    'Hebei':'河北','河北':'河北','Shanxi':'山西','山西':'山西',
    'Inner Mongolia':'内蒙古','内蒙古':'内蒙古',
    'Liaoning':'辽宁','辽宁':'辽宁','Jilin':'吉林','吉林':'吉林',
    'Heilongjiang':'黑龙江','黑龙江':'黑龙江',
    'Shanghai':'上海','上海':'上海','Jiangsu':'江苏','江苏':'江苏',
    'Zhejiang':'浙江','浙江':'浙江','Anhui':'安徽','安徽':'安徽',
    'Fujian':'福建','福建':'福建','Jiangxi':'江西','江西':'江西',
    'Shandong':'山东','山东':'山东','Henan':'河南','河南':'河南',
    'Hubei':'湖北','湖北':'湖北','Hunan':'湖南','湖南':'湖南',
    'Guangdong':'广东','广东':'广东','Guangxi':'广西','广西':'广西',
    'Hainan':'海南','海南':'海南','Chongqing':'重庆','重庆':'重庆',
    'Sichuan':'四川','四川':'四川','Guizhou':'贵州','贵州':'贵州',
    'Yunnan':'云南','云南':'云南',
    'Tibet (Tibet Autonomous Region)':'西藏','西藏':'西藏',
    'Shaanxi':'陕西','陕西':'陕西','Gansu':'甘肃','甘肃':'甘肃',
    'Qinghai':'青海','青海':'青海','Ningxia':'宁夏','宁夏':'宁夏',
    'Xinjiang':'新疆','新疆':'新疆',
}
df['prov_cn'] = df['Province'].map(prov_map).fillna(df['Province'])

# === 4. 全部列分类 ===
CORE_HM = ['Cd_mgkg','Pb_mgkg','As_mgkg','Cu_mgkg','Zn_mgkg','Ni_mgkg','Cr_mgkg','Hg_mgkg']
CORE_ORG = ['Sum_PAH_ngg','BaP_ngg','SumPCB_ngg','SumDDTs_ngg','SumHCHs_ngg']
# 通用指标：pH、有机质、肥力、物理性质（参考障碍因子集）
COMMON = [
    'pH_merged', 'OC_pct', 'CEC_cmolkg',
    'Sand_pct', 'Silt_pct', 'Clay_pct', 'SoilBD_gcm3',
    'LandUse', 'SamplingDepth', 'SoilTexture',
]
META_COLS = ['Latitude', 'Longitude', 'City']

# 所有需要的列（按存在性过滤）
ALL_NEEDED = META_COLS + CORE_HM + CORE_ORG + COMMON

COL_RENAME = {
    'Latitude':'纬度', 'Longitude':'经度', 'City':'城市',
    'pH_merged':'pH', 'OC_pct':'有机质(%)', 'CEC_cmolkg':'CEC(cmol/kg)',
    'Sand_pct':'砂粒(%)', 'Silt_pct':'粉粒(%)', 'Clay_pct':'黏粒(%)',
    'SoilBD_gcm3':'容重(g/cm³)', 'LandUse':'土地利用',
    'SamplingDepth':'采样深度(cm)', 'SoilTexture':'土壤质地',
    'Cd_mgkg':'镉_Cd(mg/kg)', 'Pb_mgkg':'铅_Pb(mg/kg)',
    'As_mgkg':'砷_As(mg/kg)', 'Cu_mgkg':'铜_Cu(mg/kg)',
    'Zn_mgkg':'锌_Zn(mg/kg)', 'Ni_mgkg':'镍_Ni(mg/kg)',
    'Cr_mgkg':'铬_Cr(mg/kg)', 'Hg_mgkg':'汞_Hg(mg/kg)',
    'Sum_PAH_ngg':'多环芳烃_PAHs(ng/g)', 'BaP_ngg':'苯并芘_BaP(ng/g)',
    'SumPCB_ngg':'多氯联苯_PCBs(ng/g)', 'SumDDTs_ngg':'滴滴涕_DDTs(ng/g)',
    'SumHCHs_ngg':'六六六_HCHs(ng/g)',
}

# === 5. RF 插补 ===
STR_COLS = ['City','LandUse','Province','prov_cn','Pollution_Type','Source',
            'DOI','Country','SampleID','SiteDescription','SoilTexture']

def rf_impute(data, target_cols):
    data = data.copy()
    # 自动检测所有字符串列（object dtype），不强制转换
    str_cols_set = set(STR_COLS)
    for c in data.columns:
        if data[c].dtype == object:
            str_cols_set.add(c)
    str_data = {}
    for c in str_cols_set:
        if c in data.columns:
            str_data[c] = data[c].copy()
    # 非字符串列强制转 float
    for c in data.columns:
        if c in str_cols_set: continue
        if data[c].dtype == object:
            data[c] = pd.to_numeric(data[c], errors='coerce')
    num_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    # target_cols 只处理数值列
    available = [c for c in target_cols if c in data.columns and c not in str_cols_set]

    for target in available:
        if data[target].isna().sum() == 0: continue
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

    for c in data.select_dtypes(include=[np.number]).columns:
        if data[c].isna().any():
            data[c] = data[c].fillna(data[c].median() if not data[c].isna().all() else 0)

    for c, vals in str_data.items():
        if c in data.columns: data[c] = vals
    return data

# === 6. 生成 ===
def gen_sites(df_source, target_cols, n_sites, type_label, blank_cols=None):
    """
    df_source: 数据源（composite 或全量）
    target_cols: 要保留的列（含通用+污染指标）
    blank_cols: 要设为 NaN 的列（用于纯 HM/OP 场地隐藏对方类型指标）
    """
    generated = []
    available = [c for c in target_cols if c in df_source.columns]

    df_clean = df_source  # 不 dropna，让 RF 插补处理缺失
    prov_groups = list(df_clean.groupby('prov_cn'))
    valid_provs = [(p, g) for p, g in prov_groups if len(g) >= 30]
    if not valid_provs:
        valid_provs = [(p, g) for p, g in prov_groups if len(g) >= 10]
    if not valid_provs:
        print(f"  ⚠️ 无足够省份数据，使用全局采样")
        valid_provs = [('全局', df_source)]
    random.shuffle(valid_provs)

    for i in range(n_sites):
        idx = i % max(len(valid_provs), 1)
        prov, group = valid_provs[idx]

        n_rows = min(random.randint(30, 55), len(group))
        site = group.sample(n=n_rows, replace=(n_rows > len(group)),
                            random_state=42 + i).reset_index(drop=True)

        keep = [c for c in available if c in site.columns]
        site = site[keep].copy()

        # 隐藏对方类型的指标（纯 HM → ORG=NaN; 纯 OP → HM=NaN）
        if blank_cols:
            for bc in blank_cols:
                if bc in site.columns:
                    site[bc] = np.nan

        # RF 插补
        site = rf_impute(site, available)

        # 坐标过滤
        if 'Latitude' in site.columns:
            site['Latitude'] = pd.to_numeric(site['Latitude'], errors='coerce')
            site = site[site['Latitude'].between(15, 55)]
        if 'Longitude' in site.columns:
            site['Longitude'] = pd.to_numeric(site['Longitude'], errors='coerce')
            site = site[site['Longitude'].between(70, 140)]

        if len(site) < 15:
            site = group.sample(n=min(35, len(group)), replace=True,
                                random_state=142 + i * 7).reset_index(drop=True)
            keep2 = [c for c in available if c in site.columns]
            site = site[keep2].copy()
            if blank_cols:
                for bc in blank_cols:
                    if bc in site.columns: site[bc] = np.nan
            site = rf_impute(site, available)

        # 序号 + 采样点编号
        site.insert(0, '序号', range(1, len(site) + 1))
        prefix = prov[:2] if len(prov) >= 2 else prov
        site.insert(1, '采样点编号',
                    [f'{prefix}-{type_label[:2]}{i+1:02d}-{j+1:03d}'
                     for j in range(len(site))])

        # 重命名
        site.rename(columns={k: v for k, v in COL_RENAME.items()
                             if k in site.columns}, inplace=True)

        # 城市名
        city_val = prov
        if '城市' in site.columns:
            cvs = site['城市'].dropna()
            city_val = str(cvs.iloc[0]) if len(cvs) > 0 else prov

        fname = f'{prov}_{city_val}_{type_label}_{i+1:02d}.xlsx'
        fpath = os.path.join(DEST, fname)
        site.to_excel(fpath, index=False)
        generated.append((fname, len(site), len(site.columns)))

    return generated

# === 7. 清空 ===
for f in glob.glob(os.path.join(DEST, '*.xlsx')):
    try: os.remove(f)
    except: pass
for f in glob.glob(os.path.join(DEST, '~$*')):
    try: os.remove(f)
    except: pass

# 使用全部有效数据（不限类型）
all_valid = df[df['type'].isin(['heavy_metal', 'organic', 'composite'])]
print(f"有效数据: {len(all_valid)}行 (heavy_metal={len(df[df['type']=='heavy_metal'])}, organic={len(df[df['type']=='organic'])}, composite={len(df[df['type']=='composite'])})")

# 全部需要的列（从 all_valid 中筛选存在的）
all_hm_cols = [c for c in (META_COLS + CORE_HM + [x for x in COMMON if x in all_valid.columns]) if c in all_valid.columns]
all_org_cols = [c for c in (META_COLS + CORE_ORG + [x for x in COMMON if x in all_valid.columns]) if c in all_valid.columns]
all_comp_cols = [c for c in (META_COLS + CORE_HM + CORE_ORG + [x for x in COMMON if x in all_valid.columns]) if c in all_valid.columns]

total = 0
for tlabel, cols, blank, n in [
    ('重金属', all_hm_cols, CORE_ORG, 10),
    ('有机污染', all_org_cols, CORE_HM, 10),
    ('复合污染', all_comp_cols, [], 10),
]:
    print(f"\n=== {tlabel} ({len(cols)}列) ===")
    res = gen_sites(all_valid, cols, n, tlabel, blank)
    for name, rows, cols_n in res:
        print(f"  ✅ {name} ({rows}行 x {cols_n}列)")
    total += len(res)

print(f"\n总计: {total} 个场地")

# === 8. 翻译英文城市 + 清理文件名 ===
city_trans = {
    "Ma'anshan":'马鞍山','Yuxi':'玉溪','Handan':'邯郸','Dazu':'大足','Xingren':'兴仁',
    'Hechi':'河池','Xiantao':'仙桃','Liaozhong County':'辽中','Shigatse':'日喀则',
    'Chonghua':'从化','Huaibei':'淮北','Tianjin':'天津','Zhongxian':'忠县',
    'Liaoyang':'辽阳','Nanjing':'南京','Xiangyuan':'襄垣','Shanghai':'上海',
    'Dalian':'大连','Qingdao':'青岛','Guiyu':'贵屿','Sanya':'三亚',
    'Chengdu':'成都','Changshu':'常熟','Beijing':'北京','Guangzhou':'广州',
    'Shenzhen':'深圳','Wuhan':'武汉','Hangzhou':'杭州','Kunming':'昆明',
    'Lhasa':'拉萨','Xiamen':'厦门','Dongguan':'东莞','Foshan':'佛山',
    'Zhuhai':'珠海','Jinan':'济南','Zhengzhou':'郑州','Hefei':'合肥',
    'Fuzhou':'福州','Changsha':'长沙','Nanchang':'南昌','Taiyuan':'太原',
    'Xian':'西安','Lanzhou':'兰州','Xining':'西宁','Yinchuan':'银川',
    'Urumqi':'乌鲁木齐','Hohhot':'呼和浩特','Nanning':'南宁','Guiyang':'贵阳',
    'Haikou':'海口','Shenyang':'沈阳','Changchun':'长春','Harbin':'哈尔滨',
}
renamed = 0
for f in sorted(glob.glob(os.path.join(DEST, '*.xlsx'))):
    old = os.path.basename(f)
    new = old
    for en, cn in city_trans.items():
        new = new.replace(en, cn)
    new = new.replace('_-_', '_市区_')
    parts = new.replace('.xlsx','').split('_')
    if len(parts) >= 2 and parts[0] == parts[1]:
        parts[1] = '市区'
        new = '_'.join(parts) + '.xlsx'
    new = new.replace("'", '')
    if new != old:
        os.rename(f, os.path.join(DEST, new))
        renamed += 1

print(f"\n翻译/修复: {renamed} 个文件名")
