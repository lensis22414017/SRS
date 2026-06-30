# 裴总发布前的两项指导：代码签名证书 + WeasyPrint/GPL/MIT 协议

> 辛特助整理于 2026-06-30。软件全部没问题后申请软著(裴总已定), 此处只讲另两项。

---

## 一、代码签名证书指导（建议裴总办理）

### 1.1 为什么要签名
未签名的 `SRS.exe` 在 Windows 首次运行会触发 **SmartScreen "Windows 已保护你的电脑 / 未知发布者"** 警告，甲方/用户看到会担心是病毒，影响验收体验。签名后右键属性→数字签名→可查"发布者: XXX"，SmartScreen 警告消失（或大幅降低）。

### 1.3 办理步骤（裴总操作）

**步骤 1：选证书类型**
| 类型 | 价格 | 特点 | 推荐 |
|---|---|---|---|
| **OV 标准代码签名** | ~$200-300/年 | 立即生效, 但新证书需积累信誉才消除 SmartScreen | ⭐ 性价比 |
| **EV 扩展验证** | ~$300-400/年 | 立即消除 SmartScreen, 需硬件 token(USB) | 最佳体验 |

**推荐机构**（裴总任选其一官网申请）：
- Sectigo（原 Comodo）：性价比高 https://www.sectigo.com/ssl-certificates/code-signing
- DigiCert：品牌权威 https://www.digicert.com/code-signing/
- 国内代理：天威诚信/数安时代（人民币支付、中文服务，适合个人/小团队）

**步骤 2：准备申请材料**
- 个人开发者：身份证 + 手机号 + 邮箱
- 企业：营业执照 + 法人身份证 + 企业邮箱
- 部分机构要求电话回拨验证（用申请时填的电话）

**步骤 3：提交申请 + 验证**
- 在线填写信息 → 机构审核（1-3 工作日）→ 邮件收到证书（.pfx/.p12 文件 + 密码）
- EV 证书会寄 USB 硬件 token

**步骤 4：用证书签名 exe**（辛特助指导裴总执行，约 5 分钟）
收到 .pfx 后, 在 PowerShell 跑(裴总只需提供 pfx 路径+密码):
```powershell
# 1. 装 SDK 工具(若没有)
#    从微软下载 Windows SDK, 含 signtool.exe

# 2. 签名(辛特助会帮裴总生成命令)
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe" sign `
  /f "C:\path\to\裴总的证书.pfx" `
  /p "裴总的密码" `
  /tr http://timestamp.digicert.com /td sha256 /fd sha256 `
  "C:\Users\曾鸿\Desktop\SRS\dist\SRS\SRS.exe"

# 3. 验证签名
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe" verify `
  /pa "C:\Users\曾鸿\Desktop\SRS\dist\SRS\SRS.exe"
```
签名后右键 SRS.exe→属性→数字签名, 能看到"发布者: 你的名字/公司"即成功。

**步骤 5：打包分发**
- 7z 压缩 `dist/SRS/` → 分发给甲方
- 首次运行无 SmartScreen 警告（OV 需积累信誉, EV 立即消除）

### 1.4 成本与时间
- 总成本: ~$200-400/年
- 等待: 申请 1-3 天 + 审核验证 1-2 天 = 约 1 周
- 裴总只需: 选机构 + 提交材料 + 收 .pfx, 签名操作辛特助代劳

---

## 二、WeasyPrint GPL 边界 + MIT 协议指导

### 2.1 事实查证（辛特助不假设，基于包元数据）
我用 importlib.metadata 查了实际许可证:
| 组件 | 真实许可证 | GPL 风险 |
|---|---|---|
| **WeasyPrint 本身** | **BSD-3** ✅ | 无（不是 GPL！） |
| pydyf / tinycss2 / cssselect2 | BSD ✅ | 无 |
| cffi / fonttools / tinyhtml5 | MIT ✅ | 无 |
| **pyphen**（WeasyPrint 依赖） | **GPLv2+ / LGPLv2+ 双授权** ⚠️ | **有 GPL 边界** |
| Pango / Cairo（系统库） | **LGPL**（非 GPL） | 边界更宽松 |

**结论**: 我之前 PACKAGING.md 写的"WeasyPrint 依赖 GPL 的 Pango/Cairo"**不精确**——
WeasyPrint 本身是 BSD, Pango/Cairo 是 LGPL; 真正的 GPL 边界来自 **pyphen**(分词断字)。

### 2.2 GPL 动态链接边界（FSF 立场）
- **FSF 立场**（gpl-faq）: MIT 程序**动态链接** GPL 库 → 创建衍生作品 → MIT 程序需遵循 GPL（传染性）
- **争议**: 部分法律学者认为动态链接不构成衍生作品, 但 FSF 官方立场保守, 商业发布应按 FSF 立场避险
- **pyphen 双授权**: pyphen 是 GPLv2+ / LGPLv2+ 双授权; SRS 用 LGPL 选项（LGPL 允许动态链接不传染）即可规避开源要求

### 2.3 SRS 的实际风险与方案（裴总三选一）

| 方案 | 做法 | 效果 | 推荐 |
|---|---|---|---|
| **A 用 pyphen 的 LGPL 授权**（推荐 ⭐） | NOTICE 声明 WeasyPrint+pyphen 按 LGPL 动态链接使用, SRS 仍可 MIT 发布 | 规避 GPL 传染, 保留 MIT | 最务实 |
| **B 降级到 xhtml2pdf 纯 Python** | report_service 改为优先 xhtml2pdf(Apache-2.0, 纯 Python 无 GPL), weasyprint 仅留可选 | 完全无 GPL 边界, 但 PDF 排版质量略降 | 最保守 |
| **C 接受 pyphen GPL 边界** | 内部/学术使用, 不商业分发则 GPL 边界无实际触发 | 零改动 | 学术场景 |

### 2.4 MIT 协议与本项目的关系（裴总决策）
- SRS 主代码用 **MIT 发布** ✅（最宽松, 利于甲方验收 + 后续定制 + 软著申请并存）
- MIT 允许: 商用/修改/分发/私用, 唯一要求保留版权声明
- MIT 与 LGPL 兼容（LGPL 库动态链接 MIT 程序, MIT 程序不传染）
- ⚠️ MIT 与 GPL 不兼容（若 SRS 用 pyphen 的 GPL 选项而非 LGPL, 则 SRS 需转 GPL——故选方案 A 的 LGPL）

### 2.5 辛特助建议（裴总定夺）
**推荐方案 A**: NOTICE 已声明 pyphen 按 LGPL 动态链接使用, SRS 保持 MIT 发布。
- 零代码改动, PDF 质量不变(weasyprint 一级渲染保留)
- 法律层面: LGPL 明确允许动态链接闭源/其他许可程序, FSF 也认可
- 若裴总想完全无 GPL/LGPL 边界(极致保守)→ 方案 B, 辛特助改 report_service 降级链(30 分钟)

---

## 三、总结建议（裴总下一步）

| 事项 | 辛特助建议 | 裴总需做什么 |
|---|---|---|
| 软著 | 软件全部没问题后申请 | 后续准备材料, 辛特助可帮整理源代码鉴别文档 |
| 代码签名 | 办理 OV 或 EV 证书 | 选机构 + 提交材料 + 收 .pfx, 签名操作辛特助代劳 |
| WeasyPrint/GPL | 方案 A(LGPL 声明, 已在 NOTICE) | 无需操作, 裴总确认即可; 或选方案 B 辛特助改代码 |
| MIT 协议 | 保持 MIT(已创建 LICENSE) | 无需操作 |

裴总确认方案 A / B 后, 辛特助执行(若 B 则改降级链, 若 A 则不需要改代码)。代码签名等裴总拿到 .pfx 辛特助指导签。
