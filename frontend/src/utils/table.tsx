import type { ColumnType } from "antd/es/table";

/** 序号列: 居中, 自动行号 */
export function seqCol<T = any>(width = 64): ColumnType<T> {
  return {
    title: "序号", key: "__seq", width, align: "center",
    render: (_: any, __: T, i: number) => i + 1,
  };
}

/** 数字列: 居中显示 */
export function numCol<T = any>(title: string, dataIndex: string, opts: Partial<ColumnType<T>> = {}): ColumnType<T> {
  return {
    title, dataIndex, align: "center",
    render: (v: any) => (v === null || v === undefined || v === "" ? "—" : v),
    ...opts,
  };
}

/** 文字列: 左对齐两端展示 */
export function textCol<T = any>(title: string, dataIndex: string, opts: Partial<ColumnType<T>> = {}): ColumnType<T> {
  return {
    title, dataIndex, align: "left",
    onCell: () => ({ style: { textAlign: "justify" as const } }),
    render: (v: any) => (v === null || v === undefined || v === "" ? "—" : v),
    ...opts,
  };
}
