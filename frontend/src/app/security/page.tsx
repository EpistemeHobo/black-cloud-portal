"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { Column } from "primereact/column";
import { DataTable } from "primereact/datatable";
import { SelectButton } from "primereact/selectbutton";
import { Tag } from "primereact/tag";
import { Card, SeverityTag } from "@/components/bits";
import { api, formatDateTime } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SecretAlert } from "@/lib/types";

type Rule = { id: string; label: string; severity: string; blocks_save: boolean };
type ScanRun = {
  id: number; trigger: string; started_at: string; finished_at: string | null; systems_scanned: number;
  texts_scanned: number; findings: number; new_alerts: number; error: string | null; started_by: string | null;
};
type Scans = { interval_hours: number; runs: ScanRun[] };

const TRIGGERS: Record<string, string> = { scheduled: "ตามรอบ", manual: "ผู้ดูแลสั่ง", cli: "คำสั่ง (cron)" };

/** Admins: how often everything is scanned, the recent scans, and a button to scan now. */
function ScanRuns() {
  const { notify } = useSession();
  const [scans, setScans] = useState<Scans | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    api<Scans>("/api/admin/secret-scans").then(setScans).catch((e) => notify("error", "โหลดประวัติการตรวจไม่สำเร็จ", e.message));
  }, [notify]);
  useEffect(load, [load]);

  async function scanNow() {
    setBusy(true);
    try {
      await api("/api/admin/secret-scans", { method: "POST" });
      notify("info", "เริ่มตรวจทุกระบบแล้ว", "ผลจะขึ้นในตารางเมื่อเสร็จ");
      setTimeout(load, 3000);
    } catch (e) {
      notify("error", "เริ่มตรวจไม่สำเร็จ", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="การตรวจทุกระบบตามรอบ (ผู้ดูแลพอร์ทัล)"
      actions={<Button label="ตรวจทุกระบบตอนนี้" icon="pi pi-refresh" size="small" outlined loading={busy} onClick={scanNow} />}>
      {scans && (
        <p className="-mt-1 mb-3 text-sm text-slate-600">
          {scans.interval_hours > 0
            ? `พอร์ทัลตรวจทุกระบบ รวมทั้งไฟล์แนบ ทุก ${scans.interval_hours} ชั่วโมง`
            : "ปิดการตรวจตามรอบในแอปไว้ (SECRET_SCAN_INTERVAL_HOURS=0) ให้ตั้ง cron เรียก python -m app.leak_scan แทน"}
        </p>
      )}
      <DataTable value={scans?.runs ?? []} loading={scans === null} size="small" stripedRows paginator rows={10}
        emptyMessage="ยังไม่เคยตรวจ" className="overflow-hidden rounded-lg border border-slate-200">
        <Column header="เริ่ม" body={(r: ScanRun) => <span className="whitespace-nowrap text-sm">{formatDateTime(r.started_at)}</span>} />
        <Column header="แบบ" body={(r: ScanRun) => <span className="text-sm">{TRIGGERS[r.trigger] ?? r.trigger}{r.started_by && ` · ${r.started_by}`}</span>} />
        <Column header="ระบบ" body={(r: ScanRun) => <span className="tabular-nums">{r.systems_scanned}</span>} />
        <Column header="ข้อความ" body={(r: ScanRun) => <span className="tabular-nums">{r.texts_scanned}</span>} />
        <Column header="ที่พบ" body={(r: ScanRun) => <span className="tabular-nums">{r.findings}</span>} />
        <Column header="แจ้งเตือนใหม่" body={(r: ScanRun) => r.new_alerts > 0
          ? <Tag value={String(r.new_alerts)} severity="danger" /> : <span className="text-slate-400">0</span>} />
        <Column header="ผล" body={(r: ScanRun) => r.error
          ? <span className="text-xs text-rose-700">{r.error}</span>
          : r.finished_at ? <i className="pi pi-check text-emerald-600" aria-label="เสร็จ" /> : <span className="text-xs text-slate-500">กำลังตรวจ…</span>} />
      </DataTable>
    </Card>
  );
}

/** Leak alerts on every system the viewer is part of (every system, for an admin). */
export default function SecurityPage() {
  const { me, meta, notify } = useSession();
  const [alerts, setAlerts] = useState<SecretAlert[] | null>(null);
  const [show, setShow] = useState<"open" | "all">("open");
  const [rules, setRules] = useState<Rule[]>([]);

  useEffect(() => {
    api<SecretAlert[]>(`/api/secret-alerts?status=${show}`).then(setAlerts)
      .catch((e) => notify("error", "โหลดการแจ้งเตือนไม่สำเร็จ", e.message));
  }, [show, notify]);
  useEffect(() => { api<Rule[]>("/api/secret-scan/rules").then(setRules).catch(() => undefined); }, []);

  const resolution = (k: string | null) => meta.alert_resolutions.find((r) => r.key === k)?.label ?? k;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="page-title metal-ink">ความปลอดภัย</h1>
        <p className="text-slate-600">
          รหัสลับที่พอร์ทัลพบในข้อความและไฟล์แนบของ{me.is_admin ? "ทุกระบบ" : "ระบบที่คุณเป็นเจ้าของ ผู้ดูแลสำรอง หรือนักพัฒนา"}
          {" "}จัดการแต่ละรายการได้ที่แท็บ &quot;รหัสลับและความปลอดภัย&quot; ของระบบนั้น
        </p>
      </div>

      <Card title="การแจ้งเตือนรหัสลับรั่วไหล" actions={
        <SelectButton value={show} onChange={(e) => e.value && setShow(e.value)} allowEmpty={false}
          options={[{ label: "ยังไม่ปิด", value: "open" }, { label: "ทั้งหมด", value: "all" }]} className="p-selectbutton-sm" />
      }>
        <DataTable value={alerts ?? []} loading={alerts === null} dataKey="id" size="small" stripedRows paginator rows={25}
          emptyMessage={show === "open" ? "ไม่มีการแจ้งเตือนที่ยังไม่ปิด" : "ยังไม่เคยพบรหัสลับ"}
          className="overflow-hidden rounded-lg border border-slate-200">
          <Column header="ระบบ" body={(a: SecretAlert) => (
            <Link href={`/system/?id=${encodeURIComponent(a.system_id)}&tab=security`} className="font-medium text-sky-700 hover:underline">
              {a.system_name}
            </Link>
          )} />
          <Column header="ความรุนแรง" body={(a: SecretAlert) => <SeverityTag severity={a.severity} />} />
          <Column header="สิ่งที่พบ" body={(a: SecretAlert) => (
            <span className="text-sm">{a.rule_label} <code className="text-xs text-slate-600">{a.preview}</code></span>
          )} />
          <Column header="ที่" body={(a: SecretAlert) => (
            <span className="text-sm text-slate-600">{a.location_label}{a.line ? ` บรรทัด ${a.line}` : ""}</span>
          )} />
          <Column header="พบเมื่อ" body={(a: SecretAlert) => <span className="whitespace-nowrap text-sm">{formatDateTime(a.first_seen_at)}</span>} />
          <Column header="สถานะ" body={(a: SecretAlert) => a.status === "open"
            ? <Tag value={a.still_present ? "ยังอยู่ในข้อความ" : "ยังไม่ปิด"} severity="danger" />
            : <Tag value={resolution(a.resolution) ?? "ปิดแล้ว"} severity="success" />} />
        </DataTable>
      </Card>

      {me.is_admin && <ScanRuns />}

      <Card title="สิ่งที่พอร์ทัลตรวจหา">
        <p className="-mt-1 mb-3 text-sm text-slate-600">
          รายการที่ระดับวิกฤตหรือสูงจะถูกถามยืนยันก่อนบันทึก ถ้าเป็นค่าตัวอย่างในเอกสาร ให้ใส่คำว่า <code>portal:ignore-secret</code> ไว้ในบรรทัดเดียวกัน
        </p>
        <ul className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {rules.map((r) => (
            <li key={r.id} className="flex items-center gap-2">
              <SeverityTag severity={r.severity} />
              <span>{r.label}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
