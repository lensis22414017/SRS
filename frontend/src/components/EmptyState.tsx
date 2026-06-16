import { Empty, Button } from "antd";

interface EmptyStateProps {
  /** 显示图标（可用 antd 图标或自定义 ReactNode） */
  icon?: React.ReactNode;
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  style?: React.CSSProperties;
}

/**
 * 通用空状态组件。
 * 用于列表页、图表区、分析结果等无数据时的统一展示。
 * 支持自定义图标、说明文字和操作按钮。
 */
export default function EmptyState({
  icon,
  title = "暂无数据",
  description,
  actionLabel,
  onAction,
  style,
}: EmptyStateProps) {
  return (
    <Empty
      image={icon ?? Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <span>
          <span style={{ display: "block", fontWeight: 500, fontSize: 14, color: "#374151" }}>
            {title}
          </span>
          {description && (
            <span style={{ display: "block", fontSize: 12, color: "#6b7280", marginTop: 4 }}>
              {description}
            </span>
          )}
        </span>
      }
      style={{ padding: "32px 0", ...style }}
    >
      {actionLabel && onAction && (
        <Button type="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </Empty>
  );
}
