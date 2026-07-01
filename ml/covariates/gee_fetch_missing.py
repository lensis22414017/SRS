"""补采 8463 个缺失站点的 GEE 协变量。

根因: 之前 sampleRegions 把 14 波段(含 SoilGrids 8 层) addBands 后整体采样,
  SoilGrids 在高原/极端环境无数据 → 整个采样点被丢弃 → 8463 点缺失。
修复: 非土壤层(6 波段: NDVI/降水/温度/海拔/坡度/坡向) 全球覆盖必采;
  土壤层(8 波段) 独立尽力采, 采不到填 NaN(诚实标注, 不伪造)。
输出: data/covariates/missing_8463_gee_covariates.csv (与 merged_std33_gee_covariates.csv 列对齐)
"""
import os
import sys
import time

os.environ["GEE_PROJECT_ID"] = "project-1bc9db36-ce72-4e39-b2b"

import ee

ee.Initialize(project="project-1bc9db36-ce72-4e39-b2b")
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
YEAR = "2020"

GEE_COLS = [
    "gee_ndvi", "gee_precip_annual_mm", "gee_temp_mean_c",
    "gee_elevation_m", "gee_slope_deg", "gee_aspect_deg",
    "gee_soil_pH", "gee_soc_g_kg", "gee_cec_cmol_kg", "gee_clay_pct",
    "gee_sand_pct", "gee_silt_pct", "gee_bulk_density_g_cm3", "gee_nitrogen_g_kg",
]

CACHE_DIR = os.path.join(ROOT, "data", "covariates", "gee_cache_missing")
os.makedirs(CACHE_DIR, exist_ok=True)


def build_env_image():
    """非土壤层(6 波段) — 全球覆盖, 不会丢点。"""
    veg = (ee.ImageCollection("MODIS/061/MOD13A2")
           .filterDate(f"{YEAR}-01-01", f"{YEAR}-12-31")
           .select("NDVI").mean().divide(10000).rename("gee_ndvi"))
    wc = ee.Image("WORLDCLIM/V1/BIO")
    precip = wc.select("bio12").rename("gee_precip_annual_mm")
    temp = wc.select("bio01").divide(10).rename("gee_temp_mean_c")
    srtm = ee.Image("USGS/SRTMGL1_003")
    return (veg.addBands(precip).addBands(temp)
            .addBands(srtm.select("elevation").rename("gee_elevation_m"))
            .addBands(ee.Terrain.slope(srtm).rename("gee_slope_deg"))
            .addBands(ee.Terrain.aspect(srtm).rename("gee_aspect_deg")))


def build_soil_image():
    """土壤层(8 波段) — SoilGrids, 高原/极端区可能无数据。"""
    return (ee.Image("projects/soilgrids-isric/phh2o_mean").select("phh2o_0-5cm_mean").divide(10).rename("gee_soil_pH")
            .addBands(ee.Image("projects/soilgrids-isric/soc_mean").select("soc_0-5cm_mean").rename("gee_soc_g_kg"))
            .addBands(ee.Image("projects/soilgrids-isric/cec_mean").select("cec_0-5cm_mean").rename("gee_cec_cmol_kg"))
            .addBands(ee.Image("projects/soilgrids-isric/clay_mean").select("clay_0-5cm_mean").divide(10).rename("gee_clay_pct"))
            .addBands(ee.Image("projects/soilgrids-isric/sand_mean").select("sand_0-5cm_mean").divide(10).rename("gee_sand_pct"))
            .addBands(ee.Image("projects/soilgrids-isric/silt_mean").select("silt_0-5cm_mean").divide(10).rename("gee_silt_pct"))
            .addBands(ee.Image("projects/soilgrids-isric/bdod_mean").select("bdod_0-5cm_mean").divide(100).rename("gee_bulk_density_g_cm3"))
            .addBands(ee.Image("projects/soilgrids-isric/nitrogen_mean").select("nitrogen_0-5cm_mean").rename("gee_nitrogen_g_kg")))


def sample_layer(img, coords_df, cache_name, batch_size=2000):
    """对指定 image 分批 sampleRegions, 带断点续传。"""
    n = len(coords_df)
    n_batches = (n + batch_size - 1) // batch_size
    print(f"  {cache_name}: {n} 点 × {len(img.bandNames().getInfo())} 波段, {n_batches} 批")
    all_batches = []
    for i in range(n_batches):
        cache_file = os.path.join(CACHE_DIR, f"{cache_name}_batch_{i:03d}.parquet")
        if os.path.exists(cache_file):
            print(f"    批{i+1}/{n_batches}: 缓存命中")
            all_batches.append(pd.read_parquet(cache_file))
            continue
        lo, hi = i * batch_size, min((i + 1) * batch_size, n)
        chunk = coords_df.iloc[lo:hi]
        features = [ee.Feature(ee.Geometry.Point([float(r.Longitude), float(r.Latitude)]),
                               {"site_id": int(r.site_id)}) for r in chunk.itertuples()]
        fc = ee.FeatureCollection(features)
        sampled = img.sampleRegions(collection=fc, scale=250, geometries=False)
        for attempt in range(3):
            try:
                rows = sampled.getInfo()["features"]
                break
            except Exception as e:
                wait = 10 * (attempt + 1)
                print(f"    批{i+1}: getInfo失败({e}), {wait}s后重试({attempt+1}/3)...")
                time.sleep(wait)
        else:
            rows = []
        data = [f["properties"] for f in rows]
        batch_df = pd.DataFrame(data) if data else pd.DataFrame({"site_id": chunk["site_id"].values})
        batch_df.to_parquet(cache_file)
        print(f"    批{i+1}/{n_batches}: {len(batch_df)} 点")
        all_batches.append(batch_df)
        time.sleep(1)
    return pd.concat(all_batches, ignore_index=True)


def main():
    coords = pd.read_csv(os.path.join(ROOT, "data", "covariates", "coords_missing_8463.csv"))
    print(f"补采 {len(coords)} 个缺失站点的 GEE 协变量")

    # 1. 非土壤层(全球覆盖, 必采)
    print("[1/2] 非土壤层(NDVI/降水/温度/海拔/坡度/坡向) — 全球覆盖")
    env_df = sample_layer(build_env_image(), coords, "env")
    print(f"  非土壤层采到: {len(env_df)}/{len(coords)} 点")

    # 2. 土壤层(SoilGrids, 部分点无数据 → 填NaN)
    print("[2/2] 土壤层(SoilGrids 8波段) — 高原/极端区可能缺失")
    soil_df = sample_layer(build_soil_image(), coords, "soil")
    print(f"  土壤层采到: {len(soil_df)}/{len(coords)} 点")

    # 3. 合并: 非土壤层为基础, 土壤层 left join (采不到的填NaN)
    env_df = env_df.drop_duplicates(subset="site_id").set_index("site_id")
    soil_df = soil_df.drop_duplicates(subset="site_id").set_index("site_id")
    merged = env_df.join(soil_df, how="left")
    # 确保列顺序与 GEE_COLS 一致
    for c in GEE_COLS:
        if c not in merged.columns:
            merged[c] = float("nan")
    merged = merged.reset_index().sort_values("site_id").reset_index(drop=True)
    merged = merged[["site_id"] + GEE_COLS]

    out_csv = os.path.join(ROOT, "data", "covariates", "missing_8463_gee_covariates.csv")
    merged.to_csv(out_csv, index=False)
    print(f"\n补采完成: {len(merged)} 点 → {out_csv}")
    print("各列非空率:")
    for c in GEE_COLS:
        nn = merged[c].notna().sum()
        print(f"  {c}: {nn}/{len(merged)} ({nn/len(merged)*100:.1f}%)")


if __name__ == "__main__":
    main()
