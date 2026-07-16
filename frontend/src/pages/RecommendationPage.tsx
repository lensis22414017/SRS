import { useEffect, useState } from "react";
import {
  Card, Button, Empty, message, Space, Tag, Row, Col,
  Statistic, Spin, Progress, Divider, Descriptions, Typography, Badge,
} from "antd";
import {
  ApartmentOutlined, CheckCircleOutlined, WarningOutlined, BookOutlined,
  DollarOutlined, ClockCircleOutlined, ExperimentOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import { getFlowConfig } from "../config/methodFlows";
import ReactECharts from "echarts-for-react";
import { SVG_OPTS } from "../theme/echarts";

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
  const [emptyReason, setEmptyReason] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [flowOpen, setFlowOpen] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid;
    if (!s) return;
    setLoading(true);
    api.recommendation(s)
      .then((d) => { setItems(d.items || []); setEmptyReason(d.empty_reason); })
      .catch(() => { setItems([]); setEmptyReason(undefined); })
      .finally(() => { setLoading(false); setLoaded(true); });
  };
  useEffect(() => { if (sid) load(sid); }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try {
      const r = await api.runRecommendation(sid);
      const n = r.recommendations?.length ?? 0;
      message.success(r.organic_fallback
        ? `已生成 ${n} 条 OP 技术候选(基于有机因子, 未跑 SHAP 诊断)`
        : `已生成 ${n} 条推荐方案`);
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
          <Space>
            <Button icon={<ApartmentOutlined />} onClick={() => setFlowOpen(true)}>方法说明</Button>
            <Button type="primary" loading={busy} onClick={run} disabled={!sid}>
              运行方案推荐
            </Button>
          </Space>
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
        <>
        {/* Round7 追加: 匹配分横向条形对比卡(保留下方 RecommendCard 文本卡) */}
        <Card size="small" title="方案综合评分对比（横向条形图）" style={{ marginBottom: 16 }}>
          <ReactECharts option={{
            tooltip: { trigger: "axis", formatter: (p: any) => {
              const it = items[p[0].dataIndex];
              return "<b>" + (it.technology || it.tech_name) + "</b><br/>匹配分: " + p[0].value + "<br/>覆盖率: " + ((it.reason_struct?.score_breakdown?.coverage) ?? 0).toFixed(2);
            } },
            grid: { left: 180, right: 60, top: 16, bottom: 24 },
            xAxis: { type: "value", name: "综合匹配分", max: 1 },
            yAxis: { type: "category", inverse: true, data: items.map((it) => it.technology || it.tech_name),
              axisLabel: { fontSize: 11, width: 170, overflow: "truncate", interval: 0 } },
            series: [{ type: "bar", barMaxWidth: 22,
              data: items.map((it, i) => ({ value: it.match_score ?? 0,
                itemStyle: { color: i === 0 ? "#E64B35" : "#4DBBD5", borderRadius: [0, 4, 4, 0] } })),
              label: { show: true, position: "right", fontSize: 10, formatter: (p: any) => p.value?.toFixed(3) } }],
          }} theme="srs-light" opts={SVG_OPTS} style={{ height: Math.max(160, items.length * 50) }} />
        </Card>

        {/* Round7 追加: 障碍因子→修复技术桑基图 */}
        {(() => {
          const sankeyNodes: any[] = []; const sankeyLinks: any[] = [];
          const nodeSet = new Set<string>();
          const addNode = (n: string, cat: string) => { if (!nodeSet.has(n)) { nodeSet.add(n); sankeyNodes.push({ name: n, category: cat }); } };
          items.forEach((it) => {
            const tech = it.technology || it.tech_name;
            addNode(tech, "tech");
            const facts = (it.reason_struct?.obstacle_binding || []).map((f: any) => f.factor)
              .concat(it.matched_factors || []);
            facts.forEach((f: string) => { addNode(f, "factor"); sankeyLinks.push({ source: f, target: tech, value: (it.match_score ?? 0.1) }); });
          });
          if (sankeyLinks.length === 0) return null;
          return (
            <Card size="small" title="障碍因子 → 修复技术 桑基图（因子流向技术匹配关系）" style={{ marginBottom: 16 }}>
              <ReactECharts option={{
                tooltip: { trigger: "item", formatter: (p: any) => p.dataType === "edge" ? p.data.source + " → " + p.data.target + "<br/>匹配: " + p.data.value.toFixed(3) : p.data.name },
                series: [{ type: "sankey", layout: "none", emphasis: { focus: "adjacency" },
                  nodeAlign: "left", nodeWidth: 16, nodeGap: 6,
                  data: sankeyNodes, links: sankeyLinks,
                  lineStyle: { color: "gradient", opacity: 0.4 },
                  label: { fontSize: 10 },
                  itemStyle: { borderWidth: 0 } }],
              }} theme="srs-light" opts={SVG_OPTS} style={{ height: 320 }} />
            </Card>
          );
        })()}

        {/* Round7 追加: 技术优缺点矩阵(汇总对比) */}
        <Card size="small" title="技术优缺点对比矩阵" style={{ marginBottom: 16 }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#f5f5f5" }}>
                  <th style={{ padding: "6px 8px", textAlign: "left", borderBottom: "2px solid #e8e8e8" }}>技术</th>
                  <th style={{ padding: "6px 8px", textAlign: "left", borderBottom: "2px solid #e8e8e8" }}>✅ 优点</th>
                  <th style={{ padding: "6px 8px", textAlign: "left", borderBottom: "2px solid #e8e8e8" }}>⚠ 局限</th>
                  <th style={{ padding: "6px 8px", textAlign: "left", borderBottom: "2px solid #e8e8e8" }}>成本/工期</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const rs = it.reason_struct || {}; const cd = rs.cost_duration || {};
                  return (
                    <tr key={it.rank}>
                      <td style={{ padding: "6px 8px", borderBottom: "1px solid #f0f0f0", fontWeight: 600 }}>{it.technology || it.tech_name}</td>
                      <td style={{ padding: "6px 8px", borderBottom: "1px solid #f0f0f0", color: "#15803d" }}>{rs.advantages || "—"}</td>
                      <td style={{ padding: "6px 8px", borderBottom: "1px solid #f0f0f0", color: "#92400e" }}>{rs.limitations || "—"}</td>
                      <td style={{ padding: "6px 8px", borderBottom: "1px solid #f0f0f0" }}>{cd.cost_level || "—"}/{cd.duration_level || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Row gutter={[16, 16]}>
          {items.map((r) => (
            <Col span={24} key={r.rank || r.tech_name}>
              <RecommendCard r={r} />
            </Col>
          ))}
        </Row>
        </>
      ) : (
        <Empty
          description={
            emptyReason
              || (loaded
                ? "暂无推荐方案：请先完成障碍因子诊断后运行推荐"
                : "请选择场地并点击「运行方案推荐」")
          }
        />
      )}
      <MethodFlowDrawer open={flowOpen} onClose={() => setFlowOpen(false)} config={getFlowConfig("recommendation")!} />
    </Space>
  );
}
