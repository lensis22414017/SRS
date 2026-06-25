import { useEffect, useState } from "react";
import {
  Card, Button, Empty, message, Space, Tag, Row, Col,
  Statistic, Spin, Progress, Divider, Descriptions, Typography, Badge,
} from "antd";
import {
  CheckCircleOutlined, WarningOutlined, BookOutlined,
  DollarOutlined, ClockCircleOutlined, ExperimentOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";

const { Text, Paragraph } = Typography;

/** 成本/工期颜色映射 */
const LEVEL_COLOR: Record<string, string> = { 低: "green", 中: "gold", 高: "red", 短: "green", 长: "red" };

/** 推荐方案卡片 — 结构化分区展示 */
function RecommendCard({ r }: { r: any }) {
  const rs = r.reason_struct || {};
  const factors: { factor: string; factor_class: string }[] = rs.obstacle_binding || [];
  const fit = rs.tech_fit || {};
  const sb = rs.score_breakdown || {};
  const cd = rs.cost_duration || {};

  // 覆盖率进度条颜色
  const coverageColor =
    (sb.coverage || 0) >= 0.8 ? "#16a34a"
    : (sb.coverage || 0) >= 0.5 ? "#3b82f6"
    : "#f59e0b";

  return (
    <Card
      size="small"
      style={{ borderRadius: 8, boxShadow: "0 2px 8px rgba(0,0,0,.06)" }}
      title={
        <Space size={8}>
          <Badge
            count={`#${r.rank}`}
            style={{ backgroundColor: r.rank === 1 ? "#0f3d6e" : "#64748b" }}
          />
          <Text strong style={{ fontSize: 15 }}>{r.technology || r.tech_name}</Text>
          {fit.stage && <Tag color="cyan">{fit.stage}</Tag>}
        </Space>
      }
      extra={
        <Space size={4}>
          <DollarOutlined style={{ color: "#64748b" }} />
          <Tag color={LEVEL_COLOR[cd.cost_level] || "default"}>{cd.cost_level || "—"}成本</Tag>
          <ClockCircleOutlined style={{ color: "#64748b" }} />
          <Tag color={LEVEL_COLOR[cd.duration_level] || "default"}>{cd.duration_level || "—"}工期</Tag>
        </Space>
      }
    >
      {/* ── 区块1: 匹配得分 ───────────────────────────────── */}
      <Row gutter={16} align="middle" style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Statistic
            title="综合匹配分"
            value={r.match_score}
            precision={3}
            valueStyle={{ fontSize: 20, color: coverageColor }}
          />
        </Col>
        <Col span={9}>
          <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>障碍因子覆盖率</div>
          <Progress
            percent={Math.round((sb.coverage || 0) * 100)}
            strokeColor={coverageColor}
            size="small"
          />
        </Col>
        <Col span={9}>
          <div style={{ fontSize: 11, color: "#888" }}>
            评分组成：覆盖率×60% + 成本×25% + 工期×15%
          </div>
          <div style={{ fontSize: 11, color: "#999" }}>
            {sb.coverage?.toFixed(2)} × 0.60 + {sb.cost_score?.toFixed(2)} × 0.25
            + {sb.duration_score?.toFixed(2)} × 0.15 = {sb.total?.toFixed(4)}
          </div>
        </Col>
      </Row>

      <Divider style={{ margin: "8px 0" }} />

      {/* ── 区块2: 绑定障碍因子 ──────────────────────────── */}
      <div style={{ marginBottom: 10 }}>
        <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>
          <ExperimentOutlined /> 绑定障碍因子（本推荐针对以下已识别因子）
        </Text>
        <Space wrap size={4}>
          {factors.length > 0
            ? factors.map((f) => (
                <Tag
                  key={f.factor}
                  color={f.factor_class === "heavy_metal" ? "red" : f.factor_class === "organic" ? "purple" : "default"}
                  style={{ fontSize: 12 }}
                >
                  {f.factor}
                  <Text type="secondary" style={{ fontSize: 10, marginLeft: 4 }}>
                    {f.factor_class === "heavy_metal" ? "重金属" : f.factor_class === "organic" ? "有机物" : "其他"}
                  </Text>
                </Tag>
              ))
            : (r.matched_factors || []).map((f: string) => (
                <Tag key={f} color="red" style={{ fontSize: 12 }}>{f}</Tag>
              ))}
        </Space>
      </div>

      {/* ── 区块3: 技术适配 ───────────────────────────────── */}
      <Descriptions size="small" column={2} style={{ marginBottom: 8 }}
        styles={{ label: { color: "#888", fontSize: 11 }, content: { fontSize: 12 } }}
      >
        <Descriptions.Item label="适用污染物">{fit.applicable_pollutants || "—"}</Descriptions.Item>
        <Descriptions.Item label="适用用地">{fit.land_types_full || fit.land_match || "—"}</Descriptions.Item>
      </Descriptions>

      <Divider style={{ margin: "8px 0" }} />

      {/* ── 区块4: 优劣分析 ───────────────────────────────── */}
      <Row gutter={8} style={{ marginBottom: 8 }}>
        <Col span={12}>
          <Card
            size="small" type="inner"
            style={{ background: "#f0fdf4", border: "1px solid #bbf7d0" }}
            styles={{ body: { padding: "6px 10px" } }}
          >
            <div style={{ fontSize: 11, color: "#16a34a", fontWeight: 600, marginBottom: 2 }}>
              <CheckCircleOutlined /> 技术优点
            </div>
            <Paragraph style={{ fontSize: 12, margin: 0, color: "#15803d" }}>
              {rs.advantages || "—"}
            </Paragraph>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            size="small" type="inner"
            style={{ background: "#fffbeb", border: "1px solid #fde68a" }}
            styles={{ body: { padding: "6px 10px" } }}
          >
            <div style={{ fontSize: 11, color: "#b45309", fontWeight: 600, marginBottom: 2 }}>
              <WarningOutlined /> 局限性
            </div>
            <Paragraph style={{ fontSize: 12, margin: 0, color: "#92400e" }}>
              {rs.limitations || "—"}
            </Paragraph>
          </Card>
        </Col>
      </Row>

      {/* 二次风险 + 禁用条件 */}
      <Row gutter={8} style={{ marginBottom: 8 }}>
        <Col span={12}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            <WarningOutlined /> 二次风险：{rs.secondary_risk || "暂无数据"}
          </Text>
        </Col>
        <Col span={12}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            🚫 禁用条件：{rs.forbidden_conditions || "无"}
          </Text>
        </Col>
      </Row>

      <Divider style={{ margin: "8px 0" }} />

      {/* ── 区块5: 法规/标准来源 ──────────────────────────── */}
      <div style={{
        background: "#f8faff", borderRadius: 4, padding: "6px 10px",
        border: "1px solid #dbeafe",
      }}>
        <BookOutlined style={{ color: "#1d6fb8", marginRight: 6 }} />
        <Text style={{ fontSize: 11, color: "#1d6fb8" }}>
          推荐依据：{rs.regulatory_basis || r.source || "GB 36600-2018 / HJ 25.4-2019 / HJ 25.6-2019"}
        </Text>
      </div>

      {/* 兜底: 若 reason_struct 不存在，显示旧版文本 */}
      {!r.reason_struct && r.reason && (
        <>
          <Divider style={{ margin: "8px 0" }} />
          <Paragraph style={{ margin: 0, color: "#444", fontSize: 13, whiteSpace: "pre-wrap" }}>
            {r.reason}
          </Paragraph>
        </>
      )}

      {r.rule_version && (
        <div style={{ marginTop: 6 }}>
          <Tag style={{ fontSize: 10 }}>规则版本 {r.rule_version}</Tag>
        </div>
      )}
    </Card>
  );
}

/** 方案推荐独立页 */
export default function RecommendationPage() {
  const [sid, setSid] = useState<number>();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid;
    if (!s) return;
    setLoading(true);
    api.recommendation(s)
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  };
  useEffect(() => { if (sid) load(sid); }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try {
      const r = await api.runRecommendation(sid);
      message.success(`已生成 ${r.recommendations?.length ?? 0} 条推荐方案`);
      load(sid);
    } catch (e: any) {
      const code = e?.response?.status;
      message.error(code === 404
        ? "无可推荐方案：请先完成障碍因子诊断，或确认技术库已加载"
        : (e?.response?.data?.detail || "推荐失败"));
    } finally { setBusy(false); }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
          <SitePicker value={sid} onChange={setSid} />
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>
            运行方案推荐
          </Button>
        </Space>
        <div style={{ marginTop: 8, fontSize: 12, color: "#888" }}>
          推荐依据：障碍因子识别结果 + 技术库规则匹配（适用污染物/用地类型/禁用条件三重过滤），
          每条方案绑定具体障碍因子，含匹配度分解、法规来源与成本-工期标注。
          匹配分 = 覆盖率×60% + 成本分×25% + 工期分×15%。
        </div>
      </Card>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
      ) : items.length ? (
        <Row gutter={[16, 16]}>
          {items.map((r) => (
            <Col span={24} key={r.rank || r.tech_name}>
              <RecommendCard r={r} />
            </Col>
          ))}
        </Row>
      ) : (
        <Empty
          description={
            loaded
              ? "暂无推荐方案：请先完成障碍因子诊断后运行推荐"
              : "请选择场地并点击「运行方案推荐」"
          }
        />
      )}
    </Space>
  );
}
