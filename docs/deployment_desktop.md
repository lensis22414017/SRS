# 桌面打包(exe / dmg)与地图、AI API 调用方案

## 1. 架构选择

本系统是「前端(Vite/React) + 后端(FastAPI/Python)」。桌面化推荐 **Tauri**(包体小、跨平台、Rust 壳)或 Electron。后端有两种方式:

- **方案A(推荐,演示/单机)**:用 PyInstaller 把 FastAPI 后端打成单可执行(含 sqlite + 模型 joblib + 知识库),Tauri/Electron 启动时拉起本地 `127.0.0.1:8000`,前端打包为静态资源由壳加载。
- **方案B(政务内网)**:后端用 Docker 部署到内网服务器,桌面端仅打包前端,API 指向服务器地址。

## 2. 地图(地图服务)在打包后的 referer/白名单问题

地图服务 key 按「referer 域名白名单」校验。浏览器开发时 referer 是 `http://localhost:5173`;打包后:

- **Tauri**:WebView 的 referer 通常是 `tauri://localhost`(macOS)或 `https://tauri.localhost`(Windows)。需在地图服务控制台把这些以及 `127.0.0.1`、`localhost` 一并加入该 key 的授权域名。
- **Electron**:`file://` 协议无 referer,地图服务会拒绝。解决:用 Electron 的 `session.webRequest.onBeforeSendHeaders` 注入 `Referer: http://127.0.0.1`(已在白名单),或让前端经本地后端做**瓦片代理**(后端转发地图服务瓦片请求,key 留后端,前端不暴露 key,最稳妥)。

**推荐做法(打包通用)**:FastAPI 已提供瓦片代理 `/api/v1/map/tile/{layer}/{z}/{x}/{y}`,后端持 `TIANDITU_KEY` 向地图服务请求并回传。前端 `SiteMap` 在未配置 `VITE_TIANDITU_KEY` 时自动使用本地代理。好处:① key 可不进前端包;② 绕开 WebView referer 限制;③ 内网部署只需后端能出网或预缓存瓦片。开发演示时也兼容前端 `.env.local` 的 `VITE_TIANDITU_KEY`。

## 3. AI(GLM / OpenAI 兼容服务)在打包后的调用

AI key 必须留在**后端**(`.env` 或打包时的安全配置),前端只调 `/api/v1/ai/chat`。这样:
- 打包后 key 不暴露在前端静态资源里;
- 切换供应商(大语言模型 / 硅基流动 / 本地)只改后端 `.env`,前端无感;
- 内网无外网时,可把 `AI_BASE_URL` 指向内网自建 OpenAI 兼容服务。

## 4. 打包步骤概要(方案A + Tauri)

1. 后端:`pyinstaller --onefile --add-data "../data:data" --add-data "../ml:ml" backend/app/main.py`(需写一个启动入口用 uvicorn.run),产出 `srs-backend` 可执行。
2. 前端:`npm run build` 产出 `frontend/dist`。
3. Tauri:`tauri.conf.json` 配置 `beforeBuildCommand`、把 `dist` 作为前端、把 `srs-backend` 作为 sidecar,启动时 spawn 后端。
4. 地图服务:优先在后端 `.env` 配置 `TIANDITU_KEY`;若仍走前端直连,再在控制台加白名单 `tauri://localhost`、`https://tauri.localhost`、`127.0.0.1`、`localhost`。
5. 产物:Windows `.exe`/`.msi`,macOS `.dmg`。

## 5. 待 EXECUTE 的工程项

- [ ] 后端 PyInstaller 启动入口 + 资源打包
- [ ] Tauri/Electron 壳工程 + sidecar 配置
- [ ] 离线瓦片缓存(纯内网无外网场景)
