"use client";

import { useEffect, useMemo, useState } from "react";
import { Column } from "primereact/column";
import { DataTable } from "primereact/datatable";
import { Dropdown } from "primereact/dropdown";
import { IconField } from "primereact/iconfield";
import { InputIcon } from "primereact/inputicon";
import { InputText } from "primereact/inputtext";
import { Tag } from "primereact/tag";
import { api, formatDateTime } from "@/lib/api";
import { useSession } from "@/lib/session";

type ActivityEvent = {
  id: number;
  at: string;
  action: string;
  actor_email: string | null;
  subject_email: string | null;
  detail: string | null;
  ip: string | null;
};

// Events worth an admin's attention stand out.
const WARNING = new Set(["sign_in_failed", "locked", "suspended", "rejected"]);

/** Account events: sign-ins, sign-ups, approvals, password resets. Newest first. */
export default function ActivityPage() {
  const { me, notify } = useSession();
  const [data, setData] = useState<{ actions: Record<string, string>; events: ActivityEvent[] } | null>(null);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState<string | null>(null);

  useEffect(() => {
    if (!me.is_admin) return;
    api<{ actions: Record<string, string>; events: ActivityEvent[] }>("/api/admin/activity")
      .then(setData)
      .catch((e) => notify("error", "โหลดประวัติการใช้งานไม่สำเร็จ", e.message));
  }, [me.is_admin, notify]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.events ?? []).filter((e) =>
      (!action || e.action === action) &&
      (!q || [e.actor_email, e.subject_email, e.detail, e.ip].some((v) => v?.toLowerCase().includes(q))),
    );
  }, [data, search, action]);

  if (!me.is_admin) return <p className="text-slate-600">หน้านี้สำหรับผู้ดูแลระบบเท่านั้น</p>;

  const label = (a: string) => data?.actions[a] ?? a;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="page-title metal-ink">ประวัติการใช้งาน</h1>
        <p className="text-slate-600">
          การเข้าสู่ระบบ การสมัครใช้งาน การอนุมัติ และการตั้งรหัสผ่าน ล่าสุด 500 รายการ
          (การแก้ไขข้อมูลของแต่ละระบบอยู่ในแท็บประวัติของหน้าระบบนั้น)
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <IconField iconPosition="left" className="min-w-64 flex-1">
          <InputIcon className="pi pi-search" />
          <InputText value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ค้นหาอีเมล, รายละเอียด, IP…" className="w-full" />
        </IconField>
        <Dropdown value={action} onChange={(e) => setAction(e.value)} showClear placeholder="ทุกเหตุการณ์"
          options={Object.entries(data?.actions ?? {}).map(([value, text]) => ({ value, label: text }))} />
      </div>

      <DataTable value={visible} loading={data === null} dataKey="id" stripedRows size="small" paginator rows={50}
        emptyMessage="ยังไม่มีประวัติ" className="rounded-lg border border-slate-200 bg-white">
        <Column header="เวลา" body={(e: ActivityEvent) => <span className="whitespace-nowrap text-sm">{formatDateTime(e.at)}</span>} />
        <Column header="เหตุการณ์" body={(e: ActivityEvent) => (
          <Tag value={label(e.action)} severity={WARNING.has(e.action) ? "danger" : "info"} />
        )} />
        <Column header="บัญชี" body={(e: ActivityEvent) => <span className="text-sm">{e.subject_email ?? "–"}</span>} />
        <Column header="ผู้ทำรายการ" body={(e: ActivityEvent) => (
          <span className="text-sm text-slate-600">
            {!e.actor_email ? "–" : e.actor_email === e.subject_email ? "เจ้าของบัญชี" : e.actor_email}
          </span>
        )} />
        <Column header="รายละเอียด" body={(e: ActivityEvent) => <span className="text-sm text-slate-600">{e.detail ?? ""}</span>} />
        <Column header="IP" body={(e: ActivityEvent) => <span className="font-mono text-xs text-slate-500">{e.ip ?? ""}</span>} />
      </DataTable>
    </div>
  );
}
