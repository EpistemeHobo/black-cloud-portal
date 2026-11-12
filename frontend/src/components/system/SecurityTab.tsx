"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { Dialog } from "primereact/dialog";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { SelectButton } from "primereact/selectbutton";
import { Tag } from "primereact/tag";
import { Card, Empty, SeverityTag } from "@/components/bits";
import { api, formatDateTime } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SecretAlert, SystemDetail } from "@/lib/types";
import SecretBoxesCard from "./SecretBoxes";

function AlertsCard({ system, onChange }: { system: SystemDetail; onChange: () => void }) {
  const { meta, notify } = useSession();
  const [alerts, setAlerts] = useState<SecretAlert[] | null>(null);
  const [show, setShow] = useState<"open" | "all">("open");
  const [closing, setClosing] = useState<{ alert: SecretAlert; resolution: string; note: string } | null>(null);
  const base = `/api/systems/${encodeURIComponent(system.id)}/secret-alerts`;

  const load = useCallback(() => {
    api<SecretAlert[]>(base).then(setAlerts).catch((e) => notify("error", "โหลดการแจ้งเตือนไม่สำเร็จ", e.message));
  }, [base, notify]);
  useEffect(load, [load]);

  async function resolve(alert: SecretAlert, resolution: string | null, note?: string) {
    try {
      setAlerts(await api<SecretAlert[]>(`${base}/${alert.id}`, { method: "PUT", body: { resolution, note } }));
      setClosing(null);
      onChange();
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
    }
  }

  const resolutionLabel = (k: string | null) => meta.alert_resolutions.find((r) => r.key === k)?.label ?? k;
  const visible = (alerts ?? []).filter((a) => show === "all" || a.status === "open");

  return (
    <Card
      title={<><i className="pi pi-shield text-slate-500" aria-hidden />การแจ้งเตือนรหัสลับรั่วไหล</>}
      actions={<SelectButton value={show} onChange={(e) => e.value && setShow(e.value)} allowEmpty={false}
        options={[{ label: "ยังไม่ปิด", value: "open" }, { label: "ทั้งหมด", value: "all" }]} className="p-selectbutton-sm" />}
    >
      <p className="-mt-1 mb-3 text-sm text-slate-600">
        พอร์ทัลตรวจทุกข้อความและไฟล์แนบของระบบเมื่อบันทึก และตรวจซ้ำทั้งหมดเป็นระยะ หากพบข้อความที่ดูเหมือนรหัสลับ
        คนนอกทีมจะเห็นข้อความนั้นถูกซ่อนไว้ จนกว่าจะปิดการแจ้งเตือนว่าไม่ใช่รหัสลับ
      </p>
      <ol className="mb-3 list-decimal space-y-0.5 pl-5 text-xs text-slate-600">
        <li>ถือว่ารหัสนั้นรั่วแล้ว: เปลี่ยนหรือยกเลิกที่ต้นทางก่อน (เช่น หน้าตั้งค่า token ของ GitLab หรือ IAM ของ AWS)</li>
        <li>ลบรหัสออกจากข้อความหรือไฟล์ แล้วเก็บค่าใหม่ไว้ในกล่องรหัสลับด้านล่าง</li>
        <li>ปิดการแจ้งเตือนพร้อมเหตุผล ข้อความเก่ายังอยู่ในประวัติการแก้ไข จึงต้องเปลี่ยนค่าเสมอ ไม่ใช่แค่ลบออก</li>
      </ol>
      {alerts === null ? <Empty>กำลังโหลด…</Empty> : visible.length === 0 ? (
        <Empty>{show === "open" ? "ไม่มีการแจ้งเตือนที่ยังไม่ปิด" : "ยังไม่เคยพบรหัสลับในระบบนี้"}</Empty>
      ) : (
        <ul className="space-y-2">
          {visible.map((a) => (
            <li key={a.id} className={`rounded-lg border p-3 ${a.status === "open" ? "border-rose-200 bg-rose-50/40" : "border-slate-200 bg-slate-50"}`}>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityTag severity={a.severity} />
                <span className="font-medium text-slate-900">{a.rule_label}</span>
                <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700 ring-1 ring-slate-200">{a.preview}</code>
                {a.status === "open" ? (
                  <Tag value={a.still_present ? "ยังอยู่ในข้อความ" : "ลบออกจากข้อความแล้ว"} severity={a.still_present ? "danger" : "warning"} />
                ) : (
                  <Tag value={`ปิดแล้ว: ${resolutionLabel(a.resolution)}`} severity="success" />
                )}
                <span className="ml-auto">
                  {a.status === "open" ? (
                    <Button label="ปิดการแจ้งเตือน" size="small" outlined
                      onClick={() => setClosing({ alert: a, resolution: a.still_present ? "false_positive" : "revoked", note: "" })} />
                  ) : (
                    <Button label="เปิดอีกครั้ง" size="small" text onClick={() => resolve(a, null)} />
                  )}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                พบที่ {a.location_label}{a.line ? ` บรรทัด ${a.line}` : ""} · ครั้งแรก {formatDateTime(a.first_seen_at)}
                {" "}({a.source === "save" ? "ตอนบันทึก" : a.source === "scheduled" ? "การตรวจตามรอบ" : "การตรวจที่ผู้ดูแลสั่ง"})
                {a.status === "resolved" && <> · ปิดโดย {a.resolved_by} {formatDateTime(a.resolved_at)}{a.resolution_note && `: ${a.resolution_note}`}</>}
              </p>
            </li>
          ))}
        </ul>
      )}

      <Dialog header="ปิดการแจ้งเตือน" visible={closing !== null} onHide={() => setClosing(null)} className="w-full max-w-lg" footer={
        closing && (
          <div className="flex justify-end gap-2">
            <Button label="ยกเลิก" text onClick={() => setClosing(null)} />
            <Button label="ปิดการแจ้งเตือน" icon="pi pi-check" onClick={() => resolve(closing.alert, closing.resolution, closing.note)} />
          </div>
        )
      }>
        {closing && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">{closing.alert.rule_label} <code>{closing.alert.preview}</code> ที่ {closing.alert.location_label}</p>
            <label className="block text-sm">
              เหตุผล
              <Dropdown value={closing.resolution} options={meta.alert_resolutions} optionLabel="label" optionValue="key"
                onChange={(e) => setClosing({ ...closing, resolution: e.value })} className="mt-1 flex w-full" />
            </label>
            {(closing.resolution === "false_positive" || closing.resolution === "used_in_tests") && (
              <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900">
                เหตุผลนี้จะทำให้ทุกคนเห็นข้อความนั้นอีกครั้ง เลือกเฉพาะเมื่อแน่ใจว่าไม่ใช่รหัสที่ใช้งานได้จริง
              </p>
            )}
            {closing.resolution === "moved_to_vault" && closing.alert.still_present && (
              <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900">ข้อความนี้ยังอยู่ในระบบ ลบออกจากข้อความก่อนปิด</p>
            )}
            <label className="block text-sm">
              หมายเหตุ
              <InputText value={closing.note} onChange={(e) => setClosing({ ...closing, note: e.target.value })} maxLength={500}
                className="mt-1 w-full" placeholder="เช่น เปลี่ยน token ใน GitLab แล้วเมื่อ 11 พ.ย." />
            </label>
          </div>
        )}
      </Dialog>
    </Card>
  );
}

/** The system's secret boxes and its leak alerts. Shown only to its people (and admins). */
export default function SecurityTab({ system, onChange }: { system: SystemDetail; onChange: () => void }) {
  return (
    <div className="space-y-4">
      <AlertsCard system={system} onChange={onChange} />
      <SecretBoxesCard system={system} />
    </div>
  );
}
