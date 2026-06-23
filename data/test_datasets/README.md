# 全国数据集切分 — 单场地测试数据集

来源: `data/raw/merged_std33,zh .xlsx` (soil 项目 41504 真实检测行)
切分维度: 省 × Pollution_Type; 每切片 ≤200 真实行(单场地规模)
列: 8 重金属 + pH + 有机质(标准化中文, 匹配 SRS FactorDictionary)
生成: `_generate_splits.py` (可复跑, random_state=42)

| 文件 | 标签 | 点数 | 类型 | 省 | 砷有效 |
|---|---|---|---|---|---|
| site_江西_HM_200点.xlsx | 江西重金属(有色金属区) | 200 | HM | 江西 | 193 |
| site_广东_HM_200点.xlsx | 广东重金属(沿海工业) | 200 | HM | 广东 | 157 |
| site_湖南_HM_200点.xlsx | 湖南重金属(有色金属之乡) | 200 | HM | 湖南 | 123 |
| site_新疆_HM_200点.xlsx | 新疆重金属(干旱区) | 200 | HM | 新疆 | 189 |
