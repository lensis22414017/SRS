import axios from "axios";

const client = axios.create({ baseURL: "/api/v1" });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("srs_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && location.pathname !== "/login") {
      localStorage.removeItem("srs_token");
      location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export interface LoginResp {
  access_token: string;
  user: { username: string; display_name: string; roles: string[]; permissions: string[]; organization_id: number | null };
}

export const api = {
  login: (username: string, password: string) =>
    client.post<LoginResp>("/auth/login", { username, password }).then((r) => r.data),
  me: () => client.get("/auth/me").then((r) => r.data),

  // 注册 / 审核
  register: (body: {
    username: string; password: string; display_name: string;
    organization_name: string; role_code: string;
    contact_email?: string; contact_phone?: string;
  }) => client.post("/auth/register", body).then((r) => r.data),
  adminContact: () => client.get("/auth/admin-contact").then((r) => r.data),
  pendingApprovals: () => client.get("/auth/pending-approvals").then((r) => r.data),
  approveUser: (userId: number) => client.post(`/auth/approve/${userId}`).then((r) => r.data),
  rejectUser: (userId: number, reason: string) =>
    client.post(`/auth/reject/${userId}`, { reason }).then((r) => r.data),

  // 忘记密码 / 重置密码
  forgotPassword: (username: string) =>
    client.post("/auth/forgot-password", { username }).then((r) => r.data),
  resetPassword: (token: string, new_password: string) =>
    client.post("/auth/reset-password", { token, new_password }).then((r) => r.data),

  // 数据
  sites: (params?: any) => client.get("/sites", { params }).then((r) => r.data),
  site: (id: number) => client.get(`/sites/${id}`).then((r) => r.data),
  updateLandUse: (id: number, land_use_type: string) =>
    client.put(`/sites/${id}/land-use`, { land_use_type }).then((r) => r.data),
  points: (id: number) => client.get(`/sites/${id}/points`).then((r) => r.data),
  pointsWide: (id: number) => client.get(`/sites/${id}/points-wide`).then((r) => r.data),
  siteMapLayers: (id: number, params?: any) =>
    client.get(`/sites/${id}/map/layers`, { params }).then((r) => r.data),
  geoIndex: () => client.get("/map/geo/index").then((r) => r.data),
  geoBoundaries: (level: string, adcode?: number) =>
    client.get("/map/geo/boundaries", { params: { level, adcode } }).then((r) => r.data),
  eda: (id: number, params?: any) => client.get(`/sites/${id}/eda`, { params }).then((r) => r.data),
  measurements: (id: number, params?: any) =>
    client.get(`/sites/${id}/measurements`, { params }).then((r) => r.data),
  /** 导出场地检测长表(brief 4.3): csv/xlsx, blob 触发浏览器下载 */
  exportMeasurements: async (id: number, format: "csv" | "xlsx" = "csv") => {
    const r = await client.get(`/sites/${id}/measurements/export`,
      { params: { format }, responseType: "blob" });
    const url = URL.createObjectURL(r.data as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = `measurements_site${id}.${format}`; a.click();
    URL.revokeObjectURL(url);
  },
  importData: (mappingId: string, file: File, onConflict: string = "skip") => {
    const fd = new FormData();
    fd.append("mapping_id", mappingId);
    fd.append("file", file);
    fd.append("on_conflict", onConflict);
    return client.post("/import", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  importBatch: (mappingId: string, files: File[], onConflict: string = "skip") => {
    const fd = new FormData();
    fd.append("mapping_id", mappingId);
    fd.append("on_conflict", onConflict);
    files.forEach((f) => fd.append("files", f));
    return client.post("/import/batch", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  /** 字段映射 wizard — 第一步：读取文件列名和前3行预览 */
  importColumns: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return client.post<{ columns: string[]; preview: Record<string, string>[]; n_rows: number }>(
      "/import/columns", fd, { headers: { "Content-Type": "multipart/form-data" } }
    ).then((r) => r.data);
  },
  /** 字段映射 wizard — 最终导入：传入内联 mapping JSON + 文件 */
  importWizard: (mapping: object, file: File) => {
    const fd = new FormData();
    fd.append("mapping", JSON.stringify(mapping));
    fd.append("file", file);
    return client.post("/import/wizard", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  /** 报告 Blob（用于浏览器内预览） */
  reportBlob: (reportId: number) =>
    client.get(`/reports/${reportId}/download`, { responseType: "blob" }).then((r) => r.data as Blob),

  // 诊断 / 评价 / 推荐
  diagnosis: (id: number) => client.get(`/sites/${id}/diagnosis`).then((r) => r.data),
  runDiagnosis: (id: number) => client.post(`/sites/${id}/diagnosis`).then((r) => r.data),
  evaluation: (id: number) => client.get(`/sites/${id}/evaluation`).then((r) => r.data),
  runEvaluation: (id: number) => client.post(`/sites/${id}/evaluation`).then((r) => r.data),
  recommendation: (id: number) => client.get(`/sites/${id}/recommendation`).then((r) => r.data),
  runRecommendation: (id: number) => client.post(`/sites/${id}/recommendation`).then((r) => r.data),

  // 追溯 / 报告
  workflow: (id: number) => client.get(`/sites/${id}/workflow`).then((r) => r.data),
  initWorkflow: (id: number) => client.post(`/sites/${id}/workflow/init`).then((r) => r.data),
  updateStage: (id: number, stage: string, body: any) =>
    client.post(`/sites/${id}/workflow/${stage}`, body).then((r) => r.data),
  uploadAttachment: (id: number, stage: string, file: File, fileRole: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("file_role", fileRole);
    return client.post(`/sites/${id}/workflow/${stage}/attachment`, fd,
      { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
  reports: (id: number) => client.get(`/sites/${id}/reports`).then((r) => r.data),
  generateReport: (id: number, format: "pdf" | "docx" | "html" = "pdf") =>
    client.post(`/sites/${id}/report`, null, { params: { format } }).then((r) => r.data),
  downloadReport: async (reportId: number, filename: string) => {
    const r = await client.get(`/reports/${reportId}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },
  downloadAttachment: async (siteId: number, stage: string, attachmentId: number, filename: string) => {
    const r = await client.get(
      `/sites/${siteId}/workflow/${stage}/attachments/${attachmentId}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },

  // 系统
  changePassword: (old_password: string, new_password: string) =>
    client.post("/system/change-password", { old_password, new_password }).then((r) => r.data),
  auditLogs: (params?: any) => client.get("/system/audit-logs", { params }).then((r) => r.data),
  exportAuditLogs: async (params?: any) => {
    const r = await client.get("/system/audit-logs/export", { params, responseType: "blob" });
    const url = URL.createObjectURL(r.data as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  },
  exportTechnologies: async () => {
    const r = await client.get("/system/technologies/export", { responseType: "blob" });
    const url = URL.createObjectURL(r.data as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = `technologies_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  },
  systemConfig: () => client.get("/system/config").then((r) => r.data),
  systemHealth: () => client.get("/system/health").then((r) => r.data),
  users: () => client.get("/system/users").then((r) => r.data),

  // 联系方式
  contactInfo: () => client.get("/system/contact-info").then((r) => r.data),
  updateContactInfo: (body: { phone?: string; email?: string }) =>
    client.put("/system/contact-info", body).then((r) => r.data),

  // 场地统计
  siteStatistics: () => client.get("/sites/statistics").then((r) => r.data),

  // 技术库管理(brief 4.6)
  technologies: (params?: any) => client.get("/system/technologies", { params }).then((r) => r.data),
  createTechnology: (body: any) => client.post("/system/technologies", body).then((r) => r.data),
  updateTechnology: (id: number, body: any) => client.put(`/system/technologies/${id}`, body).then((r) => r.data),
  deleteTechnology: (id: number) => client.delete(`/system/technologies/${id}`).then((r) => r.data),

  // AI 模型配置
  aiConfigGet: () => client.get("/system/ai-config").then((r) => r.data),
  aiConfigPut: (body: { base_url: string; model: string; provider?: string; api_key?: string }) =>
    client.put("/system/ai-config", body).then((r) => r.data),
  aiConfigTest: () => client.post("/system/ai-config/test").then((r) => r.data),

  // AI
  aiStatus: () => client.get("/ai/status").then((r) => r.data),
  aiChat: (message: string, site_id?: number, history?: any[]) =>
    client.post("/ai/chat", { message, site_id, history }).then((r) => r.data),
};

export default client;
