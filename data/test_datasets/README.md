# 全国数据集切分 — 单场地测试数据集

来源: `data/raw/merged_std33,zh .xlsx` (soil 项目 41504 真实检测行)
切分: 省 × Pollution_Type; 每切片 ≤200 真实行(random_state=42)
三类: HM(重金属) / OP(有机) / HMOP(复合=重金属+有机)

| 文件 | 标签 | 点数 | 类型 | 省 | 列集 |
|---|---|---|---|---|---|
| site_江西_HM_200点.xlsx | 江西重金属(有色金属区) | 200 | HM | 江西 | HM |
| site_广东_HM_200点.xlsx | 广东重金属(沿海工业) | 200 | HM | 广东 | HM |
| site_湖南_HM_200点.xlsx | 湖南重金属(有色金属之乡) | 200 | HM | 湖南 | HM |
| site_新疆_HM_200点.xlsx | 新疆重金属(干旱区) | 200 | HM | 新疆 | HM |
| site_北京_OP_200点.xlsx | 北京有机污染(PAH为主) | 200 | OP | 北京 | OP |
| site_广东_OP_200点.xlsx | 广东有机污染(工业) | 200 | OP | 广东 | OP |
| site_山东_OP_92点.xlsx | 山东有机污染 | 92 | OP | 山东 | OP |
| site_江苏_OP_155点.xlsx | 江苏有机污染 | 155 | OP | 江苏 | OP |
| site_浙江_OP_175点.xlsx | 浙江有机污染 | 175 | OP | 浙江 | OP |
| site_广东_HM+OP_64点.xlsx | 广东复合污染 | 64 | HM+OP | 广东 | HMOP |
| site_江苏_HM+OP_32点.xlsx | 江苏复合污染 | 32 | HM+OP | 江苏 | HMOP |
| site_浙江_HM+OP_15点.xlsx | 浙江复合污染 | 15 | HM+OP | 浙江 | HMOP |
| site_辽宁_HM+OP_16点.xlsx | 辽宁复合污染 | 16 | HM+OP | 辽宁 | HMOP |
| site_山东_HM+OP_24点.xlsx | 山东复合污染 | 24 | HM+OP | 山东 | HMOP |
| site_海南_HM+OP_58点.xlsx | 海南复合污染 | 58 | HM+OP | 海南 | HMOP |
