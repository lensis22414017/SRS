"""17 场地 GEE 协变量持久化(裴总: 对17测试场地数据GEE补充, 全流程诊断用真实GEE)。

1. factor_dictionary 加 14 gee_ 因子
2. 16 场地(有坐标)GEE 采样(场地中心经纬度, 一次 sampleRegions)
3. 存 measurements(场地级 sampling_point_id=NULL) → pivot_site_measurements 自动补入所有采样点
   site 2 南京栖霞无坐标 → 跳过(诊断时 _enrich_gee_if_needed 兜底 medians)
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "ml", "covariates"))
os.environ.setdefault("GEE_PROJECT_ID", "project-1bc9db36-ce72-4e39-b2b")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ee
ee.Initialize(project=os.environ["GEE_PROJECT_ID"])
from gee_fetch import build_covariate_image, GEE_COLS  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Site, FactorDictionary, Measurement, SamplingPoint  # noqa: E402

GEE_FACTORS = {
    "gee_ndvi": ("NDVI植被指数", "环境指标"),
    "gee_precip_annual_mm": ("年降水mm", "环境指标"),
    "gee_temp_mean_c": ("年均温℃", "环境指标"),
    "gee_elevation_m": ("海拔m", "环境指标"),
    "gee_slope_deg": ("坡度", "环境指标"),
    "gee_aspect_deg": ("坡向", "环境指标"),
    "gee_soil_pH": ("SoilGrids_pH", "环境指标"),
    "gee_soc_g_kg": ("SoilGrids_SOC", "环境指标"),
    "gee_cec_cmol_kg": ("SoilGrids_CEC", "环境指标"),
    "gee_clay_pct": ("SoilGrids_黏粒", "环境指标"),
    "gee_sand_pct": ("SoilGrids_砂粒", "环境指标"),
    "gee_silt_pct": ("SoilGrids_粉粒", "环境指标"),
    "gee_bulk_density_g_cm3": ("SoilGrids_容重", "环境指标"),
    "gee_nitrogen_g_kg": ("SoilGrids_全氮", "环境指标"),
}

db = SessionLocal()

# 1. factor_dictionary 加 gee_ 因子
existing = {f.factor_code for f in db.query(FactorDictionary).all()}
for code, (name, cat) in GEE_FACTORS.items():
    if code not in existing:
        db.add(FactorDictionary(factor_code=code, factor_name=name,
                                 level1_category=cat, factor_type="协变量",
                                 default_unit="", source="GEE"))
db.commit()
fd = {f.factor_code: f.id for f in db.query(FactorDictionary).all()}
print(f"[1] factor_dictionary gee_因子: {sum(1 for c in GEE_FACTORS if c in fd)}/{len(GEE_FACTORS)}")

# 2. 16 场地(有坐标)GEE 采样
sites = db.query(Site).filter(Site.latitude.isnot(None),
                               Site.longitude.isnot(None)).all()
print(f"[2] 采样 {len(sites)} 场地 GEE 协变量(场地中心)...")
feats = [ee.Feature(ee.Geometry.Point([float(s.longitude), float(s.latitude)]),
                     {"site_id": s.id}) for s in sites]
cov = build_covariate_image()
res = cov.sampleRegions(collection=ee.FeatureCollection(feats), scale=250).getInfo()
gee_vals = {f["properties"]["site_id"]: f["properties"]
            for f in res["features"]}
print(f"    GEE采样成功 {len(gee_vals)}/{len(sites)} 场地")

# 3. 清旧 gee_ measurements(按 source_file) + 存新(绑场地第一个采样点)
gee_factor_ids = [fd[c] for c in GEE_COLS if c in fd]
db.query(Measurement).filter(Measurement.factor_id.in_(gee_factor_ids),
                              Measurement.source_file == "enrich_sites_gee").delete(synchronize_session=False)
n = 0
for site_id, props in gee_vals.items():
    sp = db.query(SamplingPoint).filter_by(site_id=site_id).first()
    if sp is None:
        continue
    for code in GEE_COLS:
        if code in fd and props.get(code) is not None:
            db.add(Measurement(site_id=site_id, sampling_point_id=sp.id,
                                factor_id=fd[code], value=float(props[code]),
                                unit="", method="GEE采样",
                                source_file="enrich_sites_gee"))
            n += 1
db.commit()
print(f"[3] 已存 {len(gee_vals)} 场地 × gee_因子 → {n} 条 measurements(场地级)")
print("    diagnosis pivot_site_measurements 会自动补入所有采样点")
db.close()
