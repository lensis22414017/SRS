import { useEffect, useMemo, useState } from "react";
import { Card, Table, Select, Spin, Empty, Row, Col, Tag, Space, Tabs, Typography, Alert } from "antd";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";
import { CATEGORICAL, PRIMARY, NEUTRAL_TEXT } from "../theme/palette";
import { SVG_OPTS } from "../theme/echarts";

const { Text } = Typography;

const PALETTE = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F",
                 "#8491B4", "#B09C85", "#91D1C2"];  // NPG Nature/Science 顶刊配色( SHAP 图同源, 问题6 EDA 美化)

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

  // 所有 hooks 必须在任何 conditional return 之前(React hooks 规则, brief 4.4)
  // 用可选链兜底 data 为 null(loading/empty 态), build* 函数对 null 入参返回 null。
  const factors = (data?.factors || []) as any[];
  const cur = factors.find((f) => f.factor === sel) || factors[0];
  const factorOptions = factors.map((f) => ({ value: f.factor, label: `${f.factor}${f.category ? `(${f.category})` : ""}` }));
  const rows = factors.map((f) => ({ factor: f.factor, ...f.stats }));
  const histOption = useMemo(() => buildHistogram(cur), [cur]);
  const boxOption = useMemo(() => buildBoxViolin(factors), [factors]);
  const scatterOption = useMemo(() => buildScatter(factors, scatterX, scatterY), [factors, scatterX, scatterY]);
  const heatOption = useMemo(() => buildHeatmap(data?.correlation), [data]);
  const qqOption = useMemo(() => buildQQ(cur), [cur]);
  const compareOption = useMemo(() => buildCompare(factors), [factors]);
  const groupedOption = useMemo(() => buildGrouped(data?.grouped, sel), [data, sel]);
  const pieOption = useMemo(() => buildPie(factors), [factors]);
  const htOption = useMemo(() => buildHypothesisTest(data?.hypothesis_test), [data]);
  const kwHeatOption = useMemo(() => buildKwHeatmap(data?.hypothesis_test), [data]);
  const esOption = useMemo(() => buildEffectSize(data?.effect_size), [data]);
  const pcaOption = useMemo(() => buildPCA(data?.pca), [data]);

  if (loading) return <Spin style={{ marginTop: 40 }} />;
  if (!data?.factors?.length) return <Empty description="暂无可分析数据" />;

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
              <Text type="secondary">选定因子的浓度分布频数直方图（15 等宽分箱）。横轴=浓度区间，纵轴=样本频次。用于判断因子分布形态（正态/偏态/多峰）。单位见因子字典。</Text>
              <Row gutter={16} style={{ marginTop: 8 }}>
                <Col span={16}>{histOption ? <ReactECharts option={histOption} style={{ height: 340 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</Col>
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
          key: "box", label: "云雨图",
          children: (
            <Card title="云雨图 Raincloud（半小提琴密度 + 样本散点 + 箱线，多因子分布对比）" size="small">
              <Text type="secondary">箱体=IQR(Q1~Q3)，中线=中位数，须线=1.5×IQR 边界；外层多边形=核密度估计(KDE)轮廓，红点=离群点。</Text>
              <div style={{ marginTop: 8 }}>{boxOption ? <ReactECharts option={boxOption} style={{ height: 440 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</div>
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
              <div style={{ marginTop: 8 }}>{scatterOption ? <ReactECharts option={scatterOption} style={{ height: 400 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "heatmap", label: "相关热力图",
          children: (
            <Card title="跨因子相关系数矩阵（Pearson）" size="small">
              <Text type="secondary">基于采样点宽表 pivot 计算皮尔逊相关。常数/低方差列已自动剔除。蓝=正相关，红=负相关。</Text>
              <div style={{ marginTop: 8 }}>{heatOption ? <ReactECharts option={heatOption} style={{ height: 480 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty description="因子数 < 2，无法计算相关矩阵" />}</div>
            </Card>
          ),
        },
        {
          key: "qq", label: "Q-Q 图",
          children: (
            <Card title="正态 Q-Q 图（检验正态性）" size="small"
              extra={<Select style={{ width: 220 }} value={sel} onChange={setSel} options={factorOptions} />}>
              <Text type="secondary">点越贴近红色 y=x 参考线，分布越接近正态。偏态因子点会呈 S 形弯曲。</Text>
              <div style={{ marginTop: 8 }}>{qqOption ? <ReactECharts option={qqOption} style={{ height: 400 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "compare", label: "因子对比",
          children: (
            <Card title="因子对比柱状图（均值 / 变异系数 CV）" size="small">
              <Text type="secondary">左 Y 轴=各因子浓度均值（深蓝），右 Y 轴=变异系数 CV%（橙）。CV 越大表示该因子在场内空间变异越剧烈，CV&gt;50% 通常提示存在局部污染热点。用于横向比较各因子的平均水平与空间稳定性。</Text>
              <div style={{ marginTop: 8 }}>{compareOption ? <ReactECharts option={compareOption} style={{ height: 420 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</div>
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
              {data?.grouped?.degraded_reason && (
                <Alert type="info" showIcon style={{ marginTop: 8 }}
                  message={`已自动降级：${data.grouped.degraded_reason}`}
                  description={`当前实际按「${groupByLabel(data.grouped.group_by)}」分组展示`} />
              )}
              <div style={{ marginTop: 8 }}>{groupedOption ? <ReactECharts option={groupedOption} style={{ height: 420 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "pie", label: "类别分布",
          children: (
            <Card title="因子类别分布（环形图）" size="small">
              <Text type="secondary">各因子类别（环境指标/化学性质/肥力指标等）数量占比环形图，快速识别场地主导污染物类型。</Text>
              <div style={{ marginTop: 8 }}>{pieOption ? <ReactECharts option={pieOption} style={{ height: 380 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty />}</div>
            </Card>
          ),
        },
        {
          key: "htest", label: "假设检验",
          children: (
            <Card title="Mann-Whitney U / Kruskal-Wallis 检验（不同区位因子浓度差异）" size="small">
              <Text type="secondary">{data?.hypothesis_test?.note || "按采样区位分组，检验同一因子在两组/多组间的浓度分布是否有显著差异。p&lt;0.05 表示差异显著。"}<br/>
              <b>看什么</b>：p 值是否小于 0.05。<b>发现了什么</b>：显著差异提示污染存在空间分异（局部热点）。<b>对诊断的影响</b>：需分区治理而非全场统一。<b>下一步</b>：对显著因子做分区精查。</Text>
              <Alert type="info" showIcon style={{ marginTop: 8 }} message="统计检验说明（重要）" description={
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
                  <li><b>p 值含义</b>：表示组间浓度差异的证据强弱，p 越小证据越强，但 <b>不代表污染成因</b>。</li>
                  <li><b>多重比较</b>：同时对多个因子做检验会增加假阳性风险，严格场景需做 Bonferroni 等校正（本图未校正，按原始 p 值展示）。</li>
                  <li><b>小样本</b>：每组样本 &lt; 5 时结果仅供探索性参考，不作为正式判定。</li>
                  <li><b>非因果</b>：显著性只说明"有差异"，不证明"该因子导致障碍"——障碍判定以规则阈值为准。</li>
                </ul>
              } />
              <div style={{ marginTop: 8 }}>
                {htOption ? (
                  <>
                    <ReactECharts option={htOption} style={{ height: 380 }} theme="srs-light" opts={SVG_OPTS} />
                    {data?.hypothesis_test?.kruskal_wallis?.length > 0 && (
                      <Table rowKey="factor" size="small" pagination={{ pageSize: 6 }} style={{ marginTop: 12 }}
                        dataSource={data.hypothesis_test.kruskal_wallis}
                        columns={[
                          textCol("因子", "factor"), numCol("组数", "n_groups"),
                          numCol("Kruskal H", "kruskal_h"), numCol("p 值", "kruskal_p"),
                          { title: "显著", dataIndex: "kruskal_p", align: "center", width: 70,
                            render: (v: number) => <Tag color={v < 0.05 ? "red" : "default"}>{v < 0.05 ? "是" : "否"}</Tag> },
                        ]} />
                    )}
                    {/* Round7 追加: Kruskal-Wallis p 值显著性热图(因子×检验统计量) */}
                    {kwHeatOption && (
                      <div style={{ marginTop: 12 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>Kruskal-Wallis 检验显著性矩阵热图（颜色越红 p 值越小=越显著）：</Text>
                        <ReactECharts option={kwHeatOption} style={{ height: 300 }} theme="srs-light" opts={SVG_OPTS} />
                      </div>
                    )}
                  </>
                ) : <Empty description="区位分组不足（需至少 2 个区位且每组≥3 样本）" />}
              </div>
            </Card>
          ),
        },
        {
          key: "effect", label: "效应量",
          children: (
            <Card title="效应量 Cohen's d / Cliff's delta（区位间差异程度）" size="small">
              <Text type="secondary">{data?.effect_size?.note || "p 值只说'有没有差异'，效应量说'差异有多大'。"}<br/>
              <b>看什么</b>：Cohen's d 绝对值。<b>发现了什么</b>：大效应(|d|&gt;0.8)表示区位间浓度差异巨大。<b>对诊断的影响</b>：大效应因子是分区治理的重点。<b>下一步</b>：优先处理大效应+高浓度的因子。</Text>
              <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 6 }}>
                ⓘ 效应量衡量差异大小，与 p 值互补。但效应量同样<b>不代表因果</b>——它只描述统计差异程度，污染成因仍需结合超标阈值与专业判断。
              </Text>
              <div style={{ marginTop: 8 }}>
                {esOption ? <ReactECharts option={esOption} style={{ height: 400 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty description="区位分组不足" />}
              </div>
            </Card>
          ),
        },
        {
          key: "pca", label: "PCA降维",
          children: (
            <Card title="主成分分析 PCA（因子共变关系与污染源识别）" size="small">
              <Text type="secondary">{data?.pca ? `前 ${data.pca.n_components} 主成分累计解释方差: ${(data.pca.cumulative_variance * 100).toFixed(1)}%` : ""}<br/>
              <b>看什么</b>：PC1/PC2 载荷散点（右上=因子聚集=同源污染）。<b>发现了什么</b>：聚集的因子(如 Cd/Pb/As 同向)提示同一污染源。<b>对诊断的影响</b>：同源因子可合并治理。<b>下一步</b>：对聚集因子组溯源。</Text>
              <div style={{ marginTop: 8 }}>
                {pcaOption ? <ReactECharts option={pcaOption} style={{ height: 450 }} theme="srs-light" opts={SVG_OPTS} /> : <Empty description="样本/因子数不足（需≥3 采样点且≥2 因子）" />}
              </div>
            </Card>
          ),
        },
        {
          key: "outlier", label: "异常值明细",
          children: (
            <Card title="异常值检测明细（IQR + Z-score 双法）" size="small">
              <Text type="secondary">{data?.outlier_detail?.note || "IQR 法 + Z-score 双法命中更可信。"}<br/>
              <b>看什么</b>：哪些采样点×因子被标记为异常。<b>发现了什么</b>：单点极高值可能是局部污染热点或检测异常。<b>对诊断的影响</b>：异常点需现场复核，区分真污染与检测误差。<b>下一步</b>：对异常点位复测。</Text>
              <div style={{ marginTop: 8 }}>
                {data?.outlier_detail?.items?.length ? (
                  <Table rowKey={(r: any) => `${r.factor}-${r.point_id}-${r.value}`} size="small"
                    pagination={{ pageSize: 10 }}
                    dataSource={data.outlier_detail.items}
                    columns={[
                      seqCol(50), textCol("因子", "factor"), numCol("采样点", "point_id"),
                      numCol("实测值", "value"), numCol("Z分", "z_score"),
                      textCol("检测法", "method"), textCol("阈值", "threshold"),
                    ]} />
                ) : <Empty description="未检测到异常值（IQR 与 Z>3 均未命中）" />}
              </div>
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
    legend: { data: ["频次", "密度趋势"], top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 50, right: 20, top: 30, bottom: 50 },
    xAxis: { type: "category",
      data: hist.edges.slice(0, -1).map((e: number, i: number) => `${e}~${hist.edges[i + 1]}`),
      axisLabel: { rotate: 45, fontSize: 9 }, name: cur.factor },
    yAxis: { type: "value", name: "频次", nameLocation: "end", nameGap: 10,
             nameTextStyle: { fontSize: 12, color: NEUTRAL_TEXT, padding: [0, 0, 4, 0] },
             axisLabel: { fontSize: 10, color: NEUTRAL_TEXT } },
    series: [
      { name: "频次", type: "bar", data: hist.counts, barMaxWidth: 28,
        itemStyle: { color: "#4DBBD5", borderRadius: [3, 3, 0, 0] },
        label: { show: true, position: "top", fontSize: 9, color: NEUTRAL_TEXT,
                 formatter: (p: any) => (p.value ? String(p.value) : "") } },
      // 密度趋势线(项目组要参考 ipynb 的直方图+KDE, 叠加 NPG 红平滑曲线)
      { name: "密度趋势", type: "line", data: hist.counts, smooth: true,
        showSymbol: false, lineStyle: { color: "#E64B35", width: 2.5 },
        areaStyle: { color: "#E64B35", opacity: 0.08 } },
    ],
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
  // 云雨图 raincloud(明确要"云雨图最好看"): 半小提琴(KDE右半"云") + jitter散点(原始值"雨") + 箱线
  valid.forEach((f, fi) => {
    const { right } = kdeOutline(f.distribution.values, 24, 0.38);
    const half = right.map(([x, y]) => [fi + x, y]);
    const polygon = [[fi, half[0][1]], ...half, [fi, half[half.length - 1][1]]];
    series.push({
      name: `密度-${f.factor}`, type: "line", z: 0,
      data: polygon, showSymbol: false, smooth: true,
      lineStyle: { color: PALETTE[fi % PALETTE.length], width: 1.2, opacity: 0.7 },
      areaStyle: { color: PALETTE[fi % PALETTE.length], opacity: 0.22 },
    });
    const rain = f.distribution.values.map((v: number) => [fi - 0.1 - Math.random() * 0.2, v]);
    series.push({
      name: `样本-${f.factor}`, type: "scatter", z: 1, data: rain, symbolSize: 3.5,
      itemStyle: { color: PALETTE[fi % PALETTE.length], opacity: 0.5 },
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
      { name: "分位点对照", type: "scatter", data, symbolSize: 6, itemStyle: { color: PALETTE[3], opacity: 0.65 } },
      { name: `线性拟合 (r=${r.toFixed(3)})`, type: "line",
        data: [[xMin, slope * xMin + intercept], [xMax, slope * xMax + intercept]] as any,
        showSymbol: false, lineStyle: { color: PALETTE[0], width: 2 } },
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
      { name: "Q-Q 点", type: "scatter", data, symbolSize: 6, itemStyle: { color: PALETTE[3], opacity: 0.65 } },
      { name: "y=x 参考", type: "line", data: [[-3, yMin], [3, yMax]] as any,
        showSymbol: false, lineStyle: { color: PALETTE[0], type: "dashed", width: 2 } },
    ],
  };
}

/** 因子对比柱状图: 均值 + 变异系数 CV(双 Y 轴, NPG 顶刊色)。 */
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
      { name: "均值", type: "bar", data: means, itemStyle: { color: "#4DBBD5", borderRadius: [3,3,0,0] }, barMaxWidth: 32 },
      { name: "变异系数 CV (%)", type: "bar", yAxisIndex: 1, data: cvs, itemStyle: { color: "#E64B35", borderRadius: [3,3,0,0] }, barMaxWidth: 32 },
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
      { name: "均值", type: "bar", data: groups.map((g: any) => g.mean), itemStyle: { color: PALETTE[3], borderRadius: [3,3,0,0] }, barMaxWidth: 32 },
      { name: "中位数", type: "bar", data: groups.map((g: any) => g.median), itemStyle: { color: PALETTE[2], borderRadius: [3,3,0,0] }, barMaxWidth: 32 },
    ],
  };
}

/** 因子类别分布环形图(pie/doughnut)。项目组要求: 柱状/环形/小提琴/热图齐全。 */
function buildPie(factors: any[]) {
  const cnt: Record<string, number> = {};
  factors.forEach((f) => { const c = f.category || "未分类"; cnt[c] = (cnt[c] || 0) + 1; });
  const data = Object.entries(cnt).map(([name, value]) => ({ name, value }));
  if (!data.length) return null;
  const PALETTE_PIE = CATEGORICAL;  // 饼图色板对齐全局莫兰迪
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, type: "scroll", textStyle: { fontSize: 11 } },
    color: PALETTE_PIE,
    series: [{ type: "pie", radius: ["38%", "68%"], center: ["50%", "45%"],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: "#fff", borderWidth: 2 },
      label: { show: true, formatter: "{b}\n{d}%", fontSize: 11 },
      data }],
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

/** 节五: Mann-Whitney U 检验结果可视化(p 值条形图, 红线=0.05 显著阈值)。 */
function buildHypothesisTest(ht: any) {
  const items = ht?.mann_whitney;
  if (!items?.length) return null;
  const sorted = [...items].sort((a: any, b: any) => (a.mann_whitney_p ?? 1) - (b.mann_whitney_p ?? 1));
  return {
    tooltip: { trigger: "axis", formatter: (p: any) => `<b>${p[0].name}</b><br/>p = ${p[0].value?.toFixed(5)}<br/>${p[0].value < 0.05 ? "🔴 显著差异" : "⚪ 无显著差异"}` },
    grid: { left: 100, right: 40, top: 30, bottom: 30 },
    xAxis: { type: "value", name: "p 值", max: 1 },
    yAxis: { type: "category", inverse: true, data: sorted.map((i: any) => i.factor) },
    series: [{
      type: "bar",
      data: sorted.map((i: any) => ({
        value: i.mann_whitney_p,
        itemStyle: { color: i.mann_whitney_p < 0.05 ? "#E64B35" : "#91D1C2", borderRadius: [0, 3, 3, 0] },
      })),
      markLine: { silent: true, symbol: "none", lineStyle: { color: "#fa541c", type: "dashed", width: 2 },
        data: [{ xAxis: 0.05, label: { formatter: "p=0.05", color: "#fa541c", fontSize: 10 } }] },
      label: { show: true, position: "right", fontSize: 9, formatter: (p: any) => p.value?.toFixed(4) },
    }],
  };
}

/** 节五: Cohen's d 效应量条形图(正向/负向 + 量级色阶)。 */
/** Round7: Kruskal-Wallis p 值显著性热图(因子行 × [H统计量/p值] 列, 越红越显著)。 */
function buildKwHeatmap(ht: any) {
  const items = ht?.kruskal_wallis;
  if (!items?.length) return null;
  const factors = items.map((i: any) => i.factor);
  // p 值取负对数 -log10(p) 放大显著性差异(越大越显著); H 统计量归一化
  const pHm = items.map((i: any, idx: number) => [0, idx, i.kruskal_p]);
  const hHm = items.map((i: any, idx: number) => [1, idx, i.kruskal_h]);
  return {
    tooltip: { position: "top", formatter: (p: any) => {
      const it = items[p.data[1]];
      const label = p.data[0] === 0 ? "p 值" : "H 统计量";
      return "<b>" + it.factor + "</b><br/>" + label + ": " + (p.data[0] === 0 ? it.kruskal_p : it.kruskal_h);
    } },
    grid: { left: 100, right: 30, top: 30, bottom: 60 },
    xAxis: { type: "category", data: ["p 值", "H 统计量"], splitArea: { show: true } },
    yAxis: { type: "category", data: factors, axisLabel: { fontSize: 10 }, splitArea: { show: true } },
    visualMap: { min: 0, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 0,
      inRange: { color: ["#dc2626", "#f59e0b", "#facc15", "#91d1c2"] } },
    series: [{ name: "KW 检验", type: "heatmap", data: pHm,
      label: { show: factors.length <= 12, fontSize: 8, formatter: (p: any) => p.data[2].toFixed(3) } }],
  };
}

function buildEffectSize(es: any) {
  const items = es?.items;
  if (!items?.length) return null;
  const sorted = [...items].sort((a: any, b: any) => Math.abs(b.cohens_d) - Math.abs(a.cohens_d));
  return {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const it = sorted[p[0].dataIndex];
      return `<b>${it.factor}</b><br/>Cohen's d = ${it.cohens_d} (${it.magnitude}效应)<br/>Cliff's δ = ${it.cliffs_delta}`;
    } },
    grid: { left: 100, right: 50, top: 30, bottom: 30 },
    legend: { data: ["Cohen's d", "Cliff's delta"], top: 0 },
    xAxis: { type: "value", name: "效应量" },
    yAxis: { type: "category", inverse: true, data: sorted.map((i: any) => i.factor) },
    series: [
      { name: "Cohen's d", type: "bar",
        data: sorted.map((i: any) => ({
          value: i.cohens_d,
          itemStyle: {
            color: Math.abs(i.cohens_d) >= 0.8 ? "#E64B35" : Math.abs(i.cohens_d) >= 0.5 ? "#F39B7F" : Math.abs(i.cohens_d) >= 0.2 ? "#F0E442" : "#91D1C2",
            borderRadius: i.cohens_d >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3],
          },
        })), barGap: "10%" },
      { name: "Cliff's delta", type: "bar",
        data: sorted.map((i: any) => i.cliffs_delta),
        itemStyle: { color: "#3C5488", opacity: 0.5, borderRadius: [3, 3, 3, 3] } },
    ],
  };
}

/** 节五: PCA 载荷散点图(PC1 vs PC2, 因子点 + 原点参考线)。 */
function buildPCA(pca: any) {
  if (!pca?.loadings?.length) return null;
  const evr = pca.explained_variance_ratio || [];
  const loadings = pca.loadings.filter((l: any) => l.pc1 != null && l.pc2 != null);
  // 合并 scores 采样点(灰点)与 loadings 因子(彩色标签)
  const scoreData = (pca.scores_sample || []).map((s: any) => [s.pc1, s.pc2]);
  return {
    tooltip: { trigger: "item" },
    grid: { left: 60, right: 30, top: 40, bottom: 50 },
    legend: { data: ["采样点", "因子载荷"], top: 0 },
    xAxis: { type: "value", name: `PC1 (${(evr[0] * 100).toFixed(1)}%)`, nameLocation: "middle", nameGap: 28 },
    yAxis: { type: "value", name: `PC2 (${(evr[1] * 100).toFixed(1)}%)`, nameLocation: "middle", nameGap: 40 },
    series: [
      { name: "采样点", type: "scatter", data: scoreData, symbolSize: 5,
        itemStyle: { color: "#94a3b8", opacity: 0.4 } },
      { name: "因子载荷", type: "scatter", data: loadings.map((l: any) => ({
        value: [l.pc1, l.pc2], name: l.factor,
      })), symbolSize: 12,
        itemStyle: { color: "#E64B35" },
        label: { show: true, formatter: (p: any) => p.data.name, fontSize: 10, color: "#0f3d6e", position: "top" } },
    ],
  };
}
