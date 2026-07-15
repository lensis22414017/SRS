import { useState } from "react";
import { Drawer, Tabs, Card, Steps, List, Table, Empty, Typography, Collapse } from "antd";
import {
  ApartmentOutlined, ImportOutlined, ExportOutlined, FileTextOutlined,
  PictureOutlined,
} from "@ant-design/icons";
import type { FlowConfig, FlowItem } from "../config/methodFlows";

const { Text, Paragraph } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
  config: FlowConfig;
}

/** IPO 卡片 — 输入/输出通用渲染 */
function ItemList({ items, color }: { items: FlowItem[]; color: string }) {
  return (
    <List
      size="small"
      dataSource={items}
      renderItem={(it) => (
        <List.Item style={{ padding: "6px 0", borderBottom: "1px solid #f0f0f0" }}>
          <List.Item.Meta
            avatar={
              <span style={{
                display: "inline-block", width: 6, height: 6,
                borderRadius: 999, background: color, marginTop: 6,
              }} />
            }
            title={<Text strong style={{ fontSize: 13 }}>{it.label}</Text>}
            description={<Text type="secondary" style={{ fontSize: 12 }}>{it.desc}</Text>}
          />
        </List.Item>
      )}
    />
  );
}

/** SVG 流程图区域 — 文件存在则显示，不存在则显示占位 */
function SvgFlow({ svgPath, title }: { svgPath: string; title: string }) {
  const [imgError, setImgError] = useState(false);

  if (imgError) {
    return (
      <Empty
        image={<PictureOutlined style={{ fontSize: 64, color: "#bfbfbf" }} />}
        description={
          <div>
            <Text type="secondary">流程图尚未生成</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 11 }}>
              请在 Excalidraw 中创建「{title}」流程图，导出 SVG 后放入
            </Text>
            <br />
            <Text code style={{ fontSize: 11 }}>frontend/src/assets/flows/</Text>
          </div>
        }
      />
    );
  }

  return (
    <div style={{ textAlign: "center", background: "#fafbfc", borderRadius: 8, padding: 16 }}>
      <img
        src={svgPath}
        alt={`${title} 流程图`}
        style={{ maxWidth: "100%", maxHeight: 420 }}
        onError={() => setImgError(true)}
      />
    </div>
  );
}

export default function MethodFlowDrawer({ open, onClose, config }: Props) {
  const tabItems = [
    {
      key: "flow",
      label: "流程图",
      children: <SvgFlow svgPath={config.svgPath} title={config.title} />,
    },
    {
      key: "ipo",
      label: "输入 / 处理 / 输出",
      children: (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* 输入 */}
          <Card
            size="small"
            title={<span style={{ color: "#0052D9" }}><ImportOutlined /> 输入</span>}
            style={{ borderLeft: "3px solid #0052D9" }}
          >
            <ItemList items={config.inputs} color="#0052D9" />
          </Card>

          {/* 处理 */}
          <Card
            size="small"
            title={<span style={{ color: "#ED7B2F" }}><ApartmentOutlined /> 处理步骤</span>}
            style={{ borderLeft: "3px solid #ED7B2F" }}
          >
            <Steps
              direction="vertical"
              size="small"
              current={-1}
              items={config.processes.map((p) => ({
                title: p.label,
                description: <Text type="secondary" style={{ fontSize: 12 }}>{p.desc}</Text>,
              }))}
            />
          </Card>

          {/* 输出 */}
          <Card
            size="small"
            title={<span style={{ color: "#00A870" }}><ExportOutlined /> 输出</span>}
            style={{ borderLeft: "3px solid #00A870" }}
          >
            <ItemList items={config.outputs} color="#00A870" />
          </Card>
        </div>
      ),
    },
    {
      key: "refs",
      label: "依据与标准",
      children: (
        <Table
          size="small"
          pagination={false}
          dataSource={config.references}
          rowKey="title"
          columns={[
            { title: "标准/文献", dataIndex: "title", render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text> },
            { title: "来源", dataIndex: "source", width: 160, render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> },
          ]}
        />
      ),
    },
  ];

  return (
    <Drawer
      title={
        <div>
          <FileTextOutlined style={{ marginRight: 8, color: "#0052D9" }} />
          <span style={{ fontWeight: 600 }}>{config.title}</span>
          {config.subtitle && (
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 13, fontWeight: 400 }}>
              · {config.subtitle}
            </Text>
          )}
        </div>
      }
      placement="right"
      width={680}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={
        <Text type="secondary" style={{ fontSize: 11 }}>
          本流程说明仅供理解系统逻辑，实际执行以系统内数据为准。
        </Text>
      }
    >
      <Tabs items={tabItems} defaultActiveKey="flow" />
    </Drawer>
  );
}
