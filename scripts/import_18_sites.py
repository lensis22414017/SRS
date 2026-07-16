"""从训练数据集生成18个代表性场地导入系统。
按省份×污染类型分组，每组取最多200行(采样点)作为一个场地。
"""
import os, sys, math
sys.path.insert(0, "backend")
os.environ["DATABASE_URL"] = "sqlite:///./srs_dev.db"
os.environ["SECRET_KEY"] = "dev_secret_change_me"

import pandas as pd
import numpy as np
from app.db.session import SessionLocal
from app.models import Site, SamplingPoint, Measurement, FactorDictionary, ImportBatch
from datetime import date

df = pd.read_parquet('autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset/06_dataset_subsets/dataset_all_v0.8.parquet')
print(f"训练集: {len(df)} 行")

# 按 province + pollution_type 分组取Top18
combo = df.groupby(['province', 'pollution_type']).size().reset_index(name='n')
combo = combo[combo['n'] >= 100].sort_values('n', ascending=False).head(18)
print(f"选取 {len(combo)} 个省×类型组合")

# 因子字典已有，取factor_id映射
db = SessionLocal()
factors = {f.factor_code: f for f in db.query(FactorDictionary).all()}
print(f"因子字典: {len(factors)} 个")

# 清除旧的训练场地(id>3的)
db.query(Measurement).filter(Measurement.site_id > 3).delete()
db.query(SamplingPoint).filter(SamplingPoint.site_id > 3).delete()
db.query(Site).filter(Site.id > 3).delete()
db.commit()
print("已清除旧训练场地")

TYPE_MAP = {"HM": "heavy_metal", "PAH": "organic", "HM+OP": "composite"}
TYPE_LABEL = {"HM": "HM", "PAH": "OP", "HM+OP": "HM+OP"}

created = 0
for idx, row in combo.iterrows():
    prov = row['province']
    ptype = row['pollution_type']
    n = row['n']
    if prov == 'unknown' or pd.isna(prov):
        continue

    subset = df[(df['province'] == prov) & (df['pollution_type'] == ptype)].head(200)
    n_pts = len(subset)
    if n_pts < 10:
        continue

    sys_type = TYPE_MAP.get(ptype, "heavy_metal")
    site_code = f"{prov}-{TYPE_LABEL.get(ptype,'HM')}-{n_pts}D"

    # 取坐标
    lons = subset['x_proxy_gee_longitude'].dropna() if 'x_proxy_gee_longitude' in subset.columns else pd.Series(dtype=float)
    lats = subset['x_proxy_gee_latitude'].dropna() if 'x_proxy_gee_latitude' in subset.columns else pd.Series(dtype=float)
    site_lng = float(lons.mean()) if len(lons) > 0 else None
    site_lat = float(lats.mean()) if len(lats) > 0 else None

    # 创建场地
    site = Site(
        site_code=site_code,
        name=f"site_{prov}_{TYPE_LABEL.get(ptype,'HM')}_{n_pts}点",
        pollution_type=sys_type,
        land_use_type="生产用地",
        province=prov if prov != 'unknown' else None,
        longitude=round(site_lng, 4) if site_lng else None,
        latitude=round(site_lat, 4) if site_lat else None,
    )
    db.add(site)
    db.flush()

    n_meas = 0
    for _, srow in subset.iterrows():
        lng = float(srow.get('x_proxy_gee_longitude', 0)) if pd.notna(srow.get('x_proxy_gee_longitude')) else None
        lat = float(srow.get('x_proxy_gee_latitude', 0)) if pd.notna(srow.get('x_proxy_gee_latitude')) else None
        # 微抖坐标让地图上点分散
        if lng and lat:
            lng += np.random.uniform(-0.01, 0.01)
            lat += np.random.uniform(-0.01, 0.01)

        pt = SamplingPoint(
            site_id=site.id,
            point_code=f"{prov[:2]}-{sys_type[:2]}-{_+1:03d}",
            longitude=round(lng, 6) if lng else None,
            latitude=round(lat, 6) if lat else None,
            sampled_at=date(2024, 7, 1),
        )
        db.add(pt)
        db.flush()

        # 提取检测值
        for col in subset.columns:
            if col.startswith('x_measured_') and not col.startswith('x_missing'):
                val = srow.get(col)
                if pd.notna(val) and val != 0:
                    factor_code = col.replace('x_measured_', '')
                    fd = factors.get(factor_code)
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

    print(f"  ✅ {site.name}: {n_pts}点, {n_meas}测量, lng={site.longitude} lat={site.latitude}")
    created += 1
    if created >= 15:  # 最多15个，加已有3个=18
        break

db.commit()
print(f"\n共创建 {created} 个训练场地（加已有3个真实场地 = {created+3}个）")

# 验证
total = db.query(Site).count()
print(f"数据库总场地数: {total}")
db.close()
