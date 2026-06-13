import { useEffect, useState } from "react";
import { Select, Space } from "antd";
import { api } from "../api/client";

export default function SitePicker({ value, onChange }: { value?: number; onChange: (id: number) => void }) {
  const [sites, setSites] = useState<any[]>([]);
  useEffect(() => {
    api.sites({ size: 200 }).then((d) => {
      setSites(d.items);
      if (!value && d.items.length) {
        sessionStorage.setItem("srs_current_site_id", String(d.items[0].id));
        onChange(d.items[0].id);
      }
    });
  }, []);
  const setSite = (id: number) => {
    sessionStorage.setItem("srs_current_site_id", String(id));
    onChange(id);
  };
  return (
    <Space>
      <span>选择场地：</span>
      <Select style={{ width: 320 }} value={value} onChange={setSite}
        options={sites.map((s) => ({ value: s.id, label: `${s.name}（${s.site_code}）` }))}
        placeholder="请选择场地" />
    </Space>
  );
}
