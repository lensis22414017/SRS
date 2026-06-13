# Docker 验证日志 — 20260612

> **重要**: 审计沙箱**无 Docker、无外网 PyPI、无 npm registry**, 因此下列命令**未在沙箱执行**, 需裴总在本机运行。本文件给出待执行命令、预期与代码级核查结论, 不谎报已通过。

## 1. 代码级预检(沙箱已做)
- `backend/Dockerfile` 存在; `deploy/docker-compose.yml` 含 db(postgres)/redis/backend, healthcheck 就绪。
- 初始化模块齐全: `app.db.bootstrap` / `load_kb` / `load_standard_thresholds` / `load_remediation_cases` 均存在。
- 基线迁移 `backend/alembic/versions/0001_baseline.py` 已新增(create_all 落当前 schema)。
- 全部后端 `*.py` 语法 `py_compile` 通过(不含 .venv)。

## 2. 待本机执行命令(原样照搬)
```bash
bash scripts/run_tests.sh
cd frontend && npm run build
cd /Users/lensis/Claude/Projects/SRS
docker build -f backend/Dockerfile -t srs-backend-fable-validation .
docker run --rm srs-backend-fable-validation pytest -q
cd deploy && docker compose -p srs_fable_validation up -d --build
docker compose -p srs_fable_validation exec backend python -m app.db.bootstrap
docker compose -p srs_fable_validation exec backend python -m app.db.load_kb
docker compose -p srs_fable_validation exec backend python -m app.db.load_standard_thresholds
docker compose -p srs_fable_validation exec backend python -m app.db.load_remediation_cases
docker compose -p srs_fable_validation exec backend pytest -q
docker compose -p srs_fable_validation down -v
```

## 3. 预期与注意
- `run_tests.sh`: 期望 ≥38 passed(新增切分测试后应增加)。
- `docker build`: Dockerfile 装 `requirements.txt`; 报告 PDF 用 xhtml2pdf, **无需** pango 系统库。
- compose 从干净卷初始化 PostgreSQL: `bootstrap` 等价 create_all, 或可改用 `alembic upgrade head`(现已有基线迁移)。
- 若 `docker compose exec` 报后端未就绪, 等 healthcheck 通过再执行 init。

## 4. 执行结果回填区(本机运行后粘贴)
- [ ] run_tests.sh: __ passed
- [ ] npm run build: pass / 主包大小 __
- [ ] docker build: pass
- [ ] docker run pytest: __ passed
- [ ] compose up + 4 个 init: ok
- [ ] compose pytest: __ passed
- [ ] compose down -v: ok
