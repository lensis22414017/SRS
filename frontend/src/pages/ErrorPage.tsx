import { Result, Button } from "antd";
import { useNavigate, useRouteError } from "react-router-dom";

type StatusCode = 403 | 404 | 500;

const ERROR_CONFIG: Record<StatusCode, { title: string; subTitle: string }> = {
  403: {
    title: "403 — 无访问权限",
    subTitle: "您没有权限访问该页面，请联系系统管理员。",
  },
  404: {
    title: "404 — 页面不存在",
    subTitle: "您访问的页面不存在，可能已被移除或链接有误。",
  },
  500: {
    title: "500 — 服务器错误",
    subTitle: "服务器发生错误，请稍后重试或联系运维人员。",
  },
};

interface ErrorPageProps {
  /** 显式指定错误码（用于权限拦截等已知场景）。省略时从路由错误中自动推断。 */
  status?: StatusCode;
  /** 可选的自定义错误描述，优先级高于默认 subTitle */
  message?: string;
}

/**
 * 通用错误页：404 / 403 / 500。
 * 用法：
 *   <Route path="*" element={<ErrorPage />} />                   // 404 catch-all
 *   <Route element={<AdminOnly><X /></AdminOnly>} />              // 403 在 AdminOnly 中使用
 *   errorElement={<ErrorPage />}                                  // React Router v6 errorElement
 */
export default function ErrorPage({ status, message: customMsg }: ErrorPageProps) {
  const nav = useNavigate();
  const routeError = useRouteError() as any;

  // 推断状态码：优先使用 prop，其次从路由错误对象推断
  let code: StatusCode = status ?? 404;
  if (!status && routeError) {
    const s = routeError?.status ?? routeError?.response?.status;
    if (s === 403 || s === 404 || s === 500) code = s;
    else if (s >= 500) code = 500;
  }

  const cfg = ERROR_CONFIG[code] ?? ERROR_CONFIG[404];

  return (
    <div
      style={{
        minHeight: "60vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Result
        status={code as any}
        title={cfg.title}
        subTitle={customMsg || cfg.subTitle}
        extra={
          <Button type="primary" onClick={() => nav("/")}>
            返回首页
          </Button>
        }
      />
    </div>
  );
}
