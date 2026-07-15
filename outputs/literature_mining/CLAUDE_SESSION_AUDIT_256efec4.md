# Claude 会话数据提取审计

## 审计结论

结论不是二选一：现有稀疏性同时来自原文/SI缺失和提取实现缺陷。实现缺陷曾系统性放大缺失、误分类与伪配对，因此旧表不能直接视为可信训练真值。

| 类别 | 会话内可复核证据 | 影响 | 当前处置 |
|---|---|---|---|
| 单位实现缺陷 | `phase14_extract_batch2.py` 定义了 `detect_unit()`，但三处记录输出硬编码 `unit = Unknown` | 可转换浓度被误记为未知单位，制造结构性缺失 | 已改为单位传播并加测试 |
| HM+OP语义缺陷 | `phase14_batch2_pipeline.py` 先按 `paper_id` 聚合，只要同一论文分别出现HM和OP就整体进入 `hm_op` | 不同样点被伪配对，复合污染标签失真 | 已改为 `sample_id` 级交集判定 |
| 介质实现缺陷 | 无目录、无MD、异常或无关键词时均返回/回退 `soil` | 水体、沉积物等可能被误纳入土壤训练集 | 已取消缺失介质默认soil |
| 值域实现缺陷 | HM浓度 `-1 <= v <= 1` 被整体删除以规避相关系数 | 合法低浓度HM被系统删除 | 已改为基于表语义过滤，不按低值一刀切 |
| 来源客观限制 | 会话多次记录主文只有汇总统计、样点表在SI、部分SI物理缺失 | 即便修复提取器，样点级完整协变量仍不足 | 只纳入可追溯原生SI；不足部分降级参考 |

因此：旧数据‘看起来很稀疏’不能证明原文天然稀疏；修复后仍缺的字段，才可归入来源限制。

## 会话元数据

- 会话文件：`C:\Users\曾鸿\.claude\projects\C--Users---\256efec4-085c-4e28-a198-da065f46a8b0.jsonl`
- 文件大小：24,913,781 bytes
- 记录类型计数：`{'last-prompt': 551, 'mode': 543, 'permission-mode': 543, 'attachment': 3439, 'file-history-snapshot': 157, 'user': 1590, 'ai-title': 542, 'assistant': 2861, 'queue-operation': 3829, 'system': 233, 'custom-title': 134, 'agent-name': 134, 'file-history-delta': 2}`

## 原始实现证据（行号为会话首次写入版本）

### `phase14_extract_batch2.py`

```text
80: UNIT_PATTERNS = {
89: BLACKLIST_SAMPLE_IDS = re.compile(
112: def detect_unit(text):
113:     for unit, pat in UNIT_PATTERNS.items():
115:             return unit
218:                 for ci, sample_id in sample_cols:
222:                         if BLACKLIST_SAMPLE_IDS.match(val_str):
229:                                     "sample_id": f"{paper_id}_{sample_id.replace(' ','_')}",
230:                                     "site_label": sample_id,
233:                                     "unit": "Unknown",
245:             sample_id = row[0].strip() if row[0] else f"S{ri}"
247:             if BLACKLIST_SAMPLE_IDS.match(sample_id):
249:             if re.match(r"^(mean|average|median|sd|std|min|max|range|cv|变异|平均|均值|中位|标准|最小值|最大值|范围)$", sample_id, re.I):
259:                                 "sample_id": f"{paper_id}_{sample_id.replace(' ','_')}",
260:                                 "site_label": sample_id,
263:                                 "unit": "Unknown",
291:                                 "sample_id": f"{paper_id}_{sample_label.replace(' ','_')}",
295:                                 "unit": "Unknown",
```

### `phase14_batch2_pipeline.py`

```text
2: 一步完成: 清理 → 填充 matrix → 整合到 manual_extract/
19:     "correlation matrix", "pearson", "spearman", "correlation coefficient",
22:     "rotated component", "旋转成分", "component matrix",
27: # ===== Matrix 关键词 =====
28: MATRIX_KEYWORDS = {
38: def is_valid_value(val_str, pollutant_std):
62: def infer_matrix_from_md(dir_name):
63:     """从 MinerU 解析的 MD 文本关键词匹配推断 matrix。"""
65:     if not full.exists(): return "soil", "no_dir"
70:         if not md_files: return "soil", "no_md"
73:         return "soil", "err"
78:     for mtype, patterns in MATRIX_KEYWORDS.items():
82:     if not scores: return "soil", "default"
104:     rows = [r for r in rows if is_valid_value(r["value"], r["pollutant_std"])]
115:     # 3. 填充 matrix (按 dir_name 批处理)
125:     print(f"Matrix 目录映射: {len(dir_map)}/{len(pids)}")
127:     matrix_cache = {}
129:         if pid not in matrix_cache:
131:                 m, note = infer_matrix_from_md(dir_map[pid])
134:             matrix_cache[pid] = (m, note)
135:     matrix_counts = Counter(m for m, _ in matrix_cache.values())
136:     print(f"Matrix 分布: {dict(matrix_counts.most_common())}")
139:     EXISTING_FIELDS = ["paper_id", "sample_id", "pollutant_std", "value", "unit",
140:                        "evidence_location", "matrix", "site_type", "province",
153:     by_paper = defaultdict(list)
155:         by_paper[r["paper_id"]].append(r)
161:     for pid, prows in by_paper.items():
163:         has_hm = bool(pollutants & hm_pollutants)
164:         has_op = bool(pollutants & op_pollutants)
166:         if has_hm and has_op:
169:         elif has_op:
172:         elif has_hm:
179:         m, note = matrix_cache.get(pid, ("soil", "default"))
198:                 nr["matrix"] = m
199:                 nr["extract_notes"] = f"phase14_batch2; matrix={note}; conf={r.get('confidence','')}; flag={r.get('value_flag','')}"
208:     print(f"原始: {len(rows)} 行 / {len(by_paper)} 论文")
```
