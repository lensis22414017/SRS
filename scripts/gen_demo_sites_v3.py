"""
v3: 严格列顺序 + 禁止全0列 + 保留空缺值
列顺序: 基础属性 → 理化性质 → 重金属 → 有机污染物
"""
import pandas as pd
import numpy as np
import os, glob, random
from sklearn.ensemble import RandomForestRegressor

np.random.seed(42); random.seed(42)

SRC = r'C:\Users\曾鸿\Desktop\000\论文中真实数据集-merged_std33,zh .xlsx'
DEST = r'C:\Users\曾鸿\Desktop\SRS-round10\data\demo_sites'

# === 1. 加载 ===
df = pd.read_excel(SRC, sheet_name='china', header=0)

# === 2. 归类 ===
def classify(pt):
    pt = str(pt).strip().upper()
    if pt in ['HM','HEAVY_METAL']: return 'heavy_metal'
    if pt in ['OP','ORGANIC','PAH','OCP','PCN','PFAS','PBDE','ANTIBIOTICS','PAH+PCB','PAH+OCP','PAH+OCP+PCB']:return 'organic'
    if pt in ['HM+OP','HM+PAH','OP+HM']: return 'composite'
    if 'HM' in pt and ('OP' in pt or 'PAH' in pt or 'OCP' in pt): return 'composite'
    return 'unknown'
df['type'] = df['Pollution_Type'].apply(classify)

# === 3. 省份 ===
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

# === 4. 严格列顺序定义 ===
# 基础属性
BASE_COLS = ['序号', '采样点编号', '省份', '城市', '纬度', '经度', '土地利用', '采样深度(cm)']
# 理化性质（障碍因子集: 化学性质+肥力指标+物理性质）
PHYS_CHEM_COLS = ['pH', '有机质(%)', 'CEC(cmol/kg)',
                  '全氮(g/kg)', '全磷(g/kg)', '全钾(g/kg)',
                  '碱解氮(mg/kg)', '速效磷(mg/kg)', '速效钾(mg/kg)',
                  '砂粒(%)', '粉粒(%)', '黏粒(%)', '容重(g/cm³)', '土壤质地']
# 重金属
HM_COLS = ['镉_Cd(mg/kg)','铅_Pb(mg/kg)','砷_As(mg/kg)','铜_Cu(mg/kg)',
           '锌_Zn(mg/kg)','镍_Ni(mg/kg)','铬_Cr(mg/kg)','汞_Hg(mg/kg)']
# 有机污染物
ORG_COLS = ['多环芳烃_PAHs(ng/g)','苯并芘_BaP(ng/g)','多氯联苯_PCBs(ng/g)',
            '滴滴涕_DDTs(ng/g)','六六六_HCHs(ng/g)']

# === 5. 源数据列映射 ===
SRC_MAP = {
    '纬度':'Latitude','经度':'Longitude','城市':'City','省份':'prov_cn',
    'pH':'pH_merged','有机质(%)':'OC_pct','CEC(cmol/kg)':'CEC_cmolkg',
    '砂粒(%)':'Sand_pct','粉粒(%)':'Silt_pct','黏粒(%)':'Clay_pct',
    '容重(g/cm³)':'SoilBD_gcm3','土地利用':'LandUse',
    '采样深度(cm)':'SamplingDepth','土壤质地':'SoilTexture',
    '镉_Cd(mg/kg)':'Cd_mgkg','铅_Pb(mg/kg)':'Pb_mgkg',
    '砷_As(mg/kg)':'As_mgkg','铜_Cu(mg/kg)':'Cu_mgkg',
    '锌_Zn(mg/kg)':'Zn_mgkg','镍_Ni(mg/kg)':'Ni_mgkg',
    '铬_Cr(mg/kg)':'Cr_mgkg','汞_Hg(mg/kg)':'Hg_mgkg',
    '多环芳烃_PAHs(ng/g)':'Sum_PAH_ngg','苯并芘_BaP(ng/g)':'BaP_ngg',
    '多氯联苯_PCBs(ng/g)':'SumPCB_ngg','滴滴涕_DDTs(ng/g)':'SumDDTs_ngg',
    '六六六_HCHs(ng/g)':'SumHCHs_ngg',
}
# 反向映射
SRC_MAP_REV = {v:k for k,v in SRC_MAP.items()}

# === 6. 生成一个场地 ===
def make_one_site(prov, group, n_rows, ptype, seed):
    """ptype: 'HM' | 'OP' | 'CP'"""
    n = min(n_rows, len(group))
    site = group.sample(n=n, replace=(n > len(group)), random_state=seed).reset_index(drop=True)
    
    # 提取源数据列
    src_cols_available = {k: v for k, v in SRC_MAP.items() if v in site.columns}
    
    # 构建输出 DataFrame
    out = pd.DataFrame()
    
    # --- 基础属性 ---
    out['序号'] = range(1, n + 1)
    prefix = prov[:2] if len(prov) >= 2 else prov
    out['采样点编号'] = [f'{prefix}-{ptype}{seed%100:02d}-{j+1:03d}' for j in range(n)]
    out['省份'] = prov
    
    # 城市
    if 'City' in site.columns:
        cities = site['City'].values
        out['城市'] = [str(c) if pd.notna(c) and str(c) != 'nan' else prov for c in cities]
    else:
        out['城市'] = prov
    
    # 坐标
    for cn, src in [('纬度','Latitude'),('经度','Longitude')]:
        if src in site.columns:
            vals = pd.to_numeric(site[src], errors='coerce')
            out[cn] = vals.values
        else:
            out[cn] = np.nan
    
    # 土地利用
    out['土地利用'] = site['LandUse'].values if 'LandUse' in site.columns else np.nan
    out['采样深度(cm)'] = site['SamplingDepth'].values if 'SamplingDepth' in site.columns else np.nan
    
    # --- 理化性质 ---
    phys_map = {
        'pH':'pH_merged', '有机质(%)':'OC_pct', 'CEC(cmol/kg)':'CEC_cmolkg',
        '砂粒(%)':'Sand_pct', '粉粒(%)':'Silt_pct', '黏粒(%)':'Clay_pct',
        '容重(g/cm³)':'SoilBD_gcm3', '土壤质地':'SoilTexture',
    }
    for cn, src in phys_map.items():
        if src in site.columns:
            vals = pd.to_numeric(site[src], errors='coerce') if cn != '土壤质地' else site[src].values
            out[cn] = vals
        else:
            out[cn] = np.nan
    
    # 肥力指标：源数据中没有直接的列，用合理随机值
    # 这些值应符合中国土壤的典型分布
    fert_ranges = {
        '全氮(g/kg)': (0.3, 3.0),
        '全磷(g/kg)': (0.2, 2.0),
        '全钾(g/kg)': (5, 30),
        '碱解氮(mg/kg)': (30, 200),
        '速效磷(mg/kg)': (2, 50),
        '速效钾(mg/kg)': (50, 300),
    }
    for cn, (lo, hi) in fert_ranges.items():
        # 基于有机质含量做相关性随机
        if '有机质(%)' in out.columns and out['有机质(%)'].notna().sum() > 3:
            om = out['有机质(%)'].fillna(out['有机质(%)'].median())
            base = lo + (om - om.min()) / max(om.max() - om.min(), 1) * (hi - lo)
            noise = np.random.uniform(0.7, 1.3, size=n)
            out[cn] = np.clip(base * noise, lo, hi).round(2)
        else:
            out[cn] = np.random.uniform(lo, hi, size=n).round(2)
    
    # --- 重金属 ---
    hm_src = {
        '镉_Cd(mg/kg)':'Cd_mgkg','铅_Pb(mg/kg)':'Pb_mgkg',
        '砷_As(mg/kg)':'As_mgkg','铜_Cu(mg/kg)':'Cu_mgkg',
        '锌_Zn(mg/kg)':'Zn_mgkg','镍_Ni(mg/kg)':'Ni_mgkg',
        '铬_Cr(mg/kg)':'Cr_mgkg','汞_Hg(mg/kg)':'Hg_mgkg',
    }
    for cn, src in hm_src.items():
        if src in site.columns and ptype in ('HM', 'CP'):
            vals = pd.to_numeric(site[src], errors='coerce')
            out[cn] = vals.values
        else:
            out[cn] = np.nan
    
    # --- 有机污染物 ---
    org_src = {
        '多环芳烃_PAHs(ng/g)':'Sum_PAH_ngg','苯并芘_BaP(ng/g)':'BaP_ngg',
        '多氯联苯_PCBs(ng/g)':'SumPCB_ngg','滴滴涕_DDTs(ng/g)':'SumDDTs_ngg',
        '六六六_HCHs(ng/g)':'SumHCHs_ngg',
    }
    for cn, src in org_src.items():
        if src in site.columns and ptype in ('OP', 'CP'):
            vals = pd.to_numeric(site[src], errors='coerce')
            out[cn] = vals.values
        else:
            out[cn] = np.nan
    
    return out

# === 7. RF 保守插补（保留空缺） ===
def conservative_impute(data, target_cols, max_fill_ratio=0.7):
    """只插补缺失率 < 50% 的列，且每列最多填 max_fill_ratio 比例"""
    data = data.copy()
    num_cols = data.select_dtypes(include=[np.number]).columns
    targets = [c for c in target_cols if c in data.columns and c in num_cols]
    
    for target in targets:
        missing = data[target].isna()
        miss_rate = missing.sum() / len(data)
        if miss_rate == 0: continue
        if miss_rate > 0.5: continue  # 缺失太多，不填
        
        features = [c for c in num_cols if c != target and data[c].notna().sum() > 5]
        if len(features) < 2: continue
        
        train_mask = data[target].notna() & data[features].notna().all(axis=1)
        if train_mask.sum() < 5: continue
        
        X_train = data.loc[train_mask, features].fillna(data[features].median())
        y_train = data.loc[train_mask, target]
        
        rf = RandomForestRegressor(n_estimators=30, max_depth=8, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)
        
        predict_mask = data[target].isna()
        n_fill = int(predict_mask.sum() * max_fill_ratio)
        if n_fill == 0: continue
        
        fill_candidates = data.index[predict_mask].tolist()
        fill_idx = np.random.choice(fill_candidates, size=n_fill, replace=False)
        X_pred = data.loc[fill_idx, features].fillna(data[features].median())
        data.loc[fill_idx, target] = rf.predict(X_pred)
    
    return data

# === 8. 清理全0列 ===
def drop_zero_cols(data):
    num_cols = data.select_dtypes(include=[np.number]).columns
    zero_cols = []
    for c in num_cols:
        vals = data[c].dropna()
        if len(vals) > 0 and (vals == 0).all():
            zero_cols.append(c)
    if zero_cols:
        data = data.drop(columns=zero_cols)
        print(f'    删除全0列: {zero_cols}')
    return data

# === 9. 主流程 ===
all_valid = df[df['type'] != 'unknown']
prov_groups = list(all_valid.groupby('prov_cn'))
valid_provs = [(p, g) for p, g in prov_groups if len(g) >= 30]
random.shuffle(valid_provs)

# 清空
for f in glob.glob(os.path.join(DEST, '*.xlsx')):
    try: os.remove(f)
    except: pass

total = 0
for ptype, label, n_sites in [('HM','重金属',10), ('OP','有机污染',10), ('CP','复合污染',10)]:
    print(f'\n=== {label} ===')
    for i in range(n_sites):
        idx = i % max(len(valid_provs), 1)
        prov, group = valid_provs[idx]
        
        n_rows = random.randint(25, 45)
        site = make_one_site(prov, group, n_rows, ptype, seed=42+i)
        
        # 坐标过滤
        if '纬度' in site.columns and '经度' in site.columns:
            lat = pd.to_numeric(site['纬度'], errors='coerce')
            lon = pd.to_numeric(site['经度'], errors='coerce')
            site = site[(lat.between(15,55)) & (lon.between(70,140))]
        
        if len(site) < 15:
            site = make_one_site(prov, group, 35, ptype, seed=142+i)
        
        # 保守插补
        num_targets = [c for c in site.columns if c not in ['序号','采样点编号','省份','城市','土地利用','土壤质地']]
        site = conservative_impute(site, num_targets, max_fill_ratio=0.6)
        
        # 删除全0列
        site = drop_zero_cols(site)
        
        # 文件名
        city_val = prov
        if '城市' in site.columns:
            cvs = site['城市'].dropna()
            city_val = str(cvs.iloc[0]) if len(cvs) > 0 else prov
        
        fname = f'{prov}_{city_val}_{label}_{i+1:02d}.xlsx'
        fpath = os.path.join(DEST, fname)
        site.to_excel(fpath, index=False)
        total += 1
        
        # 统计空缺
        num_cols = site.select_dtypes(include=[np.number]).columns
        missing_counts = {c: site[c].isna().sum() for c in num_cols if site[c].isna().sum() > 0}
        miss_str = f' 空缺列:{len(missing_counts)}' if missing_counts else ' 无空缺'
        print(f'  ✅ {fname} ({len(site)}行×{len(site.columns)}列){miss_str}')

print(f'\n总计: {total} 个场地')
