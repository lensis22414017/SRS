import { Typography, Space } from "antd";
import { InboxOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface EmptyStateProps {
  description?: string;
  style?: React.CSSProperties;
}

export default function EmptyState({ description = "暂无数据，请先选择或运行", style }: EmptyStateProps) {
  return (
    <div style={{
      padding: "64px 24px",
      textAlign: "center",
      background: "linear-gradient(180deg, rgba(248, 250, 252, 0.4) 0%, rgba(241, 245, 249, 0.6) 100%)",
      border: "1px dashed #cbd5e1",
      borderRadius: 12,
      ...style
    }}>
      <Space direction="vertical" size={16}>
        <div style={{ 
          width: 72, height: 72, margin: "0 auto", borderRadius: "50%",
          background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center" 
        }}>
          <InboxOutlined style={{ fontSize: 36, color: "#94a3b8" }} />
        </div>
        <Text type="secondary" style={{ fontSize: 14, color: "#64748b", letterSpacing: 0.5 }}>
          {description}
        </Text>
      </Space>
    </div>
  );
}
