# 数据切分泄漏审计与修复 — 20260612

审计人: Fable 5（高级研究软件审计代理）
范围: `data/splits` 四个真实切分在 `id_DOI` / `id_Source` 双键上的跨集泄漏。

## 1. 结论
**修复前: 存在泄漏(6 对)。修复后: 零泄漏(沙箱实测验证)。**

## 2. 根因
原 `ml/models/dataset_splits.py`:
- `valid` 按 **DOI** 分组留出, `test`/`external` 按 **Source** 分组留出;
- 但一个 DOI 常跨多个 Source、一个 Source 常跨多个 DOI;
- 按单键分组无法保证另一键不跨集 → 同一 DOI 的行因 Source 不同被分到 train 与 test;
- 原检查仅覆盖 `train-vs-valid(DOI)`、`train-vs-test(Source)` 两对, 漏掉交叉键与 valid-vs-test/external。

## 3. 修复前实测(旧 CSV)
| 配对 | 键 | 重叠数 |
|---|---|---|
| train vs valid | id_Source | 24 ❌ |
| train vs test | id_DOI | 125 ❌ |
| train vs external | id_DOI | 10 ❌ |
| valid vs test | id_Source | 7 ❌ |
| valid vs external | id_Source | 1 ❌ |
| test vs external | id_DOI | 3 ❌ |

共 **6 对泄漏**。

## 4. 修复方案
将 `(DOI, Source)` 视为二部图, 用并查集求**连通分量**(同一 DOI 或同一 Source 相连的行同属一个分量), 以连通分量为最小不可分单位整体分配到 train/valid/test/external。这样**任意两个真实切分在 DOI 与 Source 两个键上都零跨集**。缺失键的行归入各自单点分量。

## 5. 修复后实测(重建 CSV, 沙箱 pandas 独立复核)
- 全部 6 配对 × 2 键 = 12 项检查: **重叠均为 0** ✅
- 行数: train_real 18741 / valid 5957 / test 8855 / external 5509, 合计 39062, 不丢行不重复。
- `dataset_split_registry.json` 的 `leakage_checks.all_passed = True`。

## 6. 测试
`backend/tests/test_dataset_splits.py` 已强化为:
- `test_zero_cross_split_leakage_both_keys`: 用"Source 跨多 DOI"夹具, 断言全配对双键零重叠(旧逻辑此用例必失败)。
- `test_all_rows_partitioned_no_loss`: 不丢行不重复。
- `test_leakage_helper_detects_planted_overlap`: 负对照, 植入重叠必须被检出。
- `test_committed_real_splits_are_clean`: 校验已生成 CSV 零泄漏(无文件则 skip)。
沙箱已运行前 3 个(仅依赖 pandas/numpy)全部通过; 第 4 个在本机 pytest 环境运行。

## 7. 残留风险
- `site_id` 键当前 model_ready 无该列, 若后续引入需纳入同一连通分量逻辑。
- 行级随机切分仍可作为"记忆程度"对照, 但**不得作为主泛化指标**(见 leakage_prevention_checklist)。
