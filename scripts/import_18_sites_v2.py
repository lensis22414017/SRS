"""从训练数据集生成18个场地导入系统 v2 — 修复因子代码映射和坐标。"""
import os, sys
sys.path.insert(0, "backend")
os.environ["DATABASE_URL"] = "sqlite:///./srs_dev.db"
os.environ["SECRET_KEY"] = "dev_secret_change_me"

import pandas as pd
import numpy as np
from app.db.session import SessionLocal
from app.models import Site, SamplingPoint, Measurement, FactorDictionary
from datetime import date

df = pd.read_parquet('autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset/06_dataset_subsets/dataset_all_v0.8.parquet')

# 训练集因子代码 → 系统因子代码映射
FACTOR_MAP = {
    'Cd_mgkg': 'Cd', 'Pb_mgkg': 'Pb', 'As_mgkg': 'As', 'Cr_mgkg': '铬',
    'Hg_mgkg': '汞', 'Ni_mgkg': '镍', 'Zn_mgkg': 'Zn', 'Cu_mgkg': 'Cu',
    'OC_pct': '有机质', 'TN_gkg': '全氮',
    'SumHCHs_ngg': '六六六总量', 'SumDDTs_ngg': '滴滴涕总量',
    '钴': '钴', '钒': '钒', '铍': '铍', '锑': '锑',
    'SoilBD_gcm3': '容重', '有效磷': '有效磷', '速效钾': '速效钾',
}

db = SessionLocal()
factors = {f.factor_code: f for f in db.query(FactorDictionary).all()}

# 清旧训练场地(id>3)
db.query(Measurement).filter(Measurement.site_id > 3).delete()
db.query(SamplingPoint).filter(SamplingPoint.site_id > 3).delete()
db.query(Site).filter(Site.id > 3).delete()
db.commit()

# 按省份×类型分组
combo = df.groupby(['province', 'pollution_type']).size().reset_index(name='n')
combo = combo[(combo['n'] >= 100) & (combo['province'] != 'unknown')].sort_values('n', ascending=False).head(15)

TYPE_MAP = {"HM": "heavy_metal", "PAH": "organic", "HM+OP": "composite"}
TYPE_LABEL = {"HM": "HM", "PAH": "OP", "HM+OP": "HM+OP"}

created = 0
for _, row in combo.iterrows():
    prov = row['province']
    ptype = row['pollution_type']
    subset = df[(df['province'] == prov) & (df['pollution_type'] == ptype)].head(200)
    n_pts = len(subset)
    if n_pts < 10:
        continue

    sys_type = TYPE_MAP.get(ptype, "heavy_metal")
    site_code = f"{prov}-{TYPE_LABEL.get(ptype,'HM')}-{n_pts}D"

    # 坐标: 从GEE列或经纬度列取
    lng_col = [c for c in df.columns if 'longitude' in c.lower() or 'lng' in c.lower() or '经度' in c]
    lat_col = [c for c in df.columns if 'latitude' in c.lower() or 'lat' in c.lower() or '纬度' in c]
    lons = subset[lng_col[0]].dropna() if lng_col else pd.Series(dtype=float)
    lats = subset[lat_col[0]].dropna() if lat_col else pd.Series(dtype=float)
    site_lng = float(lons.mean()) if len(lons) > 0 else None
    site_lat = float(lats.mean()) if len(lats) > 0 else None

    site = Site(
        site_code=site_code,
        name=f"site_{prov}_{TYPE_LABEL.get(ptype,'HM')}_{n_pts}点",
        pollution_type=sys_type,
        land_use_type="生产用地",
        province=prov,
        longitude=round(site_lng, 4) if site_lng else None,
        latitude=round(site_lat, 4) if site_lat else None,
    )
    db.add(site)
    db.flush()

    n_meas = 0
    for idx, (_, srow) in enumerate(subset.iterrows()):
        lng = float(srow[lng_col[0]]) if lng_col and pd.notna(srow.get(lng_col[0])) else None
        lat = float(srow[lat_col[0]]) if lat_col and pd.notna(srow.get(lat_col[0])) else None
        if lng and lat:
            lng += np.random.uniform(-0.02, 0.02)
            lat += np.random.uniform(-0.02, 0.02)

        pt = SamplingPoint(
            site_id=site.id,
            point_code=f"{prov[:2]}-{sys_type[:2]}-{idx+1:03d}",
            longitude=round(lng, 6) if lng else None,
            latitude=round(lat, 6) if lat else None,
            sampled_at=date(2024, 7, 1),
        )
        db.add(pt)
        db.flush()

        # 用映射表提取检测值
        for col in subset.columns:
            if not col.startswith('x_measured_') or 'missing' in col:
                continue
            val = srow.get(col)
            if pd.notna(val) and val != 0:
                train_code = col.replace('x_measured_', '')
                sys_code = FACTOR_MAP.get(train_code, train_code)
                fd = factors.get(sys_code)
                if not fd:
                    # 尝试直接用训练集code
                    fd = factors.get(train_code)
                if fd:
                    db.add(Measurement(
                        site_id=site.id,
                        sampling_point_id=pt.id,
                        factor_id=fd.id,
                        value=float(val),
                        unit=fd.default_unit,
                        detected_at=date(2024, 7, 1),
                    ))
                    n_meas += 1

    print(f"✅ {site.name}: {n_pts}点 {n_meas}测量 lng={site.longitude} lat={site.latitude}")
    created += 1

db.commit()
print(f"\n共创建{created}个场地(加3真实={created+3}个)")
print(f"数据库总场地数: {db.query(Site).count()}")
db.close()
