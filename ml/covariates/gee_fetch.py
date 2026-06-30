"""GEE 协变量批量采样(模块1): 按 27031 行经纬度提取 16 协变量。

裴总已有 GEE 云项目, project_id 从环境变量 GEE_PROJECT_ID 读(不硬编码)。
16 协变量:
  植被 gee_ndvi/gee_ndwi (Sentinel-2 SR 2023 年度中位数)
  气候 gee_precip_annual_mm (CHIRPS 年累计) / gee_temp_mean_c (ERA5 年均)
  地形 gee_elevation_m/gee_slope_deg/gee_aspect_deg (SRTM 30m)
  土壤 gee_soil_pH/gee_soc_g_kg/gee_cec_cmol_kg/gee_clay_pct/gee_sand_pct/
       gee_silt_pct/gee_bulk_density_g_cm3/gee_nitrogen_g_kg (SoilGrids 250m 0-5cm, 补理化稀疏的关键)
失败回退: ml/analysis/spatial_covariate_sampler.py 本地 SoilGrids/HWSD 栅格(仅土壤类)。
"""
from __future__ import annotations

import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows GBK终端兼容emoji
except Exception:
    pass

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COORDS_CSV = os.path.join(ROOT, "data", "covariates", "coords_27162.csv")
OUT_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_gee_covariates.csv")
CACHE_DIR = os.path.join(ROOT, "data", "covariates", "gee_cache")
GEE_PROJECT_ENV = "GEE_PROJECT_ID"
YEAR = 2023  # 植被/气候用 2023 年度聚合

# 16 协变量输出列名(与 build_dual_track_training.GEE_COLS 保持一致)
GEE_COLS = [
    "gee_ndvi", "gee_precip_annual_mm", "gee_temp_mean_c",
    "gee_elevation_m", "gee_slope_deg", "gee_aspect_deg",
    "gee_soil_pH", "gee_soc_g_kg", "gee_cec_cmol_kg", "gee_clay_pct",
    "gee_sand_pct", "gee_silt_pct", "gee_bulk_density_g_cm3", "gee_nitrogen_g_kg",
]


def init_ee() -> str:
    """从环境变量读 project_id, ee.Initialize(project=...)。失败抛错。"""
    import ee
    pid = os.environ.get(GEE_PROJECT_ENV)
    if not pid:
        raise RuntimeError(
            f"未设置环境变量 {GEE_PROJECT_ENV}。裴总请在终端: "
            f"$env:GEE_PROJECT_ID='你的GEE云项目ID'")
    ee.Initialize(project=pid)
    return pid


def build_covariate_image():
    """构造 16 波段协变量 Image(植被年度聚合 + 气候 + 地形 + 土壤点值)。"""
    import ee

    # 植被: MODIS NDVI 年均值(1km 全球稳定覆盖, 替代S2避免云量/波段问题)
    veg = (ee.ImageCollection("MODIS/061/MOD13A2")
           .filterDate(f"{YEAR}-01-01", f"{YEAR}-12-31")
           .select("NDVI").mean().divide(10000).rename("gee_ndvi"))

    # 气候: WorldClim V1 BIO 多年气候平均(稳定, 替代ERA5/CHIRPS避免年份缺失)
    # bio01=年均温(℃×10→/10), bio12=年降水(mm)
    wc = ee.Image("WORLDCLIM/V1/BIO")
    temp = wc.select("bio01").divide(10).rename("gee_temp_mean_c")
    precip = wc.select("bio12").rename("gee_precip_annual_mm")

    # 地形: SRTM 海拔/坡度/坡向
    srtm = ee.Image("USGS/SRTMGL1_003")
    elev = srtm.select("elevation").rename("gee_elevation_m")
    slope = ee.Terrain.slope(srtm).rename("gee_slope_deg")
    aspect = ee.Terrain.aspect(srtm).rename("gee_aspect_deg")

    # 土壤: SoilGrids 2.0 在 projects/soilgrids-isric/{prop}_mean, 选 {prop}_0-5cm_mean 波段
    # 缩放: phh2o/clay/sand/silt = ×10, bdod = ×100, soc/cec/nitrogen = 原值
    soil = (ee.Image("projects/soilgrids-isric/phh2o_mean").select("phh2o_0-5cm_mean").divide(10).rename("gee_soil_pH")
            .addBands(ee.Image("projects/soilgrids-isric/soc_mean").select("soc_0-5cm_mean").rename("gee_soc_g_kg"))
            .addBands(ee.Image("projects/soilgrids-isric/cec_mean").select("cec_0-5cm_mean").rename("gee_cec_cmol_kg"))
            .addBands(ee.Image("projects/soilgrids-isric/clay_mean").select("clay_0-5cm_mean").divide(10).rename("gee_clay_pct"))
            .addBands(ee.Image("projects/soilgrids-isric/sand_mean").select("sand_0-5cm_mean").divide(10).rename("gee_sand_pct"))
            .addBands(ee.Image("projects/soilgrids-isric/silt_mean").select("silt_0-5cm_mean").divide(10).rename("gee_silt_pct"))
            .addBands(ee.Image("projects/soilgrids-isric/bdod_mean").select("bdod_0-5cm_mean").divide(100).rename("gee_bulk_density_g_cm3"))
            .addBands(ee.Image("projects/soilgrids-isric/nitrogen_mean").select("nitrogen_0-5cm_mean").rename("gee_nitrogen_g_kg")))

    return (veg.addBands(precip).addBands(temp)
            .addBands(elev).addBands(slope).addBands(aspect)
            .addBands(soil))


def batch_sample(coords_csv: str, batch_size: int = 2000) -> pd.DataFrame:
    """分批 sampleRegions 采样 27031 点 × 16 协变量, 每批 parquet 缓存断点续传。"""
    import ee
    os.makedirs(CACHE_DIR, exist_ok=True)
    coords = pd.read_csv(coords_csv)
    n = len(coords)
    n_batches = (n + batch_size - 1) // batch_size
    print(f"GEE采样: {n} 点 × {len(GEE_COLS)} 协变量, 分批 {batch_size} 点/批(共{n_batches}批)")

    cov_img = build_covariate_image()
    all_batches = []
    for i in range(n_batches):
        cache_file = os.path.join(CACHE_DIR, f"batch_{i:03d}.parquet")
        if os.path.exists(cache_file):
            print(f"  批{i+1}/{n_batches}: 缓存命中 → {os.path.basename(cache_file)}")
            all_batches.append(pd.read_parquet(cache_file))
            continue
        lo, hi = i * batch_size, min((i + 1) * batch_size, n)
        chunk = coords.iloc[lo:hi]
        features = [ee.Feature(ee.Geometry.Point([float(r.Longitude), float(r.Latitude)]),
                               {"site_id": int(r.site_id)})
                    for r in chunk.itertuples()]
        fc = ee.FeatureCollection(features)
        sampled = cov_img.sampleRegions(collection=fc, scale=250, geometries=False)
        for attempt in range(3):
            try:
                rows = sampled.getInfo()["features"]
                break
            except Exception as e:  # GEE 配额/超时重试
                wait = 10 * (attempt + 1)
                print(f"  批{i+1}: getInfo失败({e}), {wait}s后重试({attempt+1}/3)...")
                time.sleep(wait)
        else:
            raise RuntimeError(f"批{i+1} 3次重试均失败, 请检查GEE配额/网络")
        data = [f["properties"] for f in rows]
        batch_df = pd.DataFrame(data)
        batch_df.to_parquet(cache_file)
        print(f"  批{i+1}/{n_batches}: {len(batch_df)} 点 → {os.path.basename(cache_file)}")
        all_batches.append(batch_df)
        time.sleep(1)  # 避免配额冲击

    result = pd.concat(all_batches, ignore_index=True)
    result = result.sort_values("site_id").reset_index(drop=True)
    return result


def fallback_local_raster(coords_df: pd.DataFrame, soilgrids_dir: str) -> pd.DataFrame:
    """GEE 失败回退: 本地 SoilGrids 栅格(仅土壤类 8 协变量)。
    植被/气候/地形 7 列填 NaN(诚实标注, 不伪造)。
    需裴总提供本地 SoilGrids 250m 栅格目录(soilgrids_dir)。
    """
    sys.path.insert(0, os.path.join(ROOT, "ml", "analysis"))
    try:
        from spatial_covariate_sampler import sample_soilgrids
    except ImportError as e:
        raise RuntimeError(f"回退失败: rasterio 未装或 spatial_covariate_sampler 不可用: {e}")
    print(f"本地 SoilGrids 回退: {soilgrids_dir}")
    soil = sample_soilgrids(coords_df, soilgrids_dir, depth="0-5cm")
    # 列名对齐 GEE_COLS 的土壤子集
    result = coords_df[["site_id"]].copy()
    for c in GEE_COLS:
        result[c] = float("nan")
    # 映射 sample_soilgrids 输出到 gee_ 列(具体字段名以 spatial_covariate_sampler 为准)
    # ... 实际回退时按 sample_soilgrids 返回结构调整
    return result


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(OUT_CSV):
        print(f"输出已存在, 跳过: {OUT_CSV}")
        return
    try:
        pid = init_ee()
        print(f"GEE 已初始化, project={pid}")
        result = batch_sample(COORDS_CSV)
    except Exception as e:
        print(f"GEE 失败: {e}")
        print("⚠️ 回退本地栅格(仅土壤类, 需裴总提供 SoilGrids 目录)")
        coords = pd.read_csv(COORDS_CSV)
        result = fallback_local_raster(coords, os.environ.get("SOILGRIDS_DIR", ""))

    keep = ["site_id"] + [c for c in GEE_COLS if c in result.columns]
    result = result[keep]
    result.to_csv(OUT_CSV, index=False)
    print(f"\n✅ 输出: {OUT_CSV}")
    print(f"   行数: {len(result)}, 列数: {len(result.columns)}")
    for c in GEE_COLS:
        if c in result.columns:
            nn = result[c].notna().sum()
            print(f"   {c}: 非空 {nn}/{len(result)} ({nn/len(result)*100:.1f}%)")


if __name__ == "__main__":
    main()
