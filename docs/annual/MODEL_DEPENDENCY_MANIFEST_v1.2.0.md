# SRS v1.2.0 模型与依赖清单

由 `docs/annual/build_manifest_v12.py` 从源码树生成。sha256 均为文件内容哈希（LFS 对象取指针中的 oid）。

## 1 模型工件（课题一 KOS，p3_alpha，未重训）

| 文件 | 类型 | 字节 | sha256 |
|---|---|---|---|
| ml/artifacts/p3_alpha/all_eco_ContextOnly_RandomForest.joblib | 实体文件 | 76216743 | `fe6787f082485c8f6dd13aac87b0974bdc30c0fe06d9ca4ed06ecce912f1eef2` |
| ml/artifacts/p3_alpha/all_eco_ContextOnly_RandomForest_metrics.json | 实体文件 | 1091 | `b27fb9485d57477c14e0a14525fba472600d9e46d3a77c0d7b34768c45373c18` |
| ml/artifacts/p3_alpha/all_eco_Full_RandomForest.joblib | 实体文件 | 50424533 | `8515405a0aeadca2db6310da5ef3947b2dc16155b3a16627cb0e2738a4dddcc6` |
| ml/artifacts/p3_alpha/all_eco_Full_RandomForest_metrics.json | 实体文件 | 1038 | `79c5a372fd1ba1028dc7d35a7efaf12c2b2201e0a78d95e3db496811b6de70d8` |
| ml/artifacts/p3_alpha/all_eco_Full_RandomForest_shap_global.parquet | 实体文件 | 9308 | `d57c467b778b74adbfbc4b745314c8b509ad1dc5446dc82e81390906eb2d7669` |
| ml/artifacts/p3_alpha/all_eco_Full_RandomForest_shap_local.parquet | 实体文件 | 50914 | `6ef4c9550ddbf86f19df8da0f846e5d84fe93990b19bcef1a4a9f0f0e2645ac7` |
| ml/artifacts/p3_alpha/all_eco_Full_RandomForest_shap_meta.json | 实体文件 | 290 | `60a0cc9575bb20dca04051668ecceb77487cbe3e9042c347c6ee2d6c68a43fde` |
| ml/artifacts/p3_alpha/all_eco_MeasuredOnly_RandomForest.joblib | 实体文件 | 50024580 | `846628513a43ba09375f0199ad202bb8344d1d877a95a2aa7acca0e149c63c7f` |
| ml/artifacts/p3_alpha/all_eco_MeasuredOnly_RandomForest_metrics.json | 实体文件 | 1085 | `a6da51d91f9a495a840ed879eb794222109ca630711ccc7d3917c577dee9957b` |
| ml/artifacts/p3_alpha/all_prod_ContextOnly_RandomForest.joblib | 实体文件 | 77361257 | `2da37dad70e31d6c1205e39e71e627a987fdf44b5229476d0bfc97e442f686ab` |
| ml/artifacts/p3_alpha/all_prod_ContextOnly_RandomForest_metrics.json | 实体文件 | 1095 | `55fc775957139d0d727fcfea89f8a5918c9fb82668b9a66924685590f21d4f9e` |
| ml/artifacts/p3_alpha/all_prod_Full_RandomForest.joblib | 实体文件 | 52044391 | `11458cd9aa0a5b1954e98fd337a25bafee2d4f30c2b74ea625a529b871bfa021` |
| ml/artifacts/p3_alpha/all_prod_Full_RandomForest_metrics.json | 实体文件 | 1027 | `ceee2918fe347d175e64c3826ec01c4c60303c99e517994b90535f9f2f7d9d23` |
| ml/artifacts/p3_alpha/all_prod_Full_RandomForest_shap_global.parquet | 实体文件 | 9130 | `2a08abc16cd8b240dfb640e920e6e307f2affca4dd418919c4c18a651956832e` |
| ml/artifacts/p3_alpha/all_prod_Full_RandomForest_shap_local.parquet | 实体文件 | 52582 | `c82dd1a830ad377d56fa5b78d81b4f9d032232721b2297c30eee592735391214` |
| ml/artifacts/p3_alpha/all_prod_Full_RandomForest_shap_meta.json | 实体文件 | 290 | `b7eb1aabb5baa29e8b3a8fddbd071822ca727890659b26bb6fcbb753c5e2a293` |
| ml/artifacts/p3_alpha/all_prod_MeasuredOnly_RandomForest.joblib | 实体文件 | 51616358 | `02e54c306fc8f3511736a4f444434eb4b41907558317d5310da7b1c3dd3ca177` |
| ml/artifacts/p3_alpha/all_prod_MeasuredOnly_RandomForest_metrics.json | 实体文件 | 1071 | `fe756a45bb0690a9e0b4a6511d5caaa0fd22cf8b24fb342123299c319bc28aec` |
| ml/artifacts/p3_alpha/hm_eco_Full_RandomForest.joblib | 实体文件 | 43776340 | `2028e0b82c14985f03b367ca2f1e1fe097e961ab2843d2cd99a2dd4ddb389a20` |
| ml/artifacts/p3_alpha/hm_eco_Full_RandomForest_metrics.json | 实体文件 | 1024 | `3e3b9c94a65058c6abc6e94cc614890df84e56cead21b5aa8bde7e8ad1599f09` |
| ml/artifacts/p3_alpha/hm_eco_Full_RandomForest_shap_global.parquet | 实体文件 | 8709 | `ca9a97ed1a2f8b673c63e262c8c1cdc94a022a11f7690bb3f2158e56c064e78b` |
| ml/artifacts/p3_alpha/hm_eco_Full_RandomForest_shap_local.parquet | 实体文件 | 31389 | `1643e7625486c080ba7eb5453e79e09af300ae59db9a4ffcec77e5daeae963d7` |
| ml/artifacts/p3_alpha/hm_eco_Full_RandomForest_shap_meta.json | 实体文件 | 305 | `dfa48ad34944e98d81e4086c66917f8a186fc662a03fa9ccd6625c28eb7e7af0` |
| ml/artifacts/p3_alpha/hm_op_eco_Full_RandomForest.joblib | 实体文件 | 5123410 | `64e8d978d5fb67a87e5c2571b142efc4369f35d370e9c6d2929f3ee54cd13266` |
| ml/artifacts/p3_alpha/hm_op_eco_Full_RandomForest_metrics.json | 实体文件 | 957 | `36651c80d11582a80ad5967f7b4846c650c2f23c3b2c43873a3cf87bc141d823` |
| ml/artifacts/p3_alpha/hm_op_eco_Full_RandomForest_shap_global.parquet | 实体文件 | 11643 | `881468007f45eb2647ccdeb413a32ae2ae27d7015f71472cb476675959f53c7d` |
| ml/artifacts/p3_alpha/hm_op_prod_Full_RandomForest.joblib | 实体文件 | 4731732 | `79b0e616b95352e5dfec51892f430d94d8c76022b8d9afdbd18ed9b275dda92f` |
| ml/artifacts/p3_alpha/hm_op_prod_Full_RandomForest_metrics.json | 实体文件 | 961 | `55ac9348f2004a07835a1d8ccb15c6bdfb9940a9e5a1bb2fd05c90a931828b3e` |
| ml/artifacts/p3_alpha/hm_op_prod_Full_RandomForest_shap_global.parquet | 实体文件 | 11622 | `0ea326e7d53baa83a39c87343dd9f0ac50909184f86de6c07f6d25d520afc471` |
| ml/artifacts/p3_alpha/hm_prod_Full_RandomForest.joblib | 实体文件 | 46794870 | `b0aae5bebc670e6d95920b6c3c1c32670f51a6052f9b4c08bd90ea27fb09c21d` |
| ml/artifacts/p3_alpha/hm_prod_Full_RandomForest_metrics.json | 实体文件 | 1020 | `fa4ec3594f893e1e48ccb141403744a38784176c80f7a3027385d825377511b5` |
| ml/artifacts/p3_alpha/hm_prod_Full_RandomForest_shap_global.parquet | 实体文件 | 8670 | `6dccd98e99c861253a5bf9806ba09591a74f550a691c807e1be3fde1905f5e3d` |
| ml/artifacts/p3_alpha/hm_prod_Full_RandomForest_shap_local.parquet | 实体文件 | 31612 | `05242703349bbabd6873b50987324dd90dc2dca931bcd3d76071880c84584f9f` |
| ml/artifacts/p3_alpha/hm_prod_Full_RandomForest_shap_meta.json | 实体文件 | 292 | `178929da0b642a5cbee8f6a7ffc0fe52f53aa71c0e89036993cfdff388eed243` |
| ml/artifacts/p3_alpha/model_registry_v0.8.json | 实体文件 | 9210 | `81785c4795b1eb7d1d42ac80193df6edaf86043924bd40bc6958d7d4818aa24f` |
| ml/artifacts/p3_alpha/op_eco_Full_RandomForest.joblib | 实体文件 | 1767076 | `d59375f9233be6e760c807a4ea4ae94949efd79ff1950d9d87b857112b752d3e` |
| ml/artifacts/p3_alpha/op_eco_Full_RandomForest_metrics.json | 实体文件 | 1017 | `238bf725d13920e413fd8fb5da3d1a2d325ea263909fb6c926e25a6e05b63e1f` |
| ml/artifacts/p3_alpha/op_eco_Full_RandomForest_shap_global.parquet | 实体文件 | 8765 | `4dac429431f423067a6d3a1b12830d8c33e99fd65ceb2ad2440795529394d8b7` |
| ml/artifacts/p3_alpha/op_eco_Full_RandomForest_shap_local.parquet | 实体文件 | 16700 | `302fc80d332faedf76d831682a5f55194ecf4e5b10cebb472343ff2940bc9b1f` |
| ml/artifacts/p3_alpha/op_eco_Full_RandomForest_shap_meta.json | 实体文件 | 304 | `4e0496b594bbbe67a8fe961063472b6a2c9d4052a0ad4b5080438a6e2b740b76` |
| ml/artifacts/p3_alpha/op_prod_Full_RandomForest.joblib | 实体文件 | 1293462 | `6ff58f9f7e4ba53130b9c146f7817fccaaa33724640a3dfeb13ecf5877ef4644` |
| ml/artifacts/p3_alpha/op_prod_Full_RandomForest_metrics.json | 实体文件 | 1035 | `83c9cfd1067e114e6a82d6be5b89836d5bb33ca7d4068d2bb953ea8d6b3f954c` |
| ml/artifacts/p3_alpha/op_prod_Full_RandomForest_shap_global.parquet | 实体文件 | 8204 | `e5dbc3ecc8b5159b852c258105d0beae97eacc684014cd53a2ebc5cd8a9a4bf2` |
| ml/artifacts/p3_alpha/op_prod_Full_RandomForest_shap_local.parquet | 实体文件 | 12365 | `5acd5902b1fe667ad84d99b1803350e55ac999d9d23a47043aae8071c1e857e5` |
| ml/artifacts/p3_alpha/op_prod_Full_RandomForest_shap_meta.json | 实体文件 | 287 | `222d978029a8966aae0eecacfd45cc8aa5f60cc1d76b736846817c94b3a702fb` |
| ml/artifacts/p3_alpha/p3_alpha_summary.csv | 实体文件 | 2085 | `01d5f438d0d2873230c810fddbe687e96d932ae29433c6125c29483700820e97` |

## 2 方法与标准数据

| 文件 | 用途 | sha256 |
|---|---|---|
| data/standards/gb36600_2018_official.csv | GB 36600-2018 表1/表2 官方转录 | `515e347db85183de939b2bf5c04776671727b025648361e80f9588e8677e3b6a` |
| data/standards/gb36600_2018_v12.csv | GB 36600 运行时阈值表 | `08145eb11df0a3f71c4dd4c0257b277fbf7f93c6be962f33819a5e0ab2f399e9` |
| data/standards/gb15618_2018_official.csv | GB 15618-2018 表1–3 官方转录 | `0506739e8ad6979e3f4b470218fb67fb1111769ae3d454d85393833c19d09188` |
| data/standards/gb15618_2018_v12.csv | GB 15618 运行时阈值表 | `5172c843c0f705e13b8264e5167caa2012c4a8b7df9949c707bfa4b7b67937c1` |
| data/standards/ssui_weights_pptx_v1.json | 课题三 SSUI 权重（方法 PPT 第13/14页） | `1d168520990309244c3bb187af1786c4540f49fad1cc6f51f9fb149cf2fac684` |
| ml/evaluation/reconstruction_m2025.py | 课题二 冻结方法 M-REC-2025 | `3564e867b17d4338d58fccd10e7329a8802a7b3fc6a5b8d9fe1eafb42189069a` |
| ml/models/feature_mapping.json | 特征映射 | `7bd3680aba82b0d34b157219ba2bf323a93dc891ef12d0cc43b3495536a6a7be` |

## 3 后端依赖（backend/requirements.txt）

```
# 兼容 Python 3.11 - 3.13
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0.36
alembic>=1.14
psycopg2-binary>=2.9.10
pydantic>=2.9
pydantic-settings>=2.6
python-jose[cryptography]>=3.3
bcrypt>=4.2
python-multipart>=0.0.12
pandas>=2.2.3
numpy>=2.0
# R3 审计第二类: 显式声明 pyarrow(KOS 读 SHAP parquet 工件必需, 之前是 pandas 隐式依赖)
pyarrow>=14.0
openpyxl>=3.1
scikit-learn>=1.5.2
shap>=0.47
joblib>=1.4
jinja2>=3.1
PyYAML>=6.0.2
# --- 报告内采样点静态图件(matplotlib 离线渲染, 不依赖天地图 key) ---
matplotlib>=3.8
xhtml2pdf>=0.2.16
reportlab>=4.2
svglib==1.5.1
python-docx>=1.1
redis>=5.0
pytest>=8.3
pytest-timeout>=2.3
httpx>=0.27
# --- D12 PDF 报告生成 (macOS: brew install pango gdk-pixbuf libffi; Linux: apt-get install libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev) ---
weasyprint>=63
```

## 4 前端依赖（frontend/package.json）

| 包 | 版本 |
|---|---|
| @ant-design/icons | ^5.5.1 |
| antd | ^5.21.0 |
| axios | ^1.7.7 |
| echarts | ^5.5.1 |
| echarts-for-react | ^3.0.2 |
| katex | ^0.16.11 |
| leaflet | ^1.9.4 |
| react | ^18.3.1 |
| react-dom | ^18.3.1 |
| react-katex | ^3.0.1 |
| react-router-dom | ^6.26.2 |

## 5 打包工具

- Python 3.11（Windows 构建，actions/setup-python）；PyInstaller（`packaging/srs.spec`）
- Inno Setup 6（`packaging/srs_setup.iss`）
- Node 20（前端构建）
