/**
 * SiteConclusion — 场地综合结论(核心问题闭环)
 *
 * 面向甲方回答四个问题:
 *  1. 修复后是否适合生产用途?
 *  2. 修复后是否适合生态用途?
 *  3. 各自关键障碍因子是什么?
 *  4. 功能重构可行性/经济性/安全性如何?
 *
 * 数据聚合自: kosDiagnosis(prod/eco) + evaluation(reconstruction/ssui) + recommendation。
 * 所有结论标注来源, 不伪造。
 */
import { useEffect, useState } from "react";
import { Card, Spin, Empty, Tag, Descriptions, Statistic, Row, Col, Alert, Button, Space, Table, Typography, Divider } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, FilePdfOutlined, FileWordOutlined } from "@ant-design/icons";
import { api } from "../api/client";

const { Text, Paragraph, Title } = Typography;

export default function SiteConclusion({ siteId }: { siteId: number }) {
  const [loading, setLoading] = useState(true);
  const [site, setSite] = useState<any>(null);
  const [kosProd, setKosProd] = useState<any>(null);
  const [kosEco, setKosEco] = useState<any>(null);
  const [evalData, setEvalData] = useState<any>(null);
  const [rec, setRec] = useState<any>(null);

  useEffect(() => {
    if (!siteId) return;
    setLoading(true);
    Promise.all([
      api.site(siteId).catch(() => null),
      api.kosDiagnosis(siteId, "prod").catch(() => null),
      api.kosDiagnosis(siteId, "eco").catch(() => null),
      api.evaluation(siteId).catch(() => null),
      api.recommendation(siteId).catch(() => null),
    ]).then(([s, kp, ke, ev, r]) => {
      setSite(s);
      setKosProd(kp);
      setKosEco(ke);
      setEvalData(ev);
      setRec(r);
    }).finally(() => setLoading(false));
  }, [siteId]);

  if (loading) return <Spin style={{ marginTop: 40 }} />;
  if (!site) return <Empty description="场地数据加载失败" />;

  const prod = evalData?.results?.reconstruction_prod;
  const eco = evalData?.results?.reconstruction_eco;
  const ssui = evalData?.results?.ssui;
  const prodKey = kosProd?.key_obstacles?.slice(0, 5) || [];
  const ecoKey = kosEco?.key_obstacles?.slice(0, 5) || [];
  const recs = rec?.recommendations?.slice(0, 3) || [];
  const reviewRequired = kosProd?.review_required || kosEco?.review_required;
  const recTests = [...(kosProd?.recommended_tests || []), ...(kosEco?.recommended_tests || [])]
    .filter((t, i, arr) => arr.findIndex(x => x.factor === t.factor) === i).slice(0, 6);

  // 一句话结论判定
  const prodFit = prod?.grade === "可行";
  const ecoFit = eco?.grade === "可行";
  const verdict = (fit: boolean | undefined, label: string) => {
    if (fit === undefined) return <Tag color="default">数据不足</Tag>;
    return fit
      ? <Tag icon={<CheckCircleOutlined />} color="success">适合{label}</Tag>
      : <Tag icon={<CloseCircleOutlined />} color="error">不适合{label}</Tag>;
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16} data-testid="site-conclusion">
      {/* 一句话结论 */}
      <Card data-testid="conclusion-verdict">
        <Title level={4} style={{ marginTop: 0 }}>场地综合结论</Title>
        <Paragraph style={{ fontSize: 15 }}>
          {site.name}（{site.province || "—"}）修复后
          {verdict(prodFit, "生产用途")}
          {verdict(ecoFit, "生态用途")}。
          生产轨关键障碍: <b>{prodKey.map((k: any) => k.factor).join("、") || "无"}</b>;
          生态轨关键障碍: <b>{ecoKey.map((k: any) => k.factor).join("、") || "无"}</b>。
          {reviewRequired && <Text type="warning">部分结果需人工复核。</Text>}
        </Paragraph>
        {reviewRequired && (
          <Alert type="warning" showIcon icon={<WarningOutlined />}
            message="本场地诊断触发人工复核标记"
            description="KOS 引擎检测到数据质量提示或探索性模型结果, 正式结论需专家结合现场情况复核。" />
        )}
      </Card>

      {/* 四问 + 双轨障碍 */}
      <Row gutter={16}>
        <Col span={12}>
          <Card title={<Space><Tag color="purple">生产用途</Tag>功能重构可行性</Space>} data-testid="conclusion-prod">
            {prod ? (
              <>
                <Row gutter={8}>
                  <Col span={8}><Statistic title="综合得分" value={prod.score} suffix="分"
                    valueStyle={{ color: prodFit ? "#15803d" : "#b91c1c" }} /></Col>
                  <Col span={8}><div style={{ fontSize: 12, color: "#888" }}>评价等级</div>
                    <Tag color={prodFit ? "green" : "red"} style={{ fontSize: 14, marginTop: 8 }}>{prod.grade}</Tag></Col>
                  <Col span={8}><div style={{ fontSize: 12, color: "#888" }}>关键限制因子</div>
                    {(prod.limiting_factors || []).map((f: string) => <Tag color="orange" key={f}>{f}</Tag>)}</Col>
                </Row>
                <Divider style={{ margin: "12px 0" }} />
                <Text strong>关键障碍 Top-5:</Text>
                <Table rowKey="rank" size="small" pagination={false} style={{ marginTop: 8 }}
                  dataSource={prodKey}
                  columns={[
                    { title: "#", dataIndex: "rank", width: 40, align: "center" },
                    { title: "因子", dataIndex: "factor", width: 100 },
                    { title: "实测值", dataIndex: "value", width: 80, render: (v: number) => v?.toFixed?.(3) ?? "—" },
                  ]} />
              </>
            ) : <Empty description="未运行生产轨功能重构评价" />}
          </Card>
        </Col>
        <Col span={12}>
          <Card title={<Space><Tag color="green">生态用途</Tag>功能重构可行性</Space>} data-testid="conclusion-eco">
            {eco ? (
              <>
                <Row gutter={8}>
                  <Col span={8}><Statistic title="综合得分" value={eco.score} suffix="分"
                    valueStyle={{ color: ecoFit ? "#15803d" : "#b91c1c" }} /></Col>
                  <Col span={8}><div style={{ fontSize: 12, color: "#888" }}>评价等级</div>
                    <Tag color={ecoFit ? "green" : "red"} style={{ fontSize: 14, marginTop: 8 }}>{eco.grade}</Tag></Col>
                  <Col span={8}><div style={{ fontSize: 12, color: "#888" }}>关键限制因子</div>
                    {(eco.limiting_factors || []).map((f: string) => <Tag color="orange" key={f}>{f}</Tag>)}</Col>
                </Row>
                <Divider style={{ margin: "12px 0" }} />
                <Text strong>关键障碍 Top-5:</Text>
                <Table rowKey="rank" size="small" pagination={false} style={{ marginTop: 8 }}
                  dataSource={ecoKey}
                  columns={[
                    { title: "#", dataIndex: "rank", width: 40, align: "center" },
                    { title: "因子", dataIndex: "factor", width: 100 },
                    { title: "实测值", dataIndex: "value", width: 80, render: (v: number) => v?.toFixed?.(3) ?? "—" },
                  ]} />
              </>
            ) : <Empty description="未运行生态轨功能重构评价" />}
          </Card>
        </Col>
      </Row>

      {/* SSUI + 推荐方案 */}
      <Row gutter={16}>
        <Col span={8}>
          <Card title="可持续利用评价 SSUI" data-testid="conclusion-ssui">
            {ssui ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="SSUI 指数">{ssui.score}</Descriptions.Item>
                <Descriptions.Item label="可持续等级"><Tag color="blue">{ssui.grade}</Tag></Descriptions.Item>
              </Descriptions>
            ) : <Empty description="未运行 SSUI 评价" />}
          </Card>
        </Col>
        <Col span={16}>
          <Card title="推荐修复方案 Top 3" data-testid="conclusion-recommend">
            {recs.length ? (
              <Table rowKey="rank" size="small" pagination={false} dataSource={recs}
                columns={[
                  { title: "#", dataIndex: "rank", width: 40 },
                  { title: "技术", dataIndex: "technology" },
                  { title: "匹配度", dataIndex: "match_score", width: 80 },
                  { title: "成本", dataIndex: "cost_level", width: 70 },
                ]} />
            ) : <Empty description="未生成方案推荐" />}
          </Card>
        </Col>
      </Row>

      {/* 需补测/复核 + 下载 */}
      <Card title="需补测与人工复核项" data-testid="conclusion-review">
        {recTests.length ? (
          <Table rowKey="factor" size="small" pagination={false} dataSource={recTests}
            columns={[
              { title: "建议补测因子", dataIndex: "factor", width: 120 },
              { title: "原因", dataIndex: "reason" },
              { title: "证据等级", dataIndex: "evidence", width: 80, align: "center",
                render: (v: string) => <Tag color={v === "C" ? "orange" : "red"}>{v}</Tag> },
            ]} />
        ) : <Text type="secondary">无补测建议(所有关键因子均已实测)。</Text>}
        <Divider style={{ margin: "12px 0" }} />
        <Space>
          <Button type="primary" icon={<FilePdfOutlined />} onClick={() => {
            api.generateReport(siteId, "pdf").then(() => alert("PDF 报告生成中, 请到'追溯报告'Tab 下载"));
          }}>下载 PDF 全流程报告</Button>
          <Button icon={<FileWordOutlined />} onClick={() => {
            api.generateReport(siteId, "docx").then(() => alert("DOCX 报告生成中, 请到'追溯报告'Tab 下载"));
          }}>下载 DOCX 报告</Button>
        </Space>
      </Card>
    </Space>
  );
}
