import { useEffect, useState } from "react";
import { Card, Table, Tag, Input, Button, Space, App, Popconfirm } from "antd";
import { ImportOutlined, ReloadOutlined, DeleteOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";
import { POLLUTION_TYPE, POLLUTION_LABEL } from "../theme/palette";

const PAGE_SIZE = 10;

export default function SiteList() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);

  const load = () => {
    setLoading(true);
    api.sites({ q, size: 100 }).then(setData).catch((err) => {
      message.error(err?.response?.data?.detail || "加载失败");
      setData({ items: [], total: 0 });
    }).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  // v1.0.2: 场地删除(GPT 第三节), Popconfirm + 级联清理在后端
  const handleDelete = async (id: number, name: string) => {
    try {
      await api.deleteSite(id);
      message.success(`场地「${name}」已删除(含所有关联数据)`);
      load();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "删除失败");
    }
  };

  // v1.0.1: 批量删除(裴总任务2)
  const handleBatchDelete = async () => {
    setBatchDeleting(true);
    try {
      const ids = selectedRowKeys.map(k => Number(k));
      const res = await api.batchDeleteSites(ids);
      message.success(`批量删除完成: ${res.succeeded}/${res.total} 个场地已清除`);
      setSelectedRowKeys([]);
      load();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "批量删除失败");
    } finally {
      setBatchDeleting(false);
    }
  };

  return (
    <Card title="场地数据管理"
      extra={<Space>
        <Input.Search placeholder="按名称/编号搜索" allowClear onChange={(e) => setQ(e.target.value)} onSearch={load} style={{ width: 240 }} />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        {selectedRowKeys.length > 0 && (
          <Popconfirm
            title={`确认批量删除选中的 ${selectedRowKeys.length} 个场地？`}
            description="将级联清除所有点位、测量、诊断、评价、推荐、报告记录，不可恢复。"
            onConfirm={handleBatchDelete}
            okText="确认批量删除"
            cancelText="取消"
            okButtonProps={{ danger: true, loading: batchDeleting }}>
            <Button danger icon={<DeleteOutlined />}>批量删除({selectedRowKeys.length})</Button>
          </Popconfirm>
        )}
        <Button type="primary" icon={<ImportOutlined />} onClick={() => nav("/sites/import")}>批量导入</Button>
      </Space>}>
      <Table rowKey="id" loading={loading} dataSource={data.items}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        pagination={{
          pageSize: PAGE_SIZE,
          current: page,
          onChange: (p) => setPage(p),
          showSizeChanger: false,
          showTotal: (t) => `共 ${t} 个场地`,
        }}
        columns={[
          // v1.0.2: 序号支持分页偏移(GPT 3.5), 第 2 页第 1 条显示 11
          seqCol(64, page, PAGE_SIZE),
          textCol("场地编号", "site_code"),
          { title: "场地名称", dataIndex: "name", render: (v: string, r: any) => {
            if (!v) return "—";
            // v1.0.1: 场地名称直接显示源文件名(不再做特殊装饰渲染)
            return <span>{v}</span>;
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
          { title: "操作", align: "center", width: 160,
            render: (_, r) => (
              <Space size="small">
                <a onClick={() => nav(`/sites/${r.id}`)}>查看详情</a>
                <Popconfirm
                  title="确认删除该场地？"
                  description="将级联清除所有点位、测量、诊断、评价、推荐、报告记录，不可恢复。"
                  onConfirm={() => handleDelete(r.id, r.name)}
                  okText="确认删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}>
                  <a style={{ color: "#ff4d4f" }}><DeleteOutlined /> 删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]} />
    </Card>
  );
}
