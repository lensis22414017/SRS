import { useEffect, useMemo, useState } from "react";
import { Card, Table, Select, Spin, Empty, Row, Col, Tag, Space, Tabs, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";

const { Text } = Typography;

const PALETTE = ["#0f3d6e", "#1d6fb8", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

/** 进入模型前的 EDA 数据体检: 统计表 + 科研级图件(箱线/小提琴/散点/热力/QQ/柱状)。 */
export default function EdaPanel({ siteId }: { siteId: number }) {
  const [data, setData] = useState<any>(null);
  const [sel, setSel] = useState<string>();
  const [groupBy, setGroupBy] = useState<string>("region");
  const [loading, setLoading] = useState(true);
  const [scatterX, setScatterX] = useState<string>();
  const [scatterY, setScatterY] = useState<string>();

  useEffect(() => {
    setLoading(true);
    // 一次性拉全量(include 默认全返回), 前端各 Tab 复用, 避免多次请求
    api.eda(siteId, { group_by: groupBy, max_points: 2000 }).then((d) => {
      setData(d);
      if (d.factors?.length) {
        setSel(d.factors[0].factor);
        setScatterX(d.factors[0].factor);
        setScatterY(d.factors[Math.min(1, d.factors.length - 1)].factor);
      }
    }).catch(() => setData(null)).finally(() => setLoading(false));
  }, [siteId, groupBy]);

  if (loading) return <Spin style={{ marginTop: 40 }} />;
  if (!data?.factors?.length) return <Empty description="暂无可分析数据" />;

  const factors = data.factors as any[];
  const cur = factors.find((f) => f.factor === sel) || factors[0];
  const factorOptions = factors.map((f) => ({ value: f.factor, label: `${f.factor}${f.category ? `(${f.category})` : ""}` }));
  const rows = factors.map((f) => ({ factor: f.factor, ...f.stats }));

  const histOption = useMemo(() => buildHistogram(cur), [cur]);
  const boxOption = useMemo(() => buildBoxViolin(factors), [factors]);
  const scatterOption = useMemo(() => buildScatter(factors, scatterX, scatterY), [factors, scatterX, scatterY]);
  const heatOption = useMemo(() => buildHeatmap(data.correlation), [data]);
  const qqOption = useMemo(() => buildQQ(cur), [cur]);
  const compareOption = useMemo(() => buildCompare(factors), [factors]);
  const groupedOption = useMemo(() => buildGrouped(data.grouped, sel), [data, sel]);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Tabs defaultActiveKey="overview" items={[
        {
          key: "overview", label: "统计体检",
          children: (
            <Card title="各因子统计体检（真实数据，未插补）" size="small">
              <Text type="secondary">各因子基于真实检测值的描述统计：N=有效样本数，CV=变异系数（标准差/均值），偏度反映分布对称性，IQR 法判定异常点。形态标签「近似对称」=|偏度|≤0.5。数据来源：场地导入的原始检测长表 measurements。</Text>
              <div style={{ marginTop: 8 }}>
              <Table rowKey="factor" size="small" dataSource={rows} pagination={{ pageSize: 8 }} scroll={{ x: "max-content" }}
                columns={[
                  seqCol(56), textCol("因子", "factor"),
                  numCol("有效数", "count"), numCol("缺失%", "missing_pct"),
                  numCol("均值", "mean"), numCol("中位数", "median"),
                  numCol("标准差", "std"), numCol("CV", "cv"), numCol("偏度", "skew"),
                  { title: "形态", dataIndex: "skew_flag", align: "center",
                    render: (v: string) => <Tag color={v === "近似对称" ? "green" : "orange"}>{v || "—"}</Tag> },
                  numCol("异常点", "outliers"), numCol("最小", "min"), numCol("最大", "max"),
                ]} />
              </div>
            </Card>
          ),
        },
        {
          key: "hist", label: "直方图",
          children: (
            <Card title="分布直方图" size="small"
              extra={<Select style={{ width: 220 }} value={sel} onChange={setSel} options={factorOptions} />}>
              <Text type="secondary">选定因子的浓度分布频数直方图（15 等宽分箱）。横轴=浓度区间，纵轴=样本频数。用于判断因子分布形态（正态/偏态/多峰）。单位见因子字典。</Text>
              <Row gutter={16} style={{ marginTop: 8 }}>
                <Col span={16}>{histOption ? <ReactECharts option={histOption} style={{ height: 340 }} /> : <Empty />}</Col>
                <Col span={8}>
                  {cur && (
                    <Table size="small" pagination={false} showHeader={false} rowKey="k" dataSource={[
                      { k: "均值/中位数", v: `${cur.stats.mean} / ${cur.stats.median}` },
                      { k: "标准差 / CV", v: `${cur.stats.std} / ${cur.stats.cv ?? "—"}` },
                      { k: "偏度 / 形态", v: `${cur.stats.skew ?? "—"} ${cur.stats.skew_flag ?? ""}` },
                      { k: "异常点(IQR)", v: `${cur.stats.outliers}（${cur.stats.outlier_pct}%）` },
                      { k: "P5 / P95", v: `${cur.stats.p05} / ${cur.stats.p95}` },
                      { k: "缺失率", v: `${cur.stats.missing_pct}%` },
                    ]} columns={[textCol("指标", "k"), { title: "值", dataIndex: "v", align: "right" }]} />
                  )}
                </Col>
              </Row>
            </Card>
          ),
        },
        {
          key: "box", label: "箱线/小提琴",
          children: (
            <Card title="箱线图 + 小提琴图（多因子分布对比）" size="small">
              <Text type="secondary">箱体=IQR(Q1~Q3)，中线=中位数，须线=1.5×IQR 边界；外层多边形=核密度估计(KDE)轮廓，红点=离群点。</Text>
              <div style={{ marginTop: 8 }}>{boxOption ? <ReactECharts option={boxOption} style={{ height: 440 }} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "scatter", label: "散点图",
          children: (
            <Card title="因子散点图（双因子分位点对照 + 线性拟合）" size="small"
              extra={<Space>
                <Select style={{ width: 170 }} value={scatterX} onChange={setScatterX} options={factorOptions} />
                <Text>vs</Text>
                <Select style={{ width: 170 }} value={scatterY} onChange={setScatterY} options={factorOptions} />
              </Space>}>
              <Text type="secondary">双因子分位点散点对照（两因子各自排序后按等分位点配对）+ 最小二乘线性拟合，r 为皮尔逊相关系数。|r|→1 表示两因子强线性相关，可用于识别污染同源性（如重金属伴生）。</Text>
              <div style={{ marginTop: 8 }}>{scatterOption ? <ReactECharts option={scatterOption} style={{ height: 400 }} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "heatmap", label: "相关热力图",
          children: (
            <Card title="跨因子相关系数矩阵（Pearson）" size="small">
              <Text type="secondary">基于采样点宽表 pivot 计算皮尔逊相关。常数/低方差列已自动剔除。蓝=正相关，红=负相关。</Text>
              <div style={{ marginTop: 8 }}>{heatOption ? <ReactECharts option={heatOption} style={{ height: 480 }} /> : <Empty description="因子数 < 2，无法计算相关矩阵" />}</div>
            </Card>
          ),
        },
        {
          key: "qq", label: "Q-Q 图",
          children: (
            <Card title="正态 Q-Q 图（检验正态性）" size="small"
              extra={<Select style={{ width: 220 }} value={sel} onChange={setSel} options={factorOptions} />}>
              <Text type="secondary">点越贴近红色 y=x 参考线，分布越接近正态。偏态因子点会呈 S 形弯曲。</Text>
              <div style={{ marginTop: 8 }}>{qqOption ? <ReactECharts option={qqOption} style={{ height: 400 }} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "compare", label: "因子对比",
          children: (
            <Card title="因子对比柱状图（均值 / 变异系数 CV）" size="small">
              <Text type="secondary">左 Y 轴=各因子浓度均值（深蓝），右 Y 轴=变异系数 CV%（橙）。CV 越大表示该因子在场内空间变异越剧烈，CV&gt;50% 通常提示存在局部污染热点。用于横向比较各因子的平均水平与空间稳定性。</Text>
              <div style={{ marginTop: 8 }}>{compareOption ? <ReactECharts option={compareOption} style={{ height: 420 }} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "grouped", label: "分组对比",
          children: (
            <Card title={`按${groupByLabel(groupBy)}分组对比（选定因子）`} size="small"
              extra={<Space>
                <Select style={{ width: 150 }} value={groupBy} onChange={setGroupBy}
                  options={[{ value: "region", label: "按区域" }, { value: "depth", label: "按深度" }, { value: "factor", label: "按因子" }]} />
                {groupBy !== "factor" && <Select style={{ width: 170 }} value={sel} onChange={setSel} options={factorOptions} />}
              </Space>}>
              <Text type="secondary">选定因子按区域/深度/因子维度的均值（深蓝）与中位数（绿）对比。用于识别污染的空间分异（不同区域/深度层的浓度差异），辅助定位重点修复区段。</Text>
              <div style={{ marginTop: 8 }}>{groupedOption ? <ReactECharts option={groupedOption} style={{ height: 420 }} /> : <Empty />}</div>
            </Card>
          ),
        },
      ]} />
    </Space>
  );
}

// ========== 图件构造 ==========
function buildHistogram(cur: any) {
  const hist = cur?.histogram;
  if (!hist?.counts?.length) return null;
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 20, top: 20, bottom: 50 },
    xAxis: { type: "category",
      data: hist.edges.slice(0, -1).map((e: number, i: number) => `${e}~${hist.edges[i + 1]}`),
      axisLabel: { rotate: 45, fontSize: 9 }, name: cur.factor },
    yAxis: { type: "value", name: "频数" },
    series: [{ type: "bar", data: hist.counts, itemStyle: { color: "#0f3d6e" } }],
  };
}

/** 箱线图 + 小提琴(KDE 多边形) + 离群点。 */
function buildBoxViolin(factors: any[]) {
  const valid = factors.filter((f) => f.boxplot?.q1 != null && f.distribution?.values?.length >= 5);
  if (!valid.length) return null;
  const cats = valid.map((f) => f.factor);
  const boxData = valid.map((f) => {
    const b = f.boxplot;
    return [b.lower, b.q1, b.median, b.q3, b.upper];
  });
  const outlierData: any[] = [];
  valid.forEach((f, fi) => (f.boxplot.outliers || []).forEach((v: number) => outlierData.push([fi, v])));
  const series: any[] = [
    { name: "箱线", type: "boxplot", data: boxData, itemStyle: { color: "#dbeafe", borderColor: "#0f3d6e" } },
    { name: "离群点", type: "scatter", data: outlierData, symbolSize: 5, itemStyle: { color: "#ef4444", opacity: 0.6 } },
  ];
  // 小提琴: 每因子 KDE 直方图 → 对称多边形闭合 line+area(平移到 fi 位置)
  valid.forEach((f, fi) => {
    const { right, left } = kdeOutline(f.distribution.values, 24, 0.38);
    const polygon = [...right, ...left].map(([x, y]) => [fi + x, y]);
    series.push({
      name: `小提琴-${f.factor}`, type: "line", z: 0,
      data: polygon, showSymbol: false, smooth: true,
      lineStyle: { color: PALETTE[fi % PALETTE.length], width: 1.2, opacity: 0.6 },
      areaStyle: { color: PALETTE[fi % PALETTE.length], opacity: 0.15 },
    });
  });
  return {
    tooltip: { trigger: "item" },
    grid: { left: 60, right: 30, top: 30, bottom: 70 },
    xAxis: { type: "category", data: cats, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: "value", name: "浓度" },
    series,
  };
}

/** 由排序后的样本值生成 KDE 等宽直方图的左右轮廓(x 偏移 fi)。 */
function kdeOutline(vals: number[], bins: number, halfW: number) {
  const min = Math.min(...vals), max = Math.max(...vals);
  const width = max - min || 1;
  const counts = new Array(bins).fill(0);
  vals.forEach((v) => {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / width * bins)));
    counts[idx] += 1;
  });
  const maxC = Math.max(...counts) || 1;
  const right: [number, number][] = [], left: [number, number][] = [];
  for (let i = 0; i < bins; i++) {
    const y = min + (i + 0.5) / bins * width;
    const w = counts[i] / maxC * halfW;
    right.push([0 + w, y]);   // x 偏移由调用层用 fi 平移; 此处返回相对坐标
  }
  for (let i = bins - 1; i >= 0; i--) {
    const y = min + (i + 0.5) / bins * width;
    const w = counts[i] / maxC * halfW;
    left.push([0 - w, y]);
  }
  return { right, left };
}

/** 散点图: 双因子分位点对照(用各自排序分布的等分位点配对)+ 线性拟合 + 皮尔逊 r。 */
function buildScatter(factors: any[], xFactor?: string, yFactor?: string) {
  const xf = factors.find((f) => f.factor === xFactor);
  const yf = factors.find((f) => f.factor === yFactor);
  const xv = xf?.distribution?.values, yv = yf?.distribution?.values;
  if (!xv?.length || !yv?.length || xFactor === yFactor) return null;
  const n = Math.min(xv.length, yv.length);
  const data: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    const xi = Math.floor(i / n * xv.length);
    const yi = Math.floor(i / n * yv.length);
    data.push([xv[Math.min(xi, xv.length - 1)], yv[Math.min(yi, yv.length - 1)]]);
  }
  const xs = data.map((d) => d[0]), ys = data.map((d) => d[1]);
  const mx = mean(xs), my = mean(ys);
  let num = 0, den = 0;
  for (let i = 0; i < xs.length; i++) { num += (xs[i] - mx) * (ys[i] - my); den += (xs[i] - mx) ** 2; }
  const slope = den ? num / den : 0;
  const intercept = my - slope * mx;
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const r = corr(xs, ys);
  return {
    tooltip: { trigger: "item", formatter: (p: any) => `${xFactor}=${p.data[0]?.toFixed?.(3)}<br/>${yFactor}=${p.data[1]?.toFixed?.(3)}` },
    grid: { left: 70, right: 30, top: 30, bottom: 50 },
    legend: { data: ["分位点对照", `线性拟合 (r=${r.toFixed(3)})`] },
    xAxis: { type: "value", name: xFactor, nameLocation: "middle", nameGap: 30 },
    yAxis: { type: "value", name: yFactor, nameLocation: "middle", nameGap: 50 },
    series: [
      { name: "分位点对照", type: "scatter", data, symbolSize: 6, itemStyle: { color: "#1d6fb8", opacity: 0.6 } },
      { name: `线性拟合 (r=${r.toFixed(3)})`, type: "line",
        data: [[xMin, slope * xMin + intercept], [xMax, slope * xMax + intercept]] as any,
        showSymbol: false, lineStyle: { color: "#ef4444", width: 2 } },
    ],
  };
}

/** 相关系数热力图。 */
function buildHeatmap(corr: any) {
  if (!corr?.labels?.length) return null;
  const labels = corr.labels;
  const data: any[] = [];
  for (let i = 0; i < labels.length; i++)
    for (let j = 0; j < labels.length; j++)
      data.push([j, i, corr.matrix[i][j]]);
  return {
    tooltip: { position: "top", formatter: (p: any) => `${labels[p.data[1]]} × ${labels[p.data[0]]}<br/>r = ${p.data[2]}` },
    grid: { left: 90, right: 30, top: 20, bottom: 90 },
    xAxis: { type: "category", data: labels, axisLabel: { rotate: 50, fontSize: 9 }, splitArea: { show: true } },
    yAxis: { type: "category", data: labels, axisLabel: { fontSize: 9 }, splitArea: { show: true } },
    visualMap: { min: -1, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 0,
      inRange: { color: ["#b91c1c", "#fee2e2", "#f8fafc", "#dbeafe", "#0f3d6e"] } },
    series: [{ name: "相关系数", type: "heatmap", data, label: { show: labels.length <= 12, fontSize: 8,
      formatter: (p: any) => p.data[2].toFixed(2) }, emphasis: { itemStyle: { shadowBlur: 10 } } }],
  };
}

/** Q-Q 图: 样本分位 vs 理论正态分位 + y=x 参考线。 */
function buildQQ(cur: any) {
  const qq = cur?.qq;
  if (!qq?.sample?.length) return null;
  const data = qq.sample.map((s: number, i: number) => [qq.theoretical[i], s]);
  const ys = qq.sample;
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  return {
    tooltip: { trigger: "item", formatter: (p: any) => `理论=${p.data[0].toFixed(3)}<br/>样本=${p.data[1].toFixed(3)}` },
    grid: { left: 70, right: 30, top: 30, bottom: 50 },
    xAxis: { type: "value", name: "理论正态分位", nameLocation: "middle", nameGap: 30 },
    yAxis: { type: "value", name: `样本(${cur.factor})`, nameLocation: "middle", nameGap: 50 },
    series: [
      { name: "Q-Q 点", type: "scatter", data, symbolSize: 6, itemStyle: { color: "#1d6fb8", opacity: 0.6 } },
      { name: "y=x 参考", type: "line", data: [[-3, yMin], [3, yMax]] as any,
        showSymbol: false, lineStyle: { color: "#ef4444", type: "dashed", width: 2 } },
    ],
  };
}

/** 因子对比柱状图: 均值 + 变异系数 CV(双 Y 轴)。 */
function buildCompare(factors: any[]) {
  const cats = factors.map((f) => f.factor);
  const means = factors.map((f) => f.stats.mean ?? 0);
  const cvs = factors.map((f) => (f.stats.cv != null ? f.stats.cv * 100 : 0));
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["均值", "变异系数 CV (%)"] },
    grid: { left: 60, right: 60, top: 40, bottom: 70 },
    xAxis: { type: "category", data: cats, axisLabel: { rotate: 45, fontSize: 9 } },
    yAxis: [{ type: "value", name: "均值", position: "left" }, { type: "value", name: "CV(%)", position: "right" }],
    series: [
      { name: "均值", type: "bar", data: means, itemStyle: { color: "#0f3d6e" } },
      { name: "变异系数 CV (%)", type: "bar", yAxisIndex: 1, data: cvs, itemStyle: { color: "#f59e0b" } },
    ],
  };
}

/** 分组对比柱状图: 按 region/depth/factor。 */
function buildGrouped(grouped: any, factor?: string) {
  if (!grouped) return null;
  const groups = grouped.group_by === "factor"
    ? grouped.overall.groups
    : ((factor && grouped.per_factor?.[factor]?.groups) || grouped.overall.groups);
  if (!groups?.length) return null;
  const cats = groups.map((g: any) => g.group);
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["均值", "中位数"] },
    grid: { left: 60, right: 30, top: 40, bottom: 70 },
    xAxis: { type: "category", data: cats, axisLabel: { rotate: 30, fontSize: 10 }, name: groupByLabel(grouped.group_by) },
    yAxis: { type: "value", name: "浓度" },
    series: [
      { name: "均值", type: "bar", data: groups.map((g: any) => g.mean), itemStyle: { color: "#0f3d6e" } },
      { name: "中位数", type: "bar", data: groups.map((g: any) => g.median), itemStyle: { color: "#10b981" } },
    ],
  };
}

function groupByLabel(g: string) {
  return g === "region" ? "区域" : g === "depth" ? "深度" : "因子";
}
function mean(a: number[]) { return a.reduce((s, x) => s + x, 0) / (a.length || 1); }
function corr(x: number[], y: number[]) {
  const mx = mean(x), my = mean(y);
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < x.length; i++) { num += (x[i] - mx) * (y[i] - my); dx += (x[i] - mx) ** 2; dy += (y[i] - my) ** 2; }
  return dx && dy ? num / Math.sqrt(dx * dy) : 0;
}
