import { useEffect, useState, useMemo } from "react";
import { Card, Tabs, Table, Input, Tag, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { api } from "../api/client";

// 5 种分类的颜色映射（与 Obsidian/论文配色一致）
const CATEGORY_COLORS: Record<string, string> = {
  化学性质: "#1890ff", // 蓝色
  物理性质: "#fa8c16", // 橙色
  环境指标: "#f5222d", // 红色
  生物指标: "#52c41a", // 绿色
  肥力指标: "#722ed1", // 紫色
};

interface FactorItem {
  id: number;
  factor_name: string;
  factor_code: string;
  level1_category: string;
  default_unit: string;
  factor_type: string;
  description: string;
}

export default function FactorDictionaryTable() {
  const [data, setData] = useState<{
    total: number;
    categories: { name: string; count: number }[];
    items: FactorItem[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeCat, setActiveCat] = useState<string>("");
  const [searchText, setSearchText] = useState("");

  const load = async (category?: string, search?: string) => {
    setLoading(true);
    try {
      const r = await api.factorDictionary({
        category: category || undefined,
        search: search || undefined,
      });
      setData(r);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filteredItems = useMemo(() => {
    if (!data) return [];
    let items = data.items;
    if (activeCat) {
      items = items.filter((i) => i.level1_category === activeCat);
    }
    if (searchText) {
      const s = searchText.toLowerCase();
      items = items.filter(
        (i) =>
          (i.factor_name || "").toLowerCase().includes(s) ||
          (i.factor_code || "").toLowerCase().includes(s) ||
          (i.level1_category || "").toLowerCase().includes(s) ||
          (i.description || "").toLowerCase().includes(s)
      );
    }
    return items.map((item, idx) => ({ ...item, id: idx + 1 }));
  }, [data, activeCat, searchText]);

  const catTabs = useMemo(() => {
    if (!data) return [];
    return [
      { key: "", label: `全部 (${data.total || 0})` },
      ...data.categories.map((c) => ({
        key: c.name,
        label: `${c.name} (${c.count})`,
      })),
    ];
  }, [data]);

  const columns = [
    {
      title: "序号",
      dataIndex: "id",
      key: "id",
      width: 60,
      align: "center" as const,
    },
    {
      title: "因子名称",
      dataIndex: "factor_name",
      key: "factor_name",
      width: 180,
      ellipsis: true,
      render: (v: string, r: FactorItem) => (
        <span title={r.factor_code ? `代码: ${r.factor_code}` : v}>
          {v}
        </span>
      ),
    },
    {
      title: "指标类型",
      dataIndex: "level1_category",
      key: "level1_category",
      width: 100,
      render: (v: string) => (
        <Tag color={CATEGORY_COLORS[v] || "#999"}>{v || "—"}</Tag>
      ),
    },
    {
      title: "单位",
      dataIndex: "default_unit",
      key: "default_unit",
      width: 100,
      render: (v: string) => v || "—",
    },
    {
      title: "说明",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (v: string) => v || "—",
    },
  ];

  return (
    <Card
      title={
        <span style={{ fontSize: 15, fontWeight: 600 }}>
          📋 障碍因子集速查表
          <span style={{ fontSize: 12, color: "#8c8c8c", fontWeight: 400, marginLeft: 8 }}>
            （共 {data?.total || "—"} 项，5 大类）
          </span>
        </span>
      }
      style={{ marginTop: 16 }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <Tabs
          activeKey={activeCat}
          onChange={(k) => setActiveCat(k)}
          items={catTabs}
          size="small"
          style={{ marginBottom: 0, flex: 1 }}
        />
        <Input
          placeholder="搜索因子名称/代码/分类..."
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 280 }}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      <Spin spinning={loading}>
        <Table
          dataSource={filteredItems}
          columns={columns}
          rowKey="id"
          size="small"
          pagination={{ defaultPageSize: 15, showSizeChanger: true, pageSizeOptions: ["10", "15", "30", "50"], showTotal: (t) => `共 ${t} 项` }}
          scroll={{ x: 700 }}
        />
      </Spin>
    </Card>
  );
}
