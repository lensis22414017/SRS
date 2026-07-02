# Clean Observations Long Summary v0.8

> 由 seal_pack_repair_v0.8.py 从 02_gold_mapping + 04_feature_tables 反推生成。
> 不重新映射,仅把 measured/family/proxy 三类因子的有效(非缺失)观测展开为长表。

## 行数 / 因子数
- 总行数(有效观测): 443,121
- 因子数(去重 factor_id): 54

## 按 data_role 透视
{
  "proxy_covariate": 311620,
  "measured": 128145,
  "family_aggregate": 3356
}

## 按 track 透视
{
  "production": 443121
}

## 字段数
- 输出字段: 27 列
- 字段清单见 clean_long_data_dictionary_v0.8.csv

## 用途
1. 规则判障碍
2. 阈值匹配
3. OI 目标生成审计
4. 补测建议
5. KOS 前置输入
