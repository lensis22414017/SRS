import { Card, Alert, Descriptions, Tag, Typography, Empty } from "antd";
import { WarningOutlined } from "@ant-design/icons";

const { Text, Paragraph } = Typography;

interface Props {
  /** organic_risk 诊断结果(GET /evaluation 的 results.organic_risk.dimensions) */
  organicRisk?: any;
  /** 缺失指标清单(补齐后可评分) */
  limitingFactors?: string[];
  /** 为什么不能算的说明 */
  explanation?: string;
  title?: string;
}

/**
 * 裴总 P0-3: OP 有机场地评价降级卡片。
 * 当功能重构/SSUI 评价不适用(有机污染场地)时, 替代仪表盘/分数显示:
 *  (1) 为什么不能算 (2) 缺哪些指标 (3) 有机污染风险诊断(超标因子/倍数)。
 * 禁止显示 NaN/null 分。
 */
export default function OrganicDegradedCard({ organicRisk, limitingFactors, explanation, title }: Props) {
  const exceed: string[] = organicRisk?.exceed_factors || [];
  const ratios: Record<string, number> = organicRisk?.max_ratios || {};
  return (
    <Card type="inner" size="small" style={{ borderColor: "#f59e0b", background: "#fffbeb" }}
      title={<><WarningOutlined style={{ color: "#f59e0b", marginRight: 6 }} />{title || "有机污染场地 — 评价降级说明"}</>}>
      <Alert type="warning" showIcon style={{ marginBottom: 12 }}
        message="本项评价不适用(有机污染场地)"
        description={explanation || "本场地为有机污染, 该评价口径基于重金属 + 农业肥力指标体系, 有机污染物不在评价体系内, 故不生成数值评分。"} />
      {limitingFactors && limitingFactors.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Text strong>缺哪些指标(补齐后可评分)：</Text>
          <div style={{ marginTop: 4 }}>
            {limitingFactors.map((f) => (
              <Tag key={f} color="orange" style={{ margin: 2 }}>{f}</Tag>
            ))}
          </div>
        </div>
      )}
      <Card type="inner" size="small" title="有机污染风险诊断(规则型 · 基于实测浓度与标准筛选值)">
        {organicRisk ? (
          <>
            <Descriptions size="small" column={2} bordered>
              <Descriptions.Item label="诊断结论">
                <Tag color={exceed.length ? "red" : "green"}>{organicRisk.overall || "—"}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="检出有机因子数">{organicRisk.n_organic_factors || 0}</Descriptions.Item>
              <Descriptions.Item label="超标因子(最大倍数)" span={2}>
                {exceed.length ? exceed.map((f) => (
                  <Tag key={f} color="red" style={{ margin: 2 }}>{f} ({ratios[f]} 倍)</Tag>
                )) : <Text type="secondary">无超标或无可比对阈值</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="阈值来源" span={2}>
                <Text type="secondary" style={{ fontSize: 12 }}>{organicRisk.threshold_source || "—"}</Text>
              </Descriptions.Item>
            </Descriptions>
            {organicRisk.note && (
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>{organicRisk.note}</Paragraph>
            )}
          </>
        ) : <Empty description="暂无有机风险诊断(请先运行评价)" />}
      </Card>
    </Card>
  );
}
