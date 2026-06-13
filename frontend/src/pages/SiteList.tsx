import { useEffect, useState } from "react";
import { Card, Table, Tag, Input, Button, Space, message } from "antd";
import { ImportOutlined, ReloadOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";

const POLLUTION: Record<string, { c: string; t: string }> = {
  heavy_metal: { c: "red", t: "重金属" },
  organic: { c: "orange", t: "有机" },
  composite: { c: "purple", t: "复合" },
};

export default function SiteList() {
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
          textCol("名称", "name"),
          { title: "污染类型", dataIndex: "pollution_type", align: "center",
            render: (v) => v ? <Tag color={POLLUTION[v]?.c}>{POLLUTION[v]?.t || v}</Tag> : "—" },
          textCol("用地类型", "land_use_type"),
          textCol("区域", "city", { render: (_: any, r: any) => `${r.province || ""}${r.city || ""}` || "—" }),
          numCol("采样点", "n_points"),
          { title: "操作", align: "center", render: (_, r) => <a onClick={() => nav(`/sites/${r.id}`)}>查看详情</a> },
        ]} />
    </Card>
  );
}
