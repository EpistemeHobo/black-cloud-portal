"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "primereact/button";
import { Checkbox } from "primereact/checkbox";
import { Column } from "primereact/column";
import { DataTable } from "primereact/datatable";
import { IconField } from "primereact/iconfield";
import { InputIcon } from "primereact/inputicon";
import { InputText } from "primereact/inputtext";
import { Tag } from "primereact/tag";
import { api, formatDateTime } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Account, AccountStatus } from "@/lib/types";

const STATUS: Record<AccountStatus, { label: string; severity: "success" | "warning" | "danger" | "secondary" }> = {
  active: { label: "ใช้งานได้", severity: "success" },
  pending: { label: "รออนุมัติ", severity: "warning" },
  suspended: { label: "ถูกระงับ", severity: "danger" },
  no_account: { label: "ยังไม่มีบัญชี", severity: "secondary" },
};

/** Accounts for admins: suspend, grant admin or auditor, send reset links. Sign-ups waiting
    for approval are on the requests page (/requests/). */
export default function UsersPage() {
  const { me, notify } = useSession();
  const [users, setUsers] = useState<Account[] | null>(null);
  const [search, setSearch] = useState("");
  const [showNoAccount, setShowNoAccount] = useState(false);

  const load = useCallback(() => {
    api<Account[]>("/api/admin/users").then(setUsers).catch((e) => notify("error", "โหลดรายชื่อผู้ใช้ไม่สำเร็จ", e.message));
  }, [notify]);
  useEffect(() => {
    if (me.is_admin) load();
  }, [me.is_admin, load]);

  const waiting = (users ?? []).filter((u) => u.status === "pending").length;
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (users ?? []).filter((u) =>
      u.status !== "pending" &&
      (showNoAccount || u.status !== "no_account") &&
      (!q || [u.name, u.email, u.unit].some((v) => v?.toLowerCase().includes(q))),
    );
  }, [users, search, showNoAccount]);

  if (!me.is_admin) return <p className="text-slate-600">หน้านี้สำหรับผู้ดูแลระบบเท่านั้น</p>;

  async function change(user: Account, body: Partial<Pick<Account, "is_admin" | "is_auditor">> & { status?: "active" | "suspended" }, done: string) {
    try {
      const updated = await api<Account>(`/api/people/${user.id}`, { method: "PATCH", body });
      setUsers((list) => list?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
      notify("success", done);
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
    }
  }

  async function sendReset(user: Account) {
    try {
      await api(`/api/admin/users/${user.id}/send-reset`, { method: "POST" });
      notify("success", `ส่งลิงก์ตั้งรหัสผ่านไปที่ ${user.email} แล้ว`);
    } catch (e) {
      notify("error", "ส่งลิงก์ไม่สำเร็จ", (e as Error).message);
    }
  }

  const isMe = (u: Account) => u.id === me.id;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="page-title metal-ink">ผู้ใช้</h1>
          <p className="text-slate-600">ระงับบัญชี กำหนดสิทธิ์ และส่งลิงก์ตั้งรหัสผ่าน</p>
        </div>
      </div>

      {waiting > 0 && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-slate-700">
          มีคำขอใช้งาน {waiting} รายการที่ยังไม่อยู่ในรายชื่อนี้{" "}
          <Link href="/requests/" className="font-semibold text-slate-900 underline-offset-2 hover:underline">ไปที่จัดการคำขอ</Link>
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <IconField iconPosition="left" className="min-w-64 flex-1">
          <InputIcon className="pi pi-search" />
          <InputText value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ค้นหาชื่อ, อีเมล, หน่วยงาน…" className="w-full" />
        </IconField>
        <label className="flex items-center gap-2 px-2 text-sm text-slate-600">
          <Checkbox checked={showNoAccount} onChange={(e) => setShowNoAccount(!!e.checked)} />
          แสดงคนที่ยังไม่มีบัญชี (ถูกเพิ่มเป็นเจ้าของระบบ)
        </label>
      </div>

      <DataTable value={visible} loading={users === null} dataKey="id" stripedRows size="small"
        emptyMessage="ไม่พบผู้ใช้" className="rounded-lg border border-slate-200 bg-white">
        <Column header="ชื่อ" body={(u: Account) => (
          <div>
            <div className="font-medium text-slate-900">{u.name}{isMe(u) && <span className="ml-2 text-xs text-slate-500">(คุณ)</span>}</div>
            <div className="text-sm text-slate-500">{u.email}</div>
          </div>
        )} />
        <Column header="สถานะ" body={(u: Account) => (
          <div className="flex flex-wrap gap-1">
            <Tag value={STATUS[u.status].label} severity={STATUS[u.status].severity} />
            {u.locked && <Tag value="ล็อกชั่วคราว" severity="danger" icon="pi pi-lock" />}
          </div>
        )} />
        <Column header="ผู้ดูแลระบบ" align="center" body={(u: Account) => (
          <Checkbox checked={u.is_admin} disabled={u.status === "no_account" || isMe(u)}
            onChange={(e) => change(u, { is_admin: !!e.checked }, e.checked ? `${u.name} เป็นผู้ดูแลระบบแล้ว` : `ถอนสิทธิ์ผู้ดูแลระบบของ ${u.name} แล้ว`)} />
        )} />
        <Column header="ผู้ตรวจสอบ" align="center" body={(u: Account) => (
          <Checkbox checked={u.is_auditor} disabled={u.status === "no_account"}
            onChange={(e) => change(u, { is_auditor: !!e.checked }, e.checked ? `${u.name} เป็นผู้ตรวจสอบแล้ว` : `ถอนสิทธิ์ผู้ตรวจสอบของ ${u.name} แล้ว`)} />
        )} />
        <Column header="เข้าใช้ล่าสุด" body={(u: Account) => (
          <span className="text-sm text-slate-600">{u.last_sign_in_at ? formatDateTime(u.last_sign_in_at) : "–"}</span>
        )} />
        <Column header="" align="right" body={(u: Account) => (
          <div className="flex justify-end gap-1">
            {u.status === "active" && !isMe(u) && (
              <Button label="ระงับ" icon="pi pi-ban" size="small" text severity="danger"
                onClick={() => change(u, { status: "suspended" }, `ระงับบัญชี ${u.name} แล้ว`)} />
            )}
            {u.status === "suspended" && (
              <Button label="เปิดใช้อีกครั้ง" icon="pi pi-replay" size="small" text
                onClick={() => change(u, { status: "active" }, `เปิดใช้บัญชี ${u.name} อีกครั้งแล้ว`)} />
            )}
            {(u.status === "active" || u.status === "suspended") && (
              <Button label="ส่งลิงก์ตั้งรหัสผ่าน" icon="pi pi-envelope" size="small" text onClick={() => sendReset(u)} />
            )}
          </div>
        )} />
      </DataTable>
    </div>
  );
}
