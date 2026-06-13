# 依赖安装清单(裴总一次性安装用)

## 一键安装(推荐)

```bash
cd /Users/lensis/Claude/Projects/SRS
bash scripts/setup.sh
```

该脚本会:建 `backend/.venv` → 装下表全部 Python 包 → 建表 → 写入 4 角色/4 演示账号/技术库 → 知识库入库(122 因子/403 规则)→ 跑 pytest。

## Python 依赖(均在 `backend/requirements.txt`)

| 包 | 版本 | 用途 | 阶段 | 系统依赖 |
|---|---|---|---|---|
| fastapi | 0.115.0 | Web 框架 | D3+ | 无 |
| uvicorn[standard] | 0.30.6 | ASGI 服务器 | D3+ | 无 |
| sqlalchemy | 2.0.34 | ORM | D1+ | 无 |
| alembic | 1.13.2 | 数据库迁移 | D1+ | 无 |
| psycopg2-binary | 2.9.9 | PostgreSQL 驱动 | 部署 | 无(wheel) |
| pydantic / pydantic-settings | 2.9.2 / 2.5.2 | 校验/配置 | D1+ | 无 |
| python-jose[cryptography] | 3.3.0 | JWT | D13 | 无 |
| bcrypt | >=4.2 | 密码哈希 | D13 | 无 |
| python-multipart | 0.0.9 | 文件上传 | D3 | 无 |
| pandas | 2.2.2 | 数据处理 | D2+ | 无 |
| numpy | 1.26.4 | 数值 | D2+ | 无 |
| openpyxl | 3.1.5 | Excel 解析 | D3 | 无 |
| scikit-learn | 1.5.1 | RF 模型 | D6 | 无(wheel) |
| shap | 0.46.0 | 可解释性 | D7 | 无(wheel) |
| joblib | 1.4.2 | 模型持久化 | D6 | 无 |
| jinja2 | 3.1.4 | 报告模板 | D12 | 无 |
| weasyprint | 62.3 | HTML→PDF | D12 | **需系统库**(见下) |
| redis | 5.0.8 | 缓存(可选) | 后续 | 需 redis 服务 |
| pytest / httpx | 8.3.2 / 0.27.2 | 测试 | 全程 | 无 |

## 需要额外系统库的项

**weasyprint(D12 报告 PDF 才用到)** 在 macOS 需要 Pango 等系统库:

```bash
brew install pango gdk-pixbuf libffi
```

weasyprint 已默认注释(D12 时取消注释并先装系统库)。**重要: 本机为 Python 3.13, requirements 已全部改为 >= 宽松版本以匹配 3.13 的 wheel。**

**PostgreSQL / Redis** 仅 Docker 部署或生产需要;开发默认用 sqlite,无需安装。Docker 方式见 `README.md`。

## 验证安装成功

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload
# 浏览器访问 http://127.0.0.1:8000/health  应返回 {"status":"ok",...}
```
