/**
 * MethodExplainCard — 污染场地关键障碍因子「诊断方法说明」卡片
 *
 * 位置: 障碍因子分析页, 关键障碍因子结果上方。
 * 目的: 用普通中文向用户解释 KOS 综合评分由哪五要素构成, 并明确
 *       "模型贡献度 ≠ 法规判定 ≠ 因果证明", 防止误解。
 *
 * 公式(与 ml/ranking/kos_engine_v0.8.py 一致):
 *   K_i = B_i × (0.30R_i + 0.25W_i + 0.15M_i + 0.20S_i + 0.10E_i)
 */
import { useState } from "react";
import { Card, Collapse, Table, Alert, Tag, Typography, Space, Modal } from "antd";
import { QuestionCircleOutlined, ZoomInOutlined } from "@ant-design/icons";
import FormulaBlock from "./FormulaBlock";
import { flowAssetUrl } from "../config/methodFlows";

const { Text } = Typography;

const LATEX = "K_i = B_i \\times (0.30\\,R_i + 0.25\\,W_i + 0.15\\,M_i + 0.20\\,S_i + 0.10\\,E_i)";

/** 五要素普通中文解释 + 符号对照。 */
const COMPONENT_ROWS = [
  { sym: "Bᵢ", name: "规则门槛", weight: "—", cn: "该因子是否既有明确国标/文献阈值、又被实测。B=0 则整项归零,不进正式排名。" },
  { sym: "Rᵢ", name: "规则严重度", weight: "0.30", cn: "实测值超过标准阈值的程度(超标倍数归一化),越超标越严重。" },
  { sym: "Wᵢ", name: "用途权重", weight: "0.25", cn: "生产用地 / 生态用地对同一因子的容忍度不同(如镉:生产严、生态宽),体现双轨差异。" },
  { sym: "Mᵢ", name: "模型贡献度", weight: "0.15", cn: "该因子对障碍指数的模型解释贡献(辅助),非因果、非障碍高度,仅作参考。" },
  { sym: "Sᵢ", name: "稳定性", weight: "0.20", cn: "多采样点 / 多模型版本下该因子结论是否一致,防止单点偶然。" },
  { sym: "Eᵢ", name: "证据等级", weight: "0.10", cn: "A=国标实测、B=文献阈值、C=模型推断。证据越弱权重越低。" },
];

export default function MethodExplainCard({ track, flowKey }: { track?: "prod" | "eco"; flowKey?: string }) {
  const [open, setOpen] = useState<string | string[]>(["explain"]); // 默认展开
  // v1.0.2(行内缩略图+点击放大): 流程图 Modal
  const [flowModalOpen, setFlowModalOpen] = useState(false);
  const [flowError, setFlowError] = useState(false);
  const flowSrc = flowKey ? flowAssetUrl(flowKey) : null;

  return (
    <Card
      size="small"
      data-testid="method-explain-card"
      style={{ background: "#fafcff", border: "1px solid #d6e4ff", marginBottom: 0 }}
      title={
        <Space>
          <QuestionCircleOutlined style={{ color: "#1677ff" }} />
          <span>诊断方法说明</span>
          {track && (
            <Tag color={track === "prod" ? "purple" : "green"}>
              {track === "prod" ? "生产用途轨" : "生态用途轨"}
            </Tag>
          )}
        </Space>
      }
    >
      <Collapse
        bordered={false}
        activeKey={open}
        onChange={setOpen}
        items={[{
          key: "explain",
          label: <Text type="secondary" style={{ fontSize: 12 }}>这个 Top-N 是怎么算出来的?点击查看方法(普通中文)</Text>,
          children: (
            <Space direction="vertical" style={{ width: "100%" }} size={12}>
              {/* v1.0.2: 行内流程图缩略图(点击放大) */}
              {flowSrc && !flowError && (
                <div style={{ textAlign: "center", cursor: "pointer", border: "1px solid #e8e8e8", borderRadius: 6, padding: 8, background: "#fff" }}
                  onClick={() => setFlowModalOpen(true)}>
                  <img src={flowSrc} alt="方法流程图" style={{ maxHeight: 120, maxWidth: "100%" }}
                    onError={() => setFlowError(true)} />
                  <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>
                    <ZoomInOutlined /> 点击放大查看流程图
                  </div>
                </div>
              )}
              {flowSrc && flowError && (
                <Alert type="warning" showIcon style={{ fontSize: 12 }}
                  message="流程图加载失败"
                  description={`请检查文件是否存在: ${flowSrc}（public/assets/flows/ 目录下应有对应 SVG 文件）`} />
              )}
              {/* 普通中文五要素解释 */}
              <div style={{ fontSize: 12.5, color: "#333", lineHeight: 1.8 }}>
                系统先把每个检测因子过<b>规则层</b>:只有既<b>有明确阈值</b>(国标/文献)、又被<b>实测</b>的因子,
                才会被判定为"明确障碍"(B=1)。在此基础上按五个维度综合评分:
                <ul style={{ margin: "6px 0 0 18px" }}>
                  <li><b>规则严重度</b>:超标越多分越高(法规底线);</li>
                  <li><b>用途权重</b>:生产/生态用地对同一污染物的容忍度不同,体现双轨差异;</li>
                  <li><b>模型贡献度</b>:该因子对障碍指数的模型解释贡献(仅辅助参考);</li>
                  <li><b>稳定性</b>:多点/多版本是否一致,防偶然;</li>
                  <li><b>证据等级</b>:国标实测 &gt; 文献阈值 &gt; 模型推断,证据越弱权重越低。</li>
                </ul>
                最终输出<b>污染场地关键障碍因子 Top-N</b>。
              </div>

              {/* KaTeX 公式 */}
              <FormulaBlock
                title="综合评分公式"
                latex={LATEX}
                source="ml/ranking/kos_engine_v0.8.py compute_kos()"
                note="Bᵢ=0 时整项归零(规则门槛一票否决); R/W/M/S/E 均归一化到 [0,1]。"
              >
                <Table
                  rowKey="sym"
                  size="small"
                  pagination={false}
                  dataSource={COMPONENT_ROWS}
                  columns={[
                    { title: "符号", dataIndex: "sym", width: 56, align: "center",
                      render: (v: string) => <span style={{ fontWeight: 700, color: "#1677ff" }}>{v}</span> },
                    { title: "维度", dataIndex: "name", width: 96 },
                    { title: "权重", dataIndex: "weight", width: 60, align: "center",
                      render: (v: string) => v === "—" ? <Text type="secondary">门槛</Text> : <Tag color="blue">{v}</Tag> },
                    { title: "含义", dataIndex: "cn" },
                  ]}
                />
              </FormulaBlock>
            </Space>
          ),
        }]}
      />
      {/* v1.0.2: 流程图放大 Modal */}
      <Modal open={flowModalOpen} onCancel={() => setFlowModalOpen(false)} footer={null}
        width={900} title="方法流程图" centered>
        {flowSrc && <img src={flowSrc} alt="方法流程图" style={{ width: "100%" }} />}
      </Modal>
    </Card>
  );
}
