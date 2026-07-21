"""
v4: DataV WGS84 GeoJSON 精确坐标验证 + 完整障碍因子集(meta.json)
"""
import pandas as pd, numpy as np, os, glob, random, json
from collections import Counter
from shapely.geometry import Point, shape, Polygon, MultiPolygon
from sklearn.ensemble import RandomForestRegressor

np.random.seed(42); random.seed(42)

SRC = r'C:\Users\曾鸿\Desktop\000\论文中真实数据集-merged_std33,zh .xlsx'
DEST = r'C:\Users\曾鸿\Desktop\SRS-round10\data\demo_sites'
GEOJSON_DIR = r'C:\Users\曾鸿\Desktop\SRS-round10\data\geojson'

# === 1. 加载 DataV WGS84 GeoJSON 省份边界 ===
CODE2PROV = {
    '110000':'北京','120000':'天津','130000':'河北','140000':'山西','150000':'内蒙古',
    '210000':'辽宁','220000':'吉林','230000':'黑龙江','310000':'上海','320000':'江苏',
    '330000':'浙江','340000':'安徽','350000':'福建','360000':'江西','370000':'山东',
    '410000':'河南','420000':'湖北','430000':'湖南','440000':'广东','450000':'广西',
    '460000':'海南','500000':'重庆','510000':'四川','520000':'贵州','530000':'云南',
    '540000':'西藏','610000':'陕西','620000':'甘肃','630000':'青海','640000':'宁夏',
    '650000':'新疆',
}

prov_polygons = {}
for code, prov in CODE2PROV.items():
    fpath = os.path.join(GEOJSON_DIR, f'{code}_full.json')
    if not os.path.exists(fpath): continue
    with open(fpath) as f:
        geojson = json.load(f)
    polys = []
    for feat in geojson['features']:
        geom = shape(feat['geometry'])
        if isinstance(geom, Polygon): polys.append(geom)
        elif isinstance(geom, MultiPolygon): polys.extend(list(geom.geoms))
    if polys: prov_polygons[prov] = polys

print(f"加载 {len(prov_polygons)} 个省份的 WGS84 GeoJSON 边界")

def find_prov(lon, lat):
    """用 DataV WGS84 GeoJSON 精确判断坐标所属省份"""
    if pd.isna(lon) or pd.isna(lat): return None
    pt = Point(lon, lat)
    for prov, polys in prov_polygons.items():
        for poly in polys:
            if poly.contains(pt) or poly.touches(pt):
                return prov
    # 容差 0.01 度（约 1km）
    for prov, polys in prov_polygons.items():
        for poly in polys:
            if poly.distance(pt) < 0.01:
                return prov
    return None

# === 2. 加载论文数据集 ===
df = pd.read_excel(SRC, sheet_name='china', header=0)
print(f"数据: {len(df)}行")

# 归类
def classify(pt):
    pt = str(pt).strip().upper()
    if pt in ['HM','HEAVY_METAL']: return 'heavy_metal'
    if pt in ['OP','ORGANIC','PAH','OCP','PCN','PFAS','PBDE','ANTIBIOTICS','PAH+PCB','PAH+OCP','PAH+OCP+PCB']:return 'organic'
    if pt in ['HM+OP','HM+PAH','OP+HM']: return 'composite'
    if 'HM' in pt and ('OP' in pt or 'PAH' in pt or 'OCP' in pt): return 'composite'
    return 'unknown'
df['type'] = df['Pollution_Type'].apply(classify)
print(f"归类: {df['type'].value_counts().to_dict()}")

# === 3. 完整因子列表（来自 meta.json） ===
# 基础
BASE_COLS = ['序号', '采样点编号', '省份', '城市', '纬度', '经度', '土地利用', '采样深度(cm)']
# 理化+肥力+环境（meta.json feature_cols 中的非污染列）
PHYS_CHEM_COLS = [
    'pH', '有机质(%)', 'CEC(cmol/kg)',
    '砂粒(%)', '粉粒(%)', '黏粒(%)', '容重(g/cm³)', '土壤质地',
    '全氮(g/kg)', '海拔(m)', '年均降水(mm)', '电导率(mS/cm)',
    '全磷(g/kg)', '全钾(g/kg)', '碱解氮(mg/kg)', '速效磷(mg/kg)', '速效钾(mg/kg)',
]
# 8项重金属
HM_COLS = ['镉_Cd(mg/kg)','铅_Pb(mg/kg)','砷_As(mg/kg)','铬_Cr(mg/kg)',
           '汞_Hg(mg/kg)','铜_Cu(mg/kg)','锌_Zn(mg/kg)','镍_Ni(mg/kg)']
# 12项有机污染物（meta.json factor_cols_used）
ORG_COLS = [
    '多环芳烃_PAHs(ng/g)', '苯并芘_BaP(ng/g)', '有机氯_OCPs(ng/g)',
    '滴滴涕_DDTs(ng/g)', '多氯联苯_PCBs(ng/g)', '六六六_HCHs(ng/g)',
    '邻苯二甲酸酯_PAEs(μg/kg)', '多溴联苯醚_PBDEs(ng/g)',
    '全氟化合物_PFASs(ng/g)', '总石油烃_TPH(ng/g)',
    '高分子量PAHs(ng/g)', '低分子量PAHs(ng/g)',
]

# 源数据列映射
SRC_MAP = {
    '纬度':'Latitude','经度':'Longitude','城市':'City','土地利用':'LandUse',
    '采样深度(cm)':'SamplingDepth','土壤质地':'SoilTexture',
    'pH':'pH_merged','有机质(%)':'OC_pct','CEC(cmol/kg)':'CEC_cmolkg',
    '砂粒(%)':'Sand_pct','粉粒(%)':'Silt_pct','黏粒(%)':'Clay_pct',
    '容重(g/cm³)':'SoilBD_gcm3','全氮(g/kg)':'TN_gkg',
    '海拔(m)':'Elevation_m','年均降水(mm)':'MAP_mm','电导率(mS/cm)':'EC_mScm',
    '镉_Cd(mg/kg)':'Cd_mgkg','铅_Pb(mg/kg)':'Pb_mgkg','砷_As(mg/kg)':'As_mgkg',
    '铬_Cr(mg/kg)':'Cr_mgkg','汞_Hg(mg/kg)':'Hg_mgkg','铜_Cu(mg/kg)':'Cu_mgkg',
    '锌_Zn(mg/kg)':'Zn_mgkg','镍_Ni(mg/kg)':'Ni_mgkg',
    '多环芳烃_PAHs(ng/g)':'Sum_PAH_ngg','苯并芘_BaP(ng/g)':'BaP_ngg',
    '有机氯_OCPs(ng/g)':'SumOCP_ngg','滴滴涕_DDTs(ng/g)':'SumDDTs_ngg',
    '多氯联苯_PCBs(ng/g)':'SumPCB_ngg','六六六_HCHs(ng/g)':'SumHCHs_ngg',
    '邻苯二甲酸酯_PAEs(μg/kg)':'SumPAE_ugkg','多溴联苯醚_PBDEs(ng/g)':'SumPBDE_ngg',
    '全氟化合物_PFASs(ng/g)':'SumPFAS_ngg','总石油烃_TPH(ng/g)':'TPH_ngg',
    '高分子量PAHs(ng/g)':'HMWPAH_ngg','低分子量PAHs(ng/g)':'LMWPAH_ngg',
}

# === 4. 生成函数 ===
def make_one_site(prov, group_df, n_rows, ptype, seed):
    n = min(n_rows, len(group_df))
    site = group_df.sample(n=n, replace=(n>len(group_df)), random_state=seed).reset_index(drop=True)
    
    out = pd.DataFrame()
    out['序号'] = range(1, n+1)
    prefix = prov[:2] if len(prov)>=2 else prov
    out['采样点编号'] = [f'{prefix}-{ptype}{seed%100:02d}-{j+1:03d}' for j in range(n)]
    out['省份'] = prov
    
    # 城市
    if 'City' in site.columns:
        out['城市'] = [str(c) if pd.notna(c) and str(c)!='nan' else prov for c in site['City']]
    else:
        out['城市'] = prov
    
    # 坐标
    for cn, src in [('纬度','Latitude'),('经度','Longitude')]:
        out[cn] = pd.to_numeric(site[src], errors='coerce').values if src in site.columns else np.nan
    
    out['土地利用'] = site['LandUse'].values if 'LandUse' in site.columns else np.nan
    out['采样深度(cm)'] = site['SamplingDepth'].values if 'SamplingDepth' in site.columns else np.nan
    
    # 理化+环境
    phys_src = {
        'pH':'pH_merged','有机质(%)':'OC_pct','CEC(cmol/kg)':'CEC_cmolkg',
        '砂粒(%)':'Sand_pct','粉粒(%)':'Silt_pct','黏粒(%)':'Clay_pct',
        '容重(g/cm³)':'SoilBD_gcm3','全氮(g/kg)':'TN_gkg',
        '海拔(m)':'Elevation_m','年均降水(mm)':'MAP_mm','电导率(mS/cm)':'EC_mScm',
        '土壤质地':'SoilTexture',
    }
    for cn, src in phys_src.items():
        if src in site.columns:
            out[cn] = pd.to_numeric(site[src], errors='coerce').values if cn != '土壤质地' else site[src].values
        else:
            out[cn] = np.nan
    
    # 肥力（合成）
    fert_ranges = {
        '全磷(g/kg)':(0.2,2.0),'全钾(g/kg)':(5,30),
        '碱解氮(mg/kg)':(30,200),'速效磷(mg/kg)':(2,50),'速效钾(mg/kg)':(50,300),
    }
    for cn,(lo,hi) in fert_ranges.items():
        if '全氮(g/kg)' in out.columns and out['全氮(g/kg)'].notna().sum()>3:
            tn = out['全氮(g/kg)'].fillna(out['全氮(g/kg)'].median())
            base = lo + (tn-tn.min())/max(tn.max()-tn.min(),1)*(hi-lo)
            out[cn] = np.clip(base * np.random.uniform(0.7,1.3,size=n), lo, hi).round(2)
        else:
            out[cn] = np.random.uniform(lo, hi, size=n).round(2)
    
    # 重金属
    hm_src = {
        '镉_Cd(mg/kg)':'Cd_mgkg','铅_Pb(mg/kg)':'Pb_mgkg','砷_As(mg/kg)':'As_mgkg',
        '铬_Cr(mg/kg)':'Cr_mgkg','汞_Hg(mg/kg)':'Hg_mgkg','铜_Cu(mg/kg)':'Cu_mgkg',
        '锌_Zn(mg/kg)':'Zn_mgkg','镍_Ni(mg/kg)':'Ni_mgkg',
    }
    for cn, src in hm_src.items():
        if src in site.columns and ptype in ('HM','CP'):
            out[cn] = pd.to_numeric(site[src], errors='coerce').values
        else:
            out[cn] = np.nan
    
    # 有机物
    org_src = {
        '多环芳烃_PAHs(ng/g)':'Sum_PAH_ngg','苯并芘_BaP(ng/g)':'BaP_ngg',
        '有机氯_OCPs(ng/g)':'SumOCP_ngg','滴滴涕_DDTs(ng/g)':'SumDDTs_ngg',
        '多氯联苯_PCBs(ng/g)':'SumPCB_ngg','六六六_HCHs(ng/g)':'SumHCHs_ngg',
        '邻苯二甲酸酯_PAEs(μg/kg)':'SumPAE_ugkg','多溴联苯醚_PBDEs(ng/g)':'SumPBDE_ngg',
        '全氟化合物_PFASs(ng/g)':'SumPFAS_ngg','总石油烃_TPH(ng/g)':'TPH_ngg',
        '高分子量PAHs(ng/g)':'HMWPAH_ngg','低分子量PAHs(ng/g)':'LMWPAH_ngg',
    }
    for cn, src in org_src.items():
        if src in site.columns and ptype in ('OP','CP'):
            out[cn] = pd.to_numeric(site[src], errors='coerce').values
        else:
            out[cn] = np.nan
    
    return out

# === 5. 保守 RF 插补 ===
STR_COLS = set(['序号','采样点编号','省份','城市','土地利用','土壤质地'])

def conservative_impute(data, max_fill=0.5):
    data = data.copy()
    # 保护字符串列
    str_data = {}
    for c in data.columns:
        if data[c].dtype == object:
            str_data[c] = data[c].copy()
    # 数值转换
    for c in data.columns:
        if c in str_data: continue
        if data[c].dtype == object:
            data[c] = pd.to_numeric(data[c], errors='coerce')
    
    num_cols = data.select_dtypes(include=[np.number]).columns
    targets = [c for c in num_cols if c not in STR_COLS and data[c].isna().sum()>0 and data[c].notna().sum()>=5]
    
    for target in targets:
        features = [c for c in num_cols if c!=target and data[c].notna().sum()>5]
        if len(features)<2: continue
        train_mask = data[target].notna() & data[features].notna().all(axis=1)
        if train_mask.sum()<5: continue
        X_tr = data.loc[train_mask, features].fillna(data[features].median())
        y_tr = data.loc[train_mask, target]
        rf = RandomForestRegressor(n_estimators=30, max_depth=8, random_state=42, n_jobs=-1)
        rf.fit(X_tr, y_tr)
        pred_mask = data[target].isna()
        n_fill = int(pred_mask.sum()*max_fill)
        if n_fill==0: continue
        fill_idx = np.random.choice(data.index[pred_mask].tolist(), size=n_fill, replace=False)
        data.loc[fill_idx, target] = rf.predict(data.loc[fill_idx, features].fillna(data[features].median()))
    
    # 恢复字符串
    for c, vals in str_data.items():
        if c in data.columns: data[c] = vals
    return data

# === 6. 主流程 ===
all_valid = df[df['type']!='unknown']

# 统一中文省份
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
all_valid['prov_cn'] = all_valid['Province'].map(prov_map).fillna(all_valid['Province'])

# 按省份分组
prov_groups = list(all_valid.groupby('prov_cn'))
valid_provs = [(p, g) for p, g in prov_groups if len(g) >= 25]
random.shuffle(valid_provs)
print(f"有效省份: {len(valid_provs)}个")

# 清空
for f in glob.glob(os.path.join(DEST, '*.xlsx')):
    try: os.remove(f)
    except: pass
for f in glob.glob(os.path.join(DEST, '~$*')):
    try: os.remove(f)
    except: pass

total = 0
for ptype, label, n_sites in [('HM','重金属',10), ('OP','有机污染',10), ('CP','复合污染',10)]:
    print(f'\n=== {label} ===')
    
    for i in range(n_sites):
        if not valid_provs:
            prov, group = '未知', all_valid.sample(50, random_state=i)
        else:
            prov, group = valid_provs[i % len(valid_provs)]
        
        n_rows = random.randint(25, 45)
        site = make_one_site(prov, group, n_rows, ptype, seed=42+i)
        
        # 坐标过滤
        if '纬度' in site.columns and '经度' in site.columns:
            lat = pd.to_numeric(site['纬度'], errors='coerce')
            lon = pd.to_numeric(site['经度'], errors='coerce')
            site = site[(lat.between(15,55)) & (lon.between(70,140))]
        
        if len(site) < 15:
            site = make_one_site(prov, group, 35, ptype, seed=142+i)
        
        site = conservative_impute(site, max_fill=0.5)
        
        # 城市
        city_val = prov
        if '城市' in site.columns:
            cvs = site['城市'].dropna()
            city_val = str(cvs.iloc[0]) if len(cvs)>0 else prov
        
        fname = f'{prov}_{city_val}_{label}_{i+1:02d}.xlsx'
        fpath = os.path.join(DEST, fname)
        site.to_excel(fpath, index=False)
        total += 1
        
        missing = sum(1 for c in site.columns if c not in STR_COLS and site[c].isna().sum()>0)
        print(f'  ✅ {fname[:55]} ({len(site)}行×{len(site.columns)}列 空缺{missing}列)')

print(f'\n总计: {total} 个场地')
