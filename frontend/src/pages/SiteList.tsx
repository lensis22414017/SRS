import { useEffect, useState } from "react";
import { Card, Table, Tag, Input, Button, Space, App } from "antd";
import { ImportOutlined, ReloadOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";
import { POLLUTION_TYPE, POLLUTION_LABEL } from "../theme/palette";

export default function SiteList() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  const load = () => { setLoading(true); api.sites({ q, size: 100 }).then(setData).catch((err) => { message.error(err?.response?.data?.detail || "加载失败"); setData({ items: [], total: 0 }); }).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  return (
    <Card title="场地数据管理"
      extra={<Space>
        <Input.Search placeholder="按名称/编号搜索" allowClear onChange={(e) => setQ(e.target.value)} onSearch={load} style={{ width: 240 }} />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        <Button type="primary" icon={<ImportOutlined />} onClick={() => nav("/sites/import")}>批量导入</Button>
      </Space>}>
      <Table rowKey="id" loading={loading} dataSource={data.items} pagination={{ pageSize: 10 }}
        columns={[
          seqCol(64),
          textCol("场地编号", "site_code"),
          { title: "场地名称", dataIndex: "name", render: (v: string, r: any) => {
            // 优化展示: site_北京_OP_200点 → 北京 · 有机污染 · 200点
            if (!v) return "—";
            const parts = v.replace(/^site_/, "").split("_");
            if (parts.length >= 2) {
              const prov = parts[0];
              const typeCode = parts.slice(1, -1).join("_");
              const count = parts[parts.length - 1];
              const typeLabel = POLLUTION_LABEL[typeCode === "OP" ? "organic" : typeCode === "HM" ? "heavy_metal" : typeCode === "HM+OP" ? "composite" : ""] || typeCode;
              return <span>{prov} · <Tag color={POLLUTION_TYPE[typeCode === "OP" ? "organic" : typeCode === "HM" ? "heavy_metal" : "composite"] || "#888"}>{typeLabel}</Tag> · {count}</span>;
            }
            return v;
          }},
          { title: "污染类型", dataIndex: "pollution_type", align: "center",
            render: (v: string) => v ? <Tag color={POLLUTION_TYPE[v] || "#888"}>{POLLUTION_LABEL[v] || v}</Tag> : "—" },
          textCol("用地类型", "land_use_type"),
          textCol("区域", "city", { render: (_: any, r: any) => `${r.province || ""}${r.city || ""}` || "—" }),
          numCol("采样点", "n_points"),
          numCol("因子数", "n_factors"),
          { title: "超标", dataIndex: "n_exceed", align: "center", width: 80,
            render: (v: number) => v ? <Tag color="red">{v}</Tag> : <Tag color="green">无</Tag> },
          { title: "数据质量", dataIndex: "data_quality", align: "center", width: 100,
            render: (v: string) => <Tag color={v === "良好" ? "green" : v === "部分超标" ? "orange" : "red"}>{v || "—"}</Tag> },
          { title: "操作", align: "center", render: (_, r) => <a onClick={() => nav(`/sites/${r.id}`)}>查看详情</a> },
        ]} />
    </Card>
  );
}
