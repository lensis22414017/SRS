import { useState } from "react";
import { FloatButton, Drawer, Input, Button, List, Tag, Spin, Typography, Space } from "antd";
import { RobotOutlined, SendOutlined } from "@ant-design/icons";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";

interface Msg { role: "user" | "assistant"; content: string }

export default function AiAssistant({ siteId }: { siteId?: number }) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "您好，我是污染场地监管智能助手。可问我障碍因子、阈值标准、修复技术或本场地的诊断/评价结论。回答均基于知识库与场地真实数据。" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const resolveSiteId = () => {
    if (siteId) return siteId;
    const match = location.pathname.match(/^\/(?:sites|trace)\/(\d+)/);
    if (match) return Number(match[1]);
    const recent = sessionStorage.getItem("srs_current_site_id");
    return recent ? Number(recent) : undefined;
  };

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    const next = [...msgs, { role: "user" as const, content: q }];
    setMsgs(next); setInput(""); setLoading(true);
    try {
      const r = await api.aiChat(q, resolveSiteId(), next.slice(-6));
      setMsgs([...next, { role: "assistant", content: r.reply }]);
    } catch {
      setMsgs([...next, { role: "assistant", content: "AI 服务暂不可用，请稍后再试或联系管理员配置模型。" }]);
    } finally { setLoading(false); }
  };

  return (
    <>
      <FloatButton icon={<RobotOutlined />} type="primary" tooltip="AI 智能助手"
        onClick={() => setOpen(true)} style={{ right: 32, bottom: 32 }} />
      <Drawer title={<Space><RobotOutlined /> AI 智能助手（知识库 RAG）</Space>}
        open={open} onClose={() => setOpen(false)} width={420}>
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <Tag color={resolveSiteId() ? "blue" : "default"} style={{ alignSelf: "flex-start", marginBottom: 8 }}>
            {resolveSiteId() ? `当前场地上下文：#${resolveSiteId()}` : "当前未绑定具体场地"}
          </Tag>
          <List style={{ flex: 1, overflowY: "auto" }} dataSource={msgs}
            renderItem={(m) => (
              <List.Item style={{ border: "none", padding: "6px 0" }}>
                <div style={{ width: "100%", textAlign: m.role === "user" ? "right" : "left" }}>
                  <Tag color={m.role === "user" ? "blue" : "green"}>{m.role === "user" ? "我" : "助手"}</Tag>
                  <div style={{ display: "inline-block", maxWidth: "85%", padding: "8px 12px", borderRadius: 8,
                    background: m.role === "user" ? "#e6f0fb" : "#f3f6f9", marginTop: 4, whiteSpace: "pre-wrap", textAlign: "left" }}>
                    <Typography.Text>{m.content}</Typography.Text>
                  </div>
                </div>
              </List.Item>
            )} />
          {loading && <Spin style={{ margin: 8 }} />}
          <Space.Compact style={{ marginTop: 8 }}>
            <Input.TextArea value={input} onChange={(e) => setInput(e.target.value)} autoSize={{ minRows: 1, maxRows: 3 }}
              placeholder="例如：个旧场地砷超标该用什么技术？" onPressEnter={(e) => { e.preventDefault(); send(); }} />
            <Button type="primary" icon={<SendOutlined />} onClick={send} loading={loading} />
          </Space.Compact>
        </div>
      </Drawer>
    </>
  );
}
