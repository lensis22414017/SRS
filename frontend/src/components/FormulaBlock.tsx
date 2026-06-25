/**
 * FormulaBlock — LaTeX 数学公式展示组件
 *
 * 依赖: katex + react-katex (package.json 已声明, npm install 后生效)
 * 降级: 若渲染失败, 回退为等宽文本显示 (不报错, 不白屏)
 *
 * 使用示例:
 *   <FormulaBlock
 *     title="SSUI 综合指数"
 *     latex="SSUI = \left(\sum_{i=1}^{n} vC_i \cdot SC_i\right) \cdot f(t) \cdot M"
 *     source="《污染场地土壤可持续利用评价方法》第三章 §3.2"
 *   />
 */
import { useState, useEffect, useRef } from "react";
import { Card, Typography, Tag } from "antd";

const { Text } = Typography;

interface FormulaBlockProps {
  /** 公式区块标题 */
  title: string;
  /** LaTeX 字符串 */
  latex: string;
  /** 来源引用(文献/标准/方法文件) */
  source?: string;
  /** 补充说明文字 */
  note?: string;
  /** 额外内嵌说明元素 (参数表等) */
  children?: React.ReactNode;
}

export default function FormulaBlock({
  title,
  latex,
  source,
  note,
  children,
}: FormulaBlockProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState(false);

  useEffect(() => {
    if (!ref.current) return;

    // 动态 import katex, 避免 SSR/bundle 问题; 若未安装则降级为文本
    import("katex")
      .then((katex) => {
        if (!ref.current) return;
        try {
          katex.default.render(latex, ref.current, {
            displayMode: true,
            throwOnError: false,
            trust: false,
            strict: false,
          });
          setRenderError(false);
        } catch {
          setRenderError(true);
        }
      })
      .catch(() => {
        setRenderError(true);
      });
  }, [latex]);

  // 也动态加载 katex CSS (只加载一次)
  useEffect(() => {
    if (document.getElementById("katex-css")) return;
    const link = document.createElement("link");
    link.id = "katex-css";
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css";
    document.head.appendChild(link);
  }, []);

  return (
    <Card
      size="small"
      style={{
        background: "linear-gradient(135deg, #f0f4ff 0%, #e8f4f8 100%)",
        border: "1px solid #d0dff0",
        borderRadius: 8,
        marginBottom: 12,
      }}
      styles={{ body: { padding: "12px 16px" } }}
    >
      {/* 标题行 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Tag color="blue" style={{ fontSize: 12, fontWeight: 600, margin: 0 }}>
          方法公式
        </Tag>
        <Text strong style={{ fontSize: 13, color: "#0f3d6e" }}>
          {title}
        </Text>
      </div>

      {/* 公式渲染区 */}
      {renderError ? (
        /* 降级: 等宽字体文本 */
        <div
          style={{
            fontFamily: "'Courier New', monospace",
            fontSize: 14,
            color: "#1d6fb8",
            background: "#fff",
            borderRadius: 4,
            padding: "8px 12px",
            border: "1px solid #b8d0e8",
            wordBreak: "break-all",
          }}
        >
          {latex}
        </div>
      ) : (
        <div
          ref={ref}
          style={{
            background: "#fff",
            borderRadius: 4,
            padding: "8px 12px",
            border: "1px solid #b8d0e8",
            overflowX: "auto",
            minHeight: 40,
          }}
        />
      )}

      {/* 来源引用 */}
      {source && (
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            📖 来源：{source}
          </Text>
        </div>
      )}

      {/* 补充说明 */}
      {note && (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {note}
          </Text>
        </div>
      )}

      {/* 参数说明表等子内容 */}
      {children && <div style={{ marginTop: 10 }}>{children}</div>}
    </Card>
  );
}
