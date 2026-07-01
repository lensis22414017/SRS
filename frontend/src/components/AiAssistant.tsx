import { useEffect, useState } from "react";
import { FloatButton, Drawer, Input, Button, List, Tag, Spin, Typography, Space } from "antd";
import { RobotOutlined, SendOutlined } from "@ant-design/icons";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";

interface Msg { role: "user" | "assistant"; content: string }

export default function AiAssistant({ siteId }: { siteId?: number }) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: "您好，我是污染场地监管智能助手。可问我障碍因子、阈值标准、修复技术或本场地的诊断/评价结论。回答均基于知识库与场地真实数据，不编造标准与文献。" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiStat, setAiStat] = useState<any>(null);     // /ai/status 模型配置(brief 4.7)
  const [lastMeta, setLastMeta] = useState<any>(null); // 最近 chat 的知识库命中

  useEffect(() => { api.aiStatus().then(setAiStat).catch(() => {}); }, []);

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
    const hist = msgs.slice(-6);  // 历史(不含当前消息, brief 4.7 防前端重复发)
    const next = [...msgs, { role: "user" as const, content: q }];
    setMsgs(next); setInput(""); setLoading(true);
    try {
      const r = await api.aiChat(q, resolveSiteId(), hist);
      setLastMeta({
        configured: r.configured, degraded: r.degraded, error: r.error,
        nFactor: r.context?.factors?.length ?? 0,
        nThr: r.context?.thresholds?.length ?? 0,
        nTech: r.context?.technologies?.length ?? 0,
      });
      setMsgs([...next, { role: "assistant", content: r.reply }]);
    } catch (e: any) {
      // brief 4.7: 显后端 detail 而非笼统"AI 服务暂不可用"
      const detail = e?.response?.data?.detail || e?.response?.data?.reply
        || `AI 调用失败(${e?.message || "未知原因"})`;
      setMsgs([...next, { role: "assistant", content: `⚠ ${detail}` }]);
    } finally { setLoading(false); }
  };

  const sid = resolveSiteId();
  // 区分"已配置"与"已连通", UI 不得把"填了 key"显示成"已就绪"
  const modelLabel = !aiStat
    ? "模型状态加载中…"
    : !aiStat.has_config
      ? "模型未配置(走 RAG 降级)"
      : aiStat.connectivity_ok
        ? `模型: ${aiStat.model}`
        : aiStat.connectivity_stale
          ? `模型: ${aiStat.model}(连通待复测)`
          : "已配置但连通失败(走 RAG 降级)";
  const modelColor = aiStat?.has_config && aiStat?.connectivity_ok ? "green" : "orange";

  return (
    <>
      <FloatButton icon={<RobotOutlined />} type="primary" tooltip="AI 智能助手"
        onClick={() => setOpen(true)} style={{ right: 32, bottom: 32 }} />
      <Drawer title={<Space><RobotOutlined /> AI 智能助手（知识库 RAG）</Space>}
        open={open} onClose={() => setOpen(false)} width={420}>
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* brief 4.7: 顶部状态栏 — 模型状态/场地上下文/知识库命中数 */}
          <Space wrap size={6} style={{ marginBottom: 8 }}>
            <Tag color={modelColor}>{modelLabel}</Tag>
            <Tag color={sid ? "blue" : "default"}>{sid ? `场地上下文: #${sid}` : "未绑定场地"}</Tag>
            {lastMeta && (
              <Tag color="purple">知识库命中: {lastMeta.nFactor}因子 / {lastMeta.nThr}阈值 / {lastMeta.nTech}技术</Tag>
            )}
            {lastMeta?.degraded && <Tag color="gold">本次 RAG 降级</Tag>}
          </Space>
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
