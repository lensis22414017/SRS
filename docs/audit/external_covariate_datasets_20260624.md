# 外部含理化协变量土壤数据集检索清单（E③ 数据支撑, 2026-06-24）

> H4 竞品完善 - 补 SRS 训练数据协变量缺失短板（HM 块 29993 行零协变量 → 空间匹配 pH/有机质/CEC/黏粒）

## 一级推荐（直接可用，含理化指标+全球覆盖）

| 数据集 | 分辨率 | 核心字段 | 来源 | 下载 |
|---|---|---|---|---|
| **FAO HWSD v2.0** | 30 arc-sec (~1km) | SOC, pH, CEC, clay, sand, silt, bulk density, 7 depth layers | FAO/IIASA/ISRIC | [HWSD v2.0](https://repository.soilwise-he.eu/cat/collections/metadata:main/items/54aebf11-ec73-4ff8-bf6c-ecff4b0725ea) |
| **FAO HWSD v1.2** | 30 arc-sec | Organic Carbon, pH, CEC, clay fraction, texture, water capacity, depth, salinity | FAO/IIASA/JRC/中科院 | [Download ZIP](https://www.fao.org/fileadmin/user_upload/soils/HWSD%20Viewer/HWSD.zip) |
| **SoilGrids 250m v2.0** | 250m | pH, SOC, bulk density, clay/sand/silt %, CEC, N 等 | ISRIC | [GEE Community](https://gee-community-catalog.org/) |
| **OpenLandMap-soildb** | 30m (2000-2022 time-series) | SOC, SOCD, pH(1:1 H2O), bulk density, sand/silt/clay | OpenGeoHub | [Zenodo](https://zenodo.org/records/15470432) |
| **中国土壤数据库 (Shangguan 2014)** | 30 arc-sec, 8 layers to 2.3m | pH, organic matter, silt, clay, sand, CEC | BNU全球变化研究组 | [BNU Soil](http://globalchange.bnu.edu.cn/research/soil2) |
| **LimeSoDa (基准ML数据集)** | 点数据 | **SOM/SOC + pH + clay**(每个数据集必有) | Zenodo community | [Zenodo](https://zenodo.org/records/14932573) |
| **OpenLandMap compiled ESS points** | 点数据 | 化学性质(pH/OC/N/P/K) + 物理性质(BD/clay/silt/sand) | OpenGeoHub GitLab | [GitLab](https://gitlab.com/openlandmap/compiled-ess-point-data-sets) |

## 二级推荐（特定用途）

| 数据集 | 说明 |
|---|---|
| **SoilHive** | 418,636+ 点数据聚合平台，API可用。含多源土壤化学/物理数据 (Varda AG) |
| **Global Soil organic C map (GSOCmap)** | FAO 1km SOC 0-30cm |
| **KSSL (USDA)** | 美国为主+1100国际剖面，化学分析+理化全谱 |
| **Nature Commun 2025 (Qi et al.)** | 全球土壤金属迁移性 ML 模型，确认 clay+pH+CEC+OC 为关键描述符 |

## E③ 实施方案

1. **空间匹配**：SRS 场地经纬度 → HWSD/SoilGrids 提取栅格值 (pH/OC/CEC/clay/sand/silt/bulk density)
2. **增强 HM 块**：29993 行场地经纬度→栅格采样→补协变量列
3. **重训验证**：X_barrier (协变量) → RF 障碍因子 → SHAP → 验证泛化 (group-split + 空间CV)
4. **期望效果**：协变量 pH×CEC×clay 解释重金属迁移性（Nature 2025 铁证），降低标签泄漏虚高

## 检索方法
- Firecrawl search: "global soil dataset physicochemical properties pH organic matter CEC clay"
- Scrape: FAO Soils Portal + ISRIC catalog
- 参见 docs/audit/external_covariate_datasets_20260624.md
