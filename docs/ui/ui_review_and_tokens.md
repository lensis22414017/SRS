# UI 设计规范与组件规范

**文档版本**：v0.1  
**编写日期**：2026-06-16  
**编写人**：辛特助  
**状态**：草稿，持续更新

---

## 1. 设计 Token

### 1.1 主题色

| Token | 值 | 用途 |
|---|---|---|
| `colorPrimary` | `#0f3d6e` | 主色：按钮、侧边栏、标题 |
| `colorText` | `#374151` | 正文 |
| `colorTextSecondary` | `#6b7280` | 次要文字、描述 |
| `colorBorder` | `#e5e7eb` | 边框 |
| `colorBgContainer` | `#ffffff` | 卡片/容器背景 |
| `colorBgLayout` | `#f0f2f5` | 页面背景 |

### 1.2 状态色

| 语义 | 值 | 对应 Ant Design token |
|---|---|---|
| 成功 / 达标 | `#16a34a` | `colorSuccess` |
| 警告 / 轻度超标 | `#f59e0b` | `colorWarning` |
| 危险 / 严重超标 | `#dc2626` | `colorError` |
| 信息 / 中性 | `#3b82f6` | `colorInfo` |
| 未知 / 无数据 | `#64748b` | — |

### 1.3 地图污染状态色（`SiteMap.STATUS_COLOR`）

| key | 颜色 | 语义 |
|---|---|---|
| `danger` / `high` | `#dc2626` | 高风险 / 严重超标 |
| `warning` / `medium` | `#f59e0b` | 中等风险 |
| `success` / `low` | `#16a34a` | 低风险 / 达标 |
| `info` | `#3b82f6` | 信息提示 |
| `unknown` | `#64748b` | 状态未知 |

### 1.4 字号

| 用途 | 大小 | 说明 |
|---|---|---|
| 页面标题 | 16px / 600 | 卡片 `title` |
| 正文 | 14px / 400 | 默认 |
| 说明/辅助 | 12px / 400 | 描述文字、空态 |
| KPI 数字 | 24–32px / 700 | Dashboard 指标卡 |

### 1.5 间距与圆角

| Token | 值 |
|---|---|
| 卡片内边距 | 16px（Ant Design 默认） |
| 页面外边距 | `margin: 16px`（Content 层） |
| 圆角 | 8px（Ant Design 默认） |
| 卡片阴影 | `box-shadow: 0 1px 4px rgba(0,0,0,.06)` |

---

## 2. 页面清单

| # | 页面名称 | 组件文件 | 路由 | 状态 |
|---|---|---|---|---|
| 1 | 登录页 | `Login.tsx` | `/login` | ✅ |
| 2 | 首页 / 数据概览 | `Dashboard.tsx` | `/` | ✅ |
| 3 | 场地列表 | `SiteList.tsx` | `/sites` | ✅ |
| 4 | 场地详情 | `SiteDetail.tsx` | `/sites/:id` | ✅ 含地图 |
| 5 | 数据导入页 | `DataUpload.tsx` | `/sites/import` | ✅ |
| 6 | 字段映射页（交互式） | — | — | ⚠️ 待开发（当前为固定模板） |
| 7 | 数据校验结果页（独立） | — | — | ⚠️ 待开发（当前嵌入导入页） |
| 8 | 障碍因子诊断页 | `ObstacleAnalysis.tsx` | `/obstacle` | ✅ |
| 9 | SHAP 解释（含于诊断页） | 含于 ObstacleAnalysis | — | ✅ |
| 10 | 功能重构评价页 | `ReconstructionAnalysis.tsx` | `/reconstruction` | ✅ |
| 11 | SSUI 评价页 | `SSUIAnalysis.tsx` | `/ssui` | ✅ |
| 12 | 方案推荐页 | `RecommendationPage.tsx` | `/recommend` | ✅ |
| 13 | 全流程追溯列表 | `TraceList.tsx` | `/trace` | ✅ |
| 14 | 全流程追溯详情 | `TraceDetail.tsx` | `/trace/:id` | ✅ 含报告生成+下载 |
| 15 | 报告预览页（内嵌 PDF） | — | — | ⚠️ 待开发 |
| 16 | 系统管理页 | `SystemManagement.tsx` | `/system` | ✅ 含操作日志 Tab |
| 17 | 操作日志（独立路由） | 含于 SystemManagement | `/system` → Tab | ✅（Tab 实现） |
| 18 | 错误页（404/403/500） | `ErrorPage.tsx` | `*` catch-all | ✅ 2026-06-16 |
| 19 | 空状态组件（通用） | `EmptyState.tsx` | — | ✅ 2026-06-16 |
| 20 | 角色权限（含于系统管理） | 含于 SystemManagement | `/system` → Tab | ✅ |

---

## 3. SiteMap 组件规范

**文件**：`frontend/src/components/SiteMap.tsx`

### 3.1 Props

| Prop | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `sites` | `SitePoint[]` | ✅ | — | 点位数组，含经纬度 |
| `layerData` | `MapLayerData` | — | — | 后端返回的 GeoJSON + 图例数据 |
| `height` | `number` | — | `400` | 地图高度（px） |
| `zoom` | `number` | — | `5` | 初始缩放级别 |
| `onMarkerClick` | `(s: SitePoint) => void` | — | — | 点位点击回调 |

### 3.2 行政区懒加载规则

| 缩放级别 | 加载层级 | 样式 |
|---|---|---|
| 1–5 | 省界 | 深蓝粗轮廓 `#0f3d6e` weight=1.2 |
| 6–8 | 地市 | 中蓝 `#1d6fb8` weight=0.8 |
| 9+ | 县/区 | 灰细 `#64748b` weight=0.5 |

### 3.3 瓦片底图优先级

1. **L1 矢量底图**（默认，无需配置）：阿里 DataV GeoJSON，完全离线
2. **L2 MBTiles 离线影像**（可选）：需提前导入 `data/geo/tiles/*.mbtiles`
3. **L3 天地图在线**（可选）：需配置 `VITE_TIANDITU_KEY`

### 3.4 必须支持的状态

| 状态 | 实现方式 |
|---|---|
| 加载中 | Leaflet 地图容器初始化前显示 Spin |
| 无坐标数据 | `hasCoords=false` 时显示 `EmptyState`（"暂无点位坐标"） |
| 瓦片加载失败 | `tileError=true` 时降级至纯矢量底图，不报错崩溃 |
| 点位为空 | 正常渲染地图，无标注 |

---

## 4. 通用组件规范

### 4.1 EmptyState

**文件**：`frontend/src/components/EmptyState.tsx`

用于列表页、图表区、分析结果等无数据时的统一展示。

```tsx
<EmptyState
  title="暂无场地数据"
  description="请先导入场地检测数据"
  actionLabel="前往导入"
  onAction={() => nav('/sites/import')}
/>
```

### 4.2 ErrorPage

**文件**：`frontend/src/pages/ErrorPage.tsx`

支持 403 / 404 / 500。
- 作为路由 catch-all：`<Route path="*" element={<ErrorPage />} />`
- 作为权限拦截：`<ErrorPage status={403} />`
- 作为 React Router v6 errorElement：`errorElement={<ErrorPage />}`

---

## 5. 所有关键页面必须支持的状态

| 状态 | 要求 |
|---|---|
| 加载态 | `loading={true}` + AntD Spin / Table loading |
| 空态 | 使用 `EmptyState` 组件，不得显示空白或 0 条提示 |
| 错误态 | `message.error()` 提示 + 页面不崩溃 |
| 权限不足 | 显示 `ErrorPage status={403}` 或 `message.error("无权限")` |
| 导出 | 核心数据页支持 Excel / CSV 导出，调用后端接口 |
| 刷新 | 提供刷新按钮或自动重试 |
| 面包屑 | 二级以上页面有返回入口（Back 按钮或侧边栏高亮） |

---

## 6. 禁止项

- 大量使用 emoji 作为正式图标（侧边栏 `🌱` 为临时占位，正式交付前需替换为 SVG 图标）
- 图表无标题、无单位、无数据来源
- 按钮点击无 loading 反馈
- 地图使用静态图片替代真实 Leaflet 渲染
- 各页面自定义空态样式（统一使用 `EmptyState`）
