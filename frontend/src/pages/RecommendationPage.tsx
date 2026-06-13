import { useEffect, useState } from "react";
import { Card, Button, Empty, message, Space, Tag, Row, Col, Statistic, Spin } from "antd";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";

/** 方案推荐独立页: 选择场地 → 运行推荐 → 卡片列表展示(绑定障碍因子/理由/匹配度)。 */
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
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行方案推荐</Button>
        </Space>
        <p style={{ color: "#888", marginTop: 8, marginBottom: 0, fontSize: 12 }}>
          推荐依据：障碍因子识别结果 + 技术库匹配（适用污染物/用地、禁用条件过滤），每条绑定对应障碍因子，含结构化推荐理由。
        </p>
      </Card>

      {loading ? <Spin style={{ marginTop: 40 }} /> : items.length ? (
        <Row gutter={[16, 16]}>
          {items.map((r) => (
            <Col span={24} key={r.rank}>
              <Card size="small" title={<Space><Tag color="blue">#{r.rank}</Tag>{r.technology}</Space>}
                extra={<Statistic value={r.match_score} title="匹配度" valueStyle={{ fontSize: 16 }} />}>
                <p style={{ margin: 0, color: "#444", fontSize: 13, whiteSpace: "pre-wrap" }}>{r.reason}</p>
                {r.rule_version && <Tag style={{ marginTop: 8 }}>规则版本 {r.rule_version}</Tag>}
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <Empty description={loaded ? "暂无推荐方案：请先运行障碍因子诊断后再生成推荐" : "请选择场地并运行方案推荐"} />
      )}
    </Space>
  );
}
