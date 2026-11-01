"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { confirmPopup, ConfirmPopup } from "primereact/confirmpopup";
import { api, formatDate } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Account } from "@/lib/types";

/** Sign-ups waiting for an admin: approve or reject. */
export default function RequestsPage() {
  const { me, notify } = useSession();
  const [waiting, setWaiting] = useState<Account[] | null>(null);

  const load = useCallback(() => {
    api<Account[]>("/api/admin/users")
      .then((users) => setWaiting(users.filter((u) => u.status === "pending")))
      .catch((e) => notify("error", "โหลดคำขอไม่สำเร็จ", e.message));
  }, [notify]);
  useEffect(() => {
    if (me.is_admin) load();
  }, [me.is_admin, load]);

  if (!me.is_admin) return <p className="text-slate-600">หน้านี้สำหรับผู้ดูแลระบบเท่านั้น</p>;

  async function approve(user: Account) {
    try {
      await api(`/api/people/${user.id}`, { method: "PATCH", body: { status: "active" } });
      notify("success", `อนุมัติ ${user.name} แล้ว`);
      load();
    } catch (e) {
      notify("error", "อนุมัติไม่สำเร็จ", (e as Error).message);
    }
  }

  function reject(event: React.MouseEvent<HTMLButtonElement>, user: Account) {
    confirmPopup({
      target: event.currentTarget,
      icon: "pi pi-exclamation-triangle",
      message: `ปฏิเสธคำขอของ ${user.name}?`,
      acceptLabel: "ปฏิเสธ",
      rejectLabel: "ยกเลิก",
      acceptClassName: "p-button-danger",
      accept: async () => {
        try {
          await api(`/api/admin/users/${user.id}`, { method: "DELETE" });
          notify("success", "ปฏิเสธคำขอแล้ว");
          load();
        } catch (e) {
          notify("error", "ปฏิเสธไม่สำเร็จ", (e as Error).message);
        }
      },
    });
  }

  return (
    <div className="space-y-6">
      <ConfirmPopup />
      <div>
        <h1 className="page-title metal-ink">จัดการคำขอ</h1>
        <p className="text-slate-600">คนที่สมัครใช้งานและรอการอนุมัติ อนุมัติได้หลังจากผู้สมัครยืนยันอีเมลแล้ว</p>
      </div>

      {waiting === null ? (
        <p className="text-slate-500">กำลังโหลด…</p>
      ) : waiting.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-slate-500">ไม่มีคำขอที่รออนุมัติ</p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {waiting.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-slate-900">{u.name}</div>
                <div className="text-sm text-slate-600">
                  {u.email} · สมัครเมื่อ {formatDate(u.created_at)}
                  {u.email_verified
                    ? <span className="ml-2 text-emerald-700">ยืนยันอีเมลแล้ว</span>
                    : <span className="ml-2 text-amber-700">ยังไม่ได้ยืนยันอีเมล</span>}
                </div>
              </div>
              <Button label="อนุมัติ" icon="pi pi-check" size="small" disabled={!u.email_verified}
                tooltip={u.email_verified ? undefined : "อนุมัติได้หลังจากผู้สมัครกดลิงก์ยืนยันในอีเมล"}
                tooltipOptions={{ showOnDisabled: true, position: "top" }}
                onClick={() => approve(u)} />
              <Button label="ปฏิเสธ" icon="pi pi-times" size="small" severity="danger" outlined onClick={(e) => reject(e, u)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
