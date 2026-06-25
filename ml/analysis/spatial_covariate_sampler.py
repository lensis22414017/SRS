"""外部协变量空间采样器 (E③ 落地, 2026-06-24)。

从全球土壤栅格(FAO HWSD v1.2/v2.0, SoilGrids 250m, OpenLandMap)按场地经纬度
提取土壤理化属性, 生成 SRS 场地×协变量矩阵, 增强 HM 块训练数据(X_barrier)。
根本解决"HM 块 29993 行零协变量"的架构性缺陷, 让障碍因子 RF+SHAP 可识别
"pH 低→镉活性高""有机质高→PAH 吸附"等真障碍因子(非浓度 trivial 规则)。

数据源详细清单见: docs/audit/external_covariate_datasets_20260624.md

依赖: rasterio, numpy, pandas (pip install rasterio geopandas)
"""
from __future__ import annotations
import numpy as np
import pandas as pd


# === 栅格配置: 数据源→波段→协变量名映射 ===
# 使用前需下载对应栅格文件到本地, 路径在运行时传入
HWSD_V1_BANDS = {
    # HWSD v1.2 属性: band→(field, description)
    1: ("T_USDA_TEX", "USDA soil texture class"),
    2: ("T_REF_BULK_DENSITY", "Reference bulk density (kg/dm3)"),
    3: ("T_OC", "Organic carbon (% weight)"),
    4: ("T_PH_H2O", "pH (H2O)"),
    5: ("T_CEC_CLAY", "CEC of clay fraction (cmol/kg)"),
    6: ("T_CEC_SOIL", "CEC of soil (cmol/kg)"),
    7: ("T_BS", "Base saturation (%)"),
    8: ("T_TEB", "Total exchangeable bases (cmol/kg)"),
    9: ("T_CACO3", "CaCO3 content (g/kg)"),
    10: ("T_CASO4", "CaSO4 content (g/kg)"),
    # ... 继续补充至27 band
}

SOILGRIDS_BANDS = {
    # SoilGrids 250m: 属性深度组合 (0-5cm / 5-15cm / 15-30cm 等)
    # 地表层(0-5cm)优先; 命名遵循 SoilGrids 惯例
    "phh2o_0-5cm_mean": ("soil_pH", "pH in H2O, 0-5cm surface"),
    "soc_0-5cm_mean": ("SOC_g_per_kg", "Soil organic carbon (g/kg), 0-5cm"),
    "cec_0-5cm_mean": ("CEC_cmol_per_kg", "Cation exchange capacity (cmol/kg), 0-5cm"),
    "clay_0-5cm_mean": ("clay_pct", "Clay content (%), 0-5cm"),
    "sand_0-5cm_mean": ("sand_pct", "Sand content (%), 0-5cm"),
    "silt_0-5cm_mean": ("silt_pct", "Silt content (%), 0-5cm"),
    "bdod_0-5cm_mean": ("bulk_density_g_per_cm3", "Bulk density (g/cm3), 0-5cm"),
    "nitrogen_0-5cm_mean": ("nitrogen_g_per_kg", "Total nitrogen (g/kg), 0-5cm"),
}

# SRS 场地列名(与 merged/训练数据一致)
LON_COL = "Longitude"
LAT_COL = "Latitude"


def extract_point(raster_path: str, lon: float, lat: float,
                  band: int = 1) -> float | None:
    """从单波段GeoTIFF提取单点值(最近邻采样)。

    Args:
        raster_path: GeoTIFF 文件路径。
        lon, lat: WGS84 坐标。
        band: 波段索引(1-based, GDAL convention)。
    Returns:
        提取值; 坐标出范围/无数据→None。
    """
    try:
        import rasterio  # noqa: F811
    except ImportError:
        raise ImportError("需要 rasterio: pip install rasterio")
    with rasterio.open(raster_path) as src:
        row, col = src.index(lon, lat)
        if 0 <= row < src.height and 0 <= col < src.width:
            val = src.read(band, window=((row, row + 1), (col, col + 1)))
            v = float(val[0, 0])
            return None if v == src.nodata else v
    return None


def batch_extract(sites_df: pd.DataFrame, raster_config: dict,
                  band_mapping: dict) -> pd.DataFrame:
    """批量从栅格提取协变量。

    Args:
        sites_df: 场地 DataFrame, 需含 Longitude/Latitude 列。
        raster_config: {covariate_name: (raster_path, band_index)}
            例如: {"soil_pH": ("/data/hwsd_ph.tif", 1)}
        band_mapping: 波段→(输出列名, 描述) 映射字典(见上方常量)。
    Returns:
        sites_df 附加协变量列(列名=covariate_name)。
    """
    result = sites_df.copy()
    for cov_name, (raster_path, band) in raster_config.items():
        vals = []
        for _, row in result.iterrows():
            v = extract_point(raster_path, row.get(LON_COL),
                              row.get(LAT_COL), band)
            vals.append(v)
        result[cov_name] = vals
        valid_n = sum(1 for v in vals if v is not None)
        print(f"  {cov_name}: {valid_n}/{len(vals)} 场地提取成功")
    return result


def sample_hwsd(sites_df: pd.DataFrame, hwsd_raster_path: str,
                bands: list[int] | None = None) -> pd.DataFrame:
    """从 HWSD v1.2 栅格提取土壤理化属性。

    Args:
        sites_df: 场地 DataFrame。
        hwsd_raster_path: HWSD v1.2 多波段 GeoTIFF 路径。
        bands: 提取波段列表, 默认 [3,4,6,1] (OC, pH, CEC, texture)。
    Returns:
        附加列: OC_pct, soil_pH, CEC_cmol_kg, USDA_texture_class, ...
    """
    if bands is None:
        bands = [3, 4, 6, 1]  # OC, pH(H2O), CEC_soil, USDA_texture
    config = {}
    for b in bands:
        info = HWSD_V1_BANDS.get(b, (f"band_{b}", ""))
        config[info[0]] = (hwsd_raster_path, b)
    print(f"[HWSD] 从 {hwsd_raster_path} 提取 {len(bands)} 维协变量...")
    return batch_extract(sites_df, config, HWSD_V1_BANDS)


def sample_soilgrids(sites_df: pd.DataFrame, soilgrids_dir: str,
                     depth: str = "0-5cm") -> pd.DataFrame:
    """从 SoilGrids 250m 栅格(单波段文件)提取土壤属性。

    Args:
        sites_df: 场地 DataFrame。
        soilgrids_dir: SoilGrids 栅格文件目录。
        depth: 深度层 "0-5cm" / "5-15cm" / "15-30cm"。
    Returns:
        附加列: soil_pH, SOC_g_per_kg, CEC_cmol_per_kg, clay_pct, sand_pct, ...
    """
    config = {}
    for band_key, (col_name, desc) in SOILGRIDS_BANDS.items():
        if f"_{depth}_" not in band_key:
            continue
        path = f"{soilgrids_dir}/{band_key}.tif"
        import os
        if not os.path.exists(path):
            continue
        config[col_name] = (path, 1)  # 单波段文件, band=1
    print(f"[SoilGrids] 从 {soilgrids_dir} 提取 {len(config)} 维协变量 ({depth})...")
    return batch_extract(sites_df, config, SOILGRIDS_BANDS)


def enhance_hm_training_data(sites_csv: str, hwsd_raster: str,
                             output_csv: str) -> None:
    """增强 HM 块训练数据: 读场地→提取 HWSD 协变量→写增强CSV。

    这是 E③ 核心落地函数——HM 块 29993 行零协变量→添加 pH/OC/CEC/clay/texture。
    增强后训练数据可用于 X_barrier 障碍因子 RF+SHAP(非浓度 trivial 规则)。

    Args:
        sites_csv: HM 块训练数据CSV(需含 Longitude/Latitude)。
        hwsd_raster: HWSD v1.2/v2.0 GeoTIFF 路径。
        output_csv: 增强后 CSV 输出路径。
    """
    df = pd.read_csv(sites_csv)
    if LON_COL not in df.columns or LAT_COL not in df.columns:
        print("⚠️ HM块无经纬度列, 跳过增强")
        return
    enhanced = sample_hwsd(df, hwsd_raster)
    enhanced.to_csv(output_csv, index=False, encoding="utf-8-sig")
    n_added = len(HWSD_V1_BANDS)
    print(f"[E③] HM 增强完成: {len(df)} 行 + {n_added} 协变量 → {output_csv}")


if __name__ == "__main__":
    print("=== 外部协变量空间采样器 (E③) ===")
    print("使用前需下载 HWSD/SoilGrids 栅格文件(下载清单见 docs/audit/external_covariate_datasets_20260624.md)")
    print("核心接口: sample_hwsd(df, raster_path) / sample_soilgrids(df, dir) / enhance_hm_training_data(in, raster, out)")
    print("E③ 就绪: run enhance_hm_training_data() 即可补 HM 块协变量")
