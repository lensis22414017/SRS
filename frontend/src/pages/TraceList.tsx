import { useEffect, useState } from "react";
import { Card, Table, Tag, Input, Space, Button, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";

export default function TraceList() {
  const nav = useNavigate();
  const [data, setData] = useState<any>({ items: [] });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const load = () => { setLoading(true); api.sites({ q, size: 100 }).then(setData).catch((err) => { message.error(err?.response?.data?.detail || "加载失败"); setData({ items: [] }); }).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  return (
    <Card title="全流程追溯 — 选择场地"
      extra={<Space>
        <Input.Search placeholder="搜索场地" allowClear onChange={(e) => setQ(e.target.value)} onSearch={load} style={{ width: 240 }} />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </Space>}>
      <Table rowKey="id" loading={loading} dataSource={data.items} pagination={{ pageSize: 10 }}
        columns={[
          seqCol(64),
          textCol("场地编号", "site_code"),
          textCol("名称", "name"),
          { title: "污染类型", dataIndex: "pollution_type", align: "center",
            render: (v: string) => v ? <Tag color="red">{v}</Tag> : "—" },
          numCol("采样点", "n_points"),
          { title: "操作", align: "center", render: (_: any, r: any) => <a onClick={() => nav(`/trace/${r.id}`)}>进入追溯</a> },
        ]} />
    </Card>
  );
}
