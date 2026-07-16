/**
 * 方法流程图配置 — 每个核心模块的输入/处理/输出/依据定义
 * 由 MethodFlowDrawer 消费渲染
 */
export interface FlowItem {
  label: string;
  desc: string;
}

export interface FlowRef {
  title: string;
  source: string;
  url?: string;
}

export interface FlowConfig {
  key: string;
  title: string;
  subtitle?: string;
  svgPath: string;
  inputs: FlowItem[];
  processes: FlowItem[];
  outputs: FlowItem[];
  references: FlowRef[];
}

// SVG 文件路径 — 指向 public/assets/flows/ 目录, 若文件不存在 Drawer 显示友好占位
const svg = (name: string) => `/assets/flows/${name}.svg`;

export const METHOD_FLOWS: Record<string, FlowConfig> = {
  obstacle_analysis: {
    key: "obstacle_analysis",
    title: "障碍因子分析",
    subtitle: "RF + SHAP 双轨综合诊断",
    svgPath: svg("obstacle_analysis"),
    inputs: [
      { label: "场地检测数据", desc: "采样点污染物浓度、土壤理化性质、肥力指标等长表数据，来自场地导入与数据管理模块" },
      { label: "GEE 空间协变量", desc: "NDVI、年降水量、年均温、海拔、SOC、CEC、黏粒含量等 14 项卫星遥感/地理空间数据" },
      { label: "统一障碍因子知识库", desc: "含因子编码、中文名称、分类体系、阈值标准（GB 15618 / GB 36600 等）" },
      { label: "修复后用途", desc: "生产用地或生态用地，决定诊断使用哪一轨（生产轨/生态轨）的专属模型" },
    ],
    processes: [
      { label: "数据预处理", desc: "缺失值中位数填充、特征标准化（Z-score）、异常值 Winsorize 截尾（1%-99%）" },
      { label: "特征空间对齐", desc: "将场地检测因子映射到模型训练特征空间，计算特征覆盖率（coverage）指标" },
      { label: "RF 双轨预测", desc: "分别使用生产轨和生态轨随机森林模型，输出每个采样点的障碍概率 proba" },
      { label: "TreeSHAP 解释", desc: "基于树模型结构的精确 SHAP 值计算：全局特征重要性排序 + 单采样点局部 SHAP 贡献" },
      { label: "影响方向判定", desc: "Spearman 秩相关确定每个因子是正向加重障碍（+）还是负向缓解障碍（-）" },
      { label: "LLM 报告润色", desc: "AI 将技术性结论转化为通俗语言，供非技术背景人员阅读" },
    ],
    outputs: [
      { label: "关键障碍因子排序", desc: "按 |SHAP| 影响程度降序排列的障碍因子列表，含类别、方向、重要性数值" },
      { label: "模型验证指标", desc: "Spearman 秩相关系数及其等级解读（优秀/良好/一般/偏低）" },
      { label: "影响方向分布", desc: "正向加重与负向缓解因子的比例饼图，辅助判断场地障碍的整体倾向" },
      { label: "采样点风险成因", desc: "每个采样点各因子的局部 SHAP 贡献值，热力图展示风险空间分布" },
      { label: "诊断报告 (PDF)", desc: "可导出的一键诊断报告，含场地背景、因子排序、模型指标、可视化图表" },
    ],
    references: [
      { title: "Lundberg & Lee (2017) — A Unified Approach to Interpreting Model Predictions", source: "NeurIPS 2017" },
      { title: "Breiman (2001) — Random Forests", source: "Machine Learning, 45(1), 5-32" },
      { title: "GB 15618-2018 土壤环境质量 农用地土壤污染风险管控标准（试行）", source: "生态环境部 / 国家市场监督管理总局" },
      { title: "GB 36600-2018 土壤环境质量 建设用地土壤污染风险管控标准（试行）", source: "生态环境部 / 国家市场监督管理总局" },
    ],
  },

  reconstruction_eval: {
    key: "reconstruction_eval",
    title: "功能重构可行性评价",
    subtitle: "生态功能 + 生产功能双维度量化评估",
    svgPath: svg("reconstruction_eval"),
    inputs: [
      { label: "障碍因子诊断结果", desc: "RF+SHAP 诊断输出的关键障碍因子列表及影响程度" },
      { label: "场地基础属性", desc: "土壤类型、pH、有机质、CEC、容重、质地等理化指标" },
      { label: "评价指标体系", desc: "生产功能指标（肥力、结构、水分等）与生态功能指标（生物多样性、缓冲能力等）" },
      { label: "权重配置", desc: "基于专家打分或熵权法的各指标权重，支持按用地类型差异化配置" },
    ],
    processes: [
      { label: "指标标准化", desc: "各指标归一化到 [0,1] 区间，正向指标与负向指标分别采用极差标准化公式" },
      { label: "生产功能评价", desc: "加权求和计算生产功能重构可行性得分，覆盖肥力、结构、水分、污染胁迫四个维度" },
      { label: "生态功能评价", desc: "加权求和计算生态功能重构可行性得分，覆盖生物多样性、栖息地、缓冲、自净四个维度" },
      { label: "综合等级判定", desc: "生产与生态得分取加权综合，按阈值划分等级：高可行 / 中可行 / 低可行 / 不可行" },
      { label: "限制因子识别", desc: "单项指标得分低于阈值的因子被标记为限制因子，提示重构瓶颈" },
    ],
    outputs: [
      { label: "综合可行性得分", desc: "0-100 分的综合评分，含等级标签（高/中/低/不可行）" },
      { label: "双维度雷达图", desc: "生产功能与生态功能各子维度的得分雷达图，直观对比强弱项" },
      { label: "限制因子清单", desc: "拉低综合得分的瓶颈因子列表，含当前值、阈值、差距" },
      { label: "评价报告 (PDF)", desc: "可导出的功能重构评价报告" },
    ],
    references: [
      { title: "HJ 25.5-2018 污染地块风险管控与土壤修复效果评估技术导则", source: "生态环境部" },
      { title: "GB 15618-2018 农用地土壤污染风险管控标准", source: "生态环境部" },
      { title: "土壤环境质量评价技术规范（征求意见稿）", source: "生态环境部" },
    ],
  },

  ssui_eval: {
    key: "ssui_eval",
    title: "SSUI 可持续利用评价",
    subtitle: "修复后场地中长期持续利用潜力评估",
    svgPath: svg("ssui_eval"),
    inputs: [
      { label: "修复后场地参数", desc: "修复目标值、残余风险水平、用地类型、规划用途" },
      { label: "安全性维度指标", desc: "残余污染物浓度、生态毒性、地下水影响、人体健康风险" },
      { label: "经济性维度指标", desc: "修复成本、维护费用、土地增值潜力、开发收益预估" },
      { label: "时间权重函数", desc: "不同时间尺度的衰减函数，反映风险随时间的变化" },
      { label: "管理调节因子", desc: "长期监测计划、制度控制措施、应急响应能力" },
    ],
    processes: [
      { label: "安全性维度评分", desc: "基于残余风险和暴露途径的量化评分" },
      { label: "经济性维度评分", desc: "基于成本收益分析的经济可行性评分" },
      { label: "SSUI 综合指数计算", desc: "安全性 × 经济性的加权综合，乘以防衰减的时间权重函数" },
      { label: "管理因子调节", desc: "乘以管理调节系数（0.5-1.5），反映管护措施对可持续性的影响" },
      { label: "可持续等级判定", desc: "按 SSUI 阈值划分：高度可持续 / 可持续 / 基本可持续 / 不可持续" },
    ],
    outputs: [
      { label: "SSUI 综合指数", desc: "0-1 范围的可持续利用综合指数" },
      { label: "可持续等级", desc: "四级等级标签（高度可持续/可持续/基本可持续/不可持续）" },
      { label: "双轴柱状图", desc: "各指标归一化得分与权重的双轴对比" },
      { label: "评价报告 (PDF)", desc: "可导出的 SSUI 评价报告" },
    ],
    references: [
      { title: "HJ 25.5-2018 污染地块风险管控与土壤修复效果评估技术导则", source: "生态环境部" },
      { title: "GB/T 21010-2017 土地利用现状分类", source: "国家标准化管理委员会" },
      { title: "污染场地可持续修复评估框架 (SURF)", source: "Sustainable Remediation Forum" },
    ],
  },

  recommendation: {
    key: "recommendation",
    title: "方案推荐",
    subtitle: "基于诊断与评价结果的技术库智能匹配",
    svgPath: svg("recommendation"),
    inputs: [
      { label: "障碍因子诊断结果", desc: "关键障碍因子列表、影响方向、严重程度" },
      { label: "功能重构评价结果", desc: "生产/生态功能重构可行性得分及限制因子" },
      { label: "SSUI 评价结果", desc: "可持续利用等级及关键风险因子" },
      { label: "修复技术库", desc: "含技术名称、适用污染物、适用条件、成本、工期、优缺点、禁用条件等" },
    ],
    processes: [
      { label: "障碍因子匹配", desc: "根据诊断出的障碍因子，筛选技术库中适用的修复技术" },
      { label: "条件适配过滤", desc: "按土壤类型、用地类型、修复阶段等条件进一步过滤" },
      { label: "多维度评分", desc: "从有效性、成本、工期、二次风险、成熟度五个维度对候选技术打分" },
      { label: "禁用条件检查", desc: "排除存在禁用条件冲突的技术（如不适用特定污染物组合）" },
      { label: "组合方案生成", desc: "对复合污染场地，生成多技术联用的组合方案" },
    ],
    outputs: [
      { label: "推荐方案列表", desc: "按综合匹配分排序的推荐技术/组合方案" },
      { label: "评分分解", desc: "每个方案的五维度评分雷达图" },
      { label: "障碍因子覆盖", desc: "方案覆盖的障碍因子比例及未覆盖因子列表" },
      { label: "推荐报告 (PDF)", desc: "可导出的方案推荐报告" },
    ],
    references: [
      { title: "污染场地修复技术目录（第一批）", source: "生态环境部" },
      { title: "HJ 25.5-2018 污染地块风险管控与土壤修复效果评估技术导则", source: "生态环境部" },
      { title: "污染场地修复技术筛选指南", source: "中国环境科学研究院" },
    ],
  },

  trace_workflow: {
    key: "trace_workflow",
    title: "全流程追溯",
    subtitle: "调查→审批→施工→效果→管护 五阶段监管闭环",
    svgPath: svg("trace_workflow"),
    inputs: [
      { label: "场地基础信息", desc: "场地名称、位置、污染类型、用地规划、责任主体" },
      { label: "阶段材料", desc: "各阶段上传的调查方案、审批文件、施工记录、监理报告、管护计划等" },
      { label: "操作人信息", desc: "每个操作的用户身份、角色、时间戳" },
    ],
    processes: [
      { label: "阶段一：调查评估", desc: "场地初步调查 → 详细调查 → 风险评估 → 确定修复目标" },
      { label: "阶段二：方案审批", desc: "修复方案编制 → 专家评审 → 主管部门审批 → 方案备案" },
      { label: "阶段三：施工监理", desc: "修复工程施工 → 过程监测 → 监理记录 → 阶段性验收" },
      { label: "阶段四：效果评估", desc: "修复后检测 → 达标判定 → 效果评估报告 → 竣工验收" },
      { label: "阶段五：后期管护", desc: "长期监测计划 → 制度控制 → 定期巡检 → 管护记录归档" },
    ],
    outputs: [
      { label: "五阶段状态轴", desc: "可视化展示每个阶段的完成/进行中/退回/未开始状态" },
      { label: "材料档案", desc: "每个阶段的附件材料清单，支持预览和下载" },
      { label: "操作审计日志", desc: "全流程所有操作的完整记录，含操作人、时间、结果" },
      { label: "追溯报告 (PDF/DOCX)", desc: "一键生成的完整五阶段追溯报告，含附件清单和操作日志" },
    ],
    references: [
      { title: "HJ 25.5-2018 污染地块风险管控与土壤修复效果评估技术导则", source: "生态环境部" },
      { title: "污染地块土壤环境管理办法（试行）", source: "环境保护部 2016年第42号令" },
      { title: "建设用地土壤污染状况调查、风险评估、风险管控及修复效果评估报告评审指南", source: "生态环境部" },
    ],
  },

  data_import: {
    key: "data_import",
    title: "数据导入",
    subtitle: "多源场地检测数据的标准化录入流程",
    svgPath: svg("data_import"),
    inputs: [
      { label: "原始数据文件", desc: "Excel (.xlsx/.xls) 或 CSV 格式的场地检测数据" },
      { label: "字段映射模板", desc: "预定义或自定义的列名到系统字段的映射配置" },
    ],
    processes: [
      { label: "文件解析", desc: "读取文件列名和前 3 行预览，自动检测编码和表头行" },
      { label: "字段映射", desc: "用户将文件列映射到系统标准字段（场地信息、点位信息、因子检测值）" },
      { label: "数据校验", desc: "单位一致性检查、数值范围校验、必填字段检查、重复记录检测" },
      { label: "去重策略", desc: "支持跳过/覆盖/新建版本三种重复处理策略" },
      { label: "写入数据库", desc: "校验通过的数据写入 sites / sampling_points / measurements 表" },
    ],
    outputs: [
      { label: "导入报告", desc: "成功/失败/跳过条数统计，含逐条校验错误详情" },
      { label: "场地记录", desc: "新创建或更新的场地信息" },
      { label: "检测数据", desc: "标准化后进入 measurements 长表的检测数据" },
    ],
    references: [
      { title: "HJ/T 166-2004 土壤环境监测技术规范", source: "国家环境保护总局" },
      { title: "GB 15618-2018 农用地土壤污染风险管控标准", source: "生态环境部" },
    ],
  },

  report_generation: {
    key: "report_generation",
    title: "报告生成",
    subtitle: "基于 Jinja2 模板的多格式报告自动生成",
    svgPath: svg("report_generation"),
    inputs: [
      { label: "场地全量数据", desc: "基本信息、检测数据、诊断结果、评价结果、推荐方案、追溯记录" },
      { label: "报告模板", desc: "Jinja2 HTML 模板，定义报告的章节结构、样式、排版" },
      { label: "图表快照", desc: "ECharts 图表导出为 SVG/PNG 嵌入报告" },
    ],
    processes: [
      { label: "数据聚合", desc: "收集场地关联的所有诊断/评价/推荐/追溯数据" },
      { label: "模板渲染", desc: "Jinja2 引擎将数据填充到 HTML 模板，生成完整报告" },
      { label: "PDF 转换", desc: "WeasyPrint 将 HTML 渲染为 PDF，保持排版和图表质量" },
      { label: "DOCX 生成", desc: "python-docx 并行生成 Word 格式报告（含嵌入图表）" },
      { label: "版本管理", desc: "每次生成的报告记录版本号、生成时间、数据版本、操作人" },
    ],
    outputs: [
      { label: "PDF 报告", desc: "适合打印和归档的 PDF 格式追溯报告" },
      { label: "DOCX 报告", desc: "适合编辑和协作的 Word 格式报告" },
      { label: "HTML 预览", desc: "浏览器内的报告预览（生成 PDF 前确认）" },
    ],
    references: [
      { title: "HJ 25.5-2018 附录 — 修复效果评估报告编制要求", source: "生态环境部" },
      { title: "污染地块土壤环境管理办法 第24条 — 信息公开与报告", source: "环境保护部" },
    ],
  },
};

/** 所有已配置模块的 key 列表 */
export const FLOW_KEYS = Object.keys(METHOD_FLOWS);

/** 按 key 获取配置，不存在返回 undefined */
export function getFlowConfig(key: string): FlowConfig | undefined {
  return METHOD_FLOWS[key];
}
