import { useEffect, useState } from "react";
import { Select, Space, App } from "antd";
import { api } from "../api/client";

export default function SitePicker({ value, onChange, style, selectWidth }: {
  value?: number;
  onChange: (id: number) => void;
  style?: React.CSSProperties;
  selectWidth?: number;
}) {
  const { message } = App.useApp();
  const [sites, setSites] = useState<any[]>([]);
  useEffect(() => {
    api.sites({ size: 200 }).then((d) => {
      setSites(d.items);
      if (!value && d.items.length) {
        sessionStorage.setItem("srs_current_site_id", String(d.items[0].id));
        onChange(d.items[0].id);
      }
    }).catch((err) => { message.error(err?.response?.data?.detail || "加载失败"); setSites([]); });
  }, []);
  const setSite = (id: number) => {
    sessionStorage.setItem("srs_current_site_id", String(id));
    onChange(id);
  };
  return (
    <Space style={style}>
      <span>选择场地：</span>
      <Select style={{ width: selectWidth ?? 380 }} value={value} onChange={setSite}
        showSearch
        optionFilterProp="label"
        options={sites.map((s) => ({ value: s.id, label: s.name, title: `${s.name}（${s.site_code}）` }))}
        placeholder="请选择场地" />
    </Space>
  );
}
