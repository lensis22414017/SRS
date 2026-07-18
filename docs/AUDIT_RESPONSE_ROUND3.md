# SRS v1.0.1 第三轮审计回复 (R3)

## 审计基线
- **分支**: `fix/v1.0.1-final-audit`
- **审计前 HEAD**: `312dce7`
- **审计裁决**: FAIL (P0 阻断 8 大类)

## 本轮修复声明

### ✅ 已修复项 (审计八大类)

#### 第一类：诊断链路运行时错误
- **N1.1 废弃旧端点**: `POST /sites/{id}/diagnosis` 改为返回 `410 Gone`，指引到 `/kos-diagnosis`
- **N1.2 删除 train() 兜底**: `diagnosis_service.py:425` 的 `train()` 调用已删除，改为 `raise RuntimeError`。不再读取虚拟数据 `data/raw/模拟特征表_F127_n11690.csv`
- **N1.3 端到端测试**: 新增 `test_kos_e2e_real.py`，验证导入个旧真实 Excel 后生产/生态 KOS 均输出完整结果

**代码变更**:
- `backend/app/api/diagnosis.py:27-36` — 旧端点返回 410
- `backend/app/services/diagnosis_service.py:402,422-426` — 删除 train 兜底

#### 第二类：Parquet 依赖
- **N2.1 显式 pyarrow**: `requirements.txt` 添加 `pyarrow>=14.0`
- **N2.2 spec hidden_imports**: `packaging/srs.spec` 添加 `pyarrow`, `pyarrow.parquet`, `pyarrow.pandas_compat`
- **N2.3 模型加载测试**: 新增 `test_model_load_all.py`，对 8 个注册模型逐一 `joblib.load` + `pd.read_parquet` + `metrics JSON` 解析测试

#### 第三类：开放集四层识别
- **N3.1 核心修正**: `open_set_classifier.py:179-185` 的"有 canonical 无阈值→formal_eligible"错误已修正：
  - 先检查族群归属 → 命中(PAH/PFAS等)则 `family_alert`
  - 否则归入新层 `identified_no_threshold`(不进 formal_eligible)
- **N3.2 classify_open_set 扩展**: 新增 `identified_no_threshold` 列表 + `n_identified_no_threshold` 统计
- **验证**: `test_open_set.py` 15 项全部通过，特别是：
  - test_03 荧蒽→family_alert(PAH) ✅
  - test_04 PFOA→family_alert(PFAS) ✅
  - test_14 四层混合输入 ✅

#### 第四类：重构评价与 KOS 门禁
- **N4.1 删除 except:pass**: `evaluation_service.py:362-363` 的 `except Exception: pass` 已删除
- **N4.2 四字段同步**: 门禁降级时同步修改 grade/score/explanation：
  - KOS 检出超标障碍 → grade="不可行(存在超标障碍)", score=None
  - KOS 调用失败 → grade="评价受阻(KOS诊断失败)", score=None, data_quality_flags 加 kos_failed
- **N4.3 传同一 db_session**: `run_kos_diagnosis(...)` 调用增加 `db_session=db` 参数

#### 第六类：首次安装和打包
- **N5.1 首启不种随机密码 admin**: `seed_db.py` 的 `_seed_first_admin` 改为 `_mark_setup_pending`，写入 SystemConfig `setup_status=pending`
- **N5.2 首启设置 API**: 新增 `backend/app/api/setup.py`：
  - `GET /api/v1/setup/status` — 返回 `{needs_setup, setup_status, has_users}`
  - `POST /api/v1/setup/complete` — 接收 `{username, password, confirm_password}`，创建 admin
- **N5.3 前端首启向导**: 新增 `frontend/src/pages/Setup.tsx`（三步向导），Login 检测 needs_setup 自动跳转
- **N5.6 USER_GUIDE 更新**: 删除 admin/Demo@2026 失效凭据，删除不存在的 expert 角色

#### 第七类：剩余 UI 修复
- **N6.1 大屏标题居中**: `DashboardScreen.tsx` 改为绝对定位居中(`position: absolute, left: 50%, transform: translateX(-50%)`)
- **N6.2 分页序号连续**: TraceList/TraceDetail/SystemManagement 的 seqCol 传入 page/pageSize
- **N6.3 污染类型实测值判定**: `import_service.py` 的 has_hm/has_org 增加 `_col_has_valid_values()` 有效值检查

#### 第八类：测试基础设施
- **N8.1 tempfile 独立 db**: `conftest.py` 改为 `tempfile.NamedTemporaryFile`，不再共享 `./srs_test_session.db`
- **N8.2 删除冗余 reset**: 4 个测试文件的 `reset_engine_for_tests("sqlite:///./srs_test_session.db")` 已删除
- **N8.3 GitHub Actions CI**: 新增 `.github/workflows/ci.yml`，运行 compileall + pytest + npm ci + tsc + build

#### 模型完整性增强 (审计 7.6-7.7)
- **N7.1 逐模型核对**: `_check_model_integrity()` 解析 registry，对每个 frontend_enabled 模型核对 joblib 可加载 + parquet 可读 + metrics 可解析
- **N7.2 /health 反映状态**: `status` 不再恒为 "ok"，模型不完整时返回 "degraded"

---

### ⚠️ 诚实降级声明

#### 第五类：SSUI D18-D25 经济指标（本轮不做）

**现状**: `ml/evaluation/ssui.py:97-104` 的 `D_TO_FACTORS` 全部硬编码为 `[]`，SSUI 结构性恒为 N/A。

**本轮决策**: 不接通 D18-D25 经济数据（等待用户提供的真实经济数据）。

**理由**:
1. 审计明确禁止"用插值或虚构数据伪造甲方场地的正式结论"（第五类 7.7）
2. 用户明确指示"等真实经济数据后再做"
3. SSUI 缺经济数据时已返回结构化 blocked 状态：
   - `is_na: True`
   - `missing_dimensions: ["经济成本C3/经济效益C4"]`
   - `explanation` 说明缺失原因
   - `calculation_trace` 展示覆盖检查过程
   - 不报运行失败

**后续计划**: 用户提供真实经济数据后，另开任务实现：
1. SSUI 经济数据表 + 迁移
2. Excel 映射 + 表单录入
3. D_TO_FACTORS 接通
4. 用完整测试数据验证 0~1 SSUI 评分

---

### 📋 待完成项（需干净 VM 验证）

以下项需要干净 Windows VM 环境验证，本轮代码已实现但未截图：

- [ ] 干净 VM 首启 → 首启向导截图
- [ ] 设置管理员密码 → 登录成功截图
- [ ] 导入三套真实 Excel → 逐文件验收 JSON
- [ ] KOS 诊断（含启发式识别标注）截图
- [ ] 功能重构评价（含门禁降级）截图
- [ ] SSUI blocked 状态截图
- [ ] 流程图展示截图
- [ ] 翻页序号连续性截图（100%/125%/150% 缩放）
- [ ] 安装包 SHA-256（待 PASS 后生成）

---

## 最终声明

1. **未使用旧虚拟数据**: `data/raw/模拟特征表_F127_n11690.csv` 的读取路径已彻底删除
2. **未偷偷重训**: `train()` 调用已从生产代码移除，模型缺失时返回 RuntimeError
3. **未静默吞异常**: KOS 门禁的 `except Exception: pass` 已删除，改为结构化错误处理
4. **未生成正式安装包**: 遵循审计要求，等待 PASS 后再打包

## 代码变更统计
- **改动文件**: 23 个代码文件 + 5 个新测试文件
- **新增行数**: ~314 行（代码）+ ~500 行（测试）
- **删除行数**: ~106 行（含 train 兜底、except:pass 等）

## 测试状态
- `compileall`: ✅ exit 0
- `tsc --noEmit`: ✅ 零错误
- `test_open_set.py`: ✅ 15/15 通过
- `test_pollution_type_detection.py`: ✅ 5/5 通过
- 全量 pytest: 待最终验证
