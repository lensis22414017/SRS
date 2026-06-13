# SRS 桌面打包

## 目录结构

```
packaging/
├── launcher.py      # 桌面启动器 (托盘图标 + 浏览器自动打开)
├── srs.spec         # PyInstaller 打包配置
├── start.sh         # 快速启动脚本 (双击运行)
├── icon.icns        # macOS 应用图标 (待添加)
└── README.md        # 本文件
```

## 快速启动 (开发模式)

```bash
# 方式 1: Python 启动器 (含托盘图标)
DYLD_LIBRARY_PATH=/opt/homebrew/lib backend/.venv/bin/python packaging/launcher.py

# 方式 2: Shell 脚本 (最简单)
chmod +x packaging/start.sh
./packaging/start.sh     # 默认 8000 端口
./packaging/start.sh 8080 # 自定义端口
```

## 打包为 .app (macOS)

### 前置条件
```bash
# 1. 确保前端已构建
cd frontend && npm run build

# 2. 准备应用图标 (可选)
# 将 1024x1024 的 PNG 放入 packaging/icon.png
# 生成 .icns:
#   mkdir icon.iconset
#   sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
#   sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
#   iconutil -c icns icon.iconset -o packaging/icon.icns
```

### 构建
```bash
cd /Users/lensis/Claude/Projects/SRS
backend/.venv/bin/pyinstaller packaging/srs.spec --clean
```

输出: `dist/SRS.app/`

### 构建产物大小估算
- Python + 依赖: ~300 MB
- ML 库 (sklearn/shap/xgboost): ~200 MB
- 前端 + 模板: ~3 MB
- 知识库数据: ~1 MB
- **总计: ~500 MB** (可接受用于企业交付)

## 打包为 .exe (Windows)

在 Windows 上执行相同的 PyInstaller 构建:
```cmd
cd C:\path\to\SRS
backend\.venv\Scripts\python -m PyInstaller packaging\srs.spec --clean
```

## 当前打包就绪度

| 项目 | 状态 |
|------|------|
| 前端一体化服务 | ✅ 已完成 |
| 数据库自动初始化 | ✅ 已完成 |
| 平台感知数据路径 | ✅ 已完成 |
| 端口可配置 | ✅ 已完成 |
| 托盘图标启动器 | ✅ 已完成 |
| PyInstaller 配置 | ✅ 已完成 |
| 应用图标 | ⚠️ 待添加 (PNG/ICNS) |
| 代码签名 | 📋 待做 (macOS 公证) |
| DMG 打包 | 📋 待做 (create-dmg) |
| Windows 安装器 | 📋 待做 (NSIS/InnoSetup) |

## 下一步

1. 准备应用图标 (`packaging/icon.png`)
2. 运行 `pyinstaller packaging/srs.spec` 测试构建
3. 创建 DMG 安装包:
   ```bash
   brew install create-dmg
   create-dmg --volname "SRS" --window-size 600 400 \
     --app-drop-link 400 200 "dist/SRS-0.1.0.dmg" "dist/SRS.app/"
   ```
4. macOS 代码签名与公证 (如需分发到非开发者 Mac)
