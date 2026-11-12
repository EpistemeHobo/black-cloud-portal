"use client";

import { useEffect, useState } from "react";
import { Column } from "primereact/column";
import { DataTable } from "primereact/datatable";
import { api, formatDateTime } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { HistoryRow, SystemDetail } from "@/lib/types";

export default function HistoryTab({ system }: { system: SystemDetail }) {
  const { meta, label, notify } = useSession();
  const [rows, setRows] = useState<HistoryRow[] | null>(null);

  useEffect(() => {
    api<HistoryRow[]>(`/api/systems/${encodeURIComponent(system.id)}/history`)
      .then(setRows)
      .catch((e) => notify("error", "โหลดประวัติการแก้ไขไม่สำเร็จ", e.message));
  }, [system, notify]);

  const fieldLabels: Record<string, string> = Object.fromEntries(
    meta.sections.flatMap((s) => s.fields.map((f) => [f.key, f.label])),
  );
  // History stores field and action names in English; show them in Thai.
  const coreFields: Record<string, string> = {
    name: "ชื่อ", type: "ประเภท", step: "ขั้นตอน", lifecycle_state: "สถานะวงจรชีวิต",
    owning_unit_id: "หน่วยงาน", verified_at: "ยืนยันข้อมูลเป็นปัจจุบัน", verified_by_id: "ผู้ยืนยันข้อมูล",
    status: "สถานะ", evidence: "หลักฐาน",
    description: "ระบบนี้ทำอะไร", if_down: "ถ้าระบบล่ม", run_steps: "ขั้นตอนรันบนเครื่องตัวเอง",
    deploy_steps: "ขั้นตอนติดตั้ง", rollback_steps: "ขั้นตอนย้อนกลับ", guide_nothing: "คำถามที่ไม่มีรายการ",
    text: "ข้อความ", kind: "ประเภท", how_often: "ความถี่", next_due: "ครั้งถัดไป", promised_to: "สัญญากับ",
    due_date: "ภายในวันที่", done_at: "ทำเสร็จ", reachable_until: "ติดต่อได้ถึง", note: "หมายเหตุ",
    title: "ชื่อรายการ", reason: "เหตุผลที่เลือก", impact: "ผลถ้าปล่อยไว้", fix_plan: "วิธีแก้", risk: "ความเสี่ยง",
    effort: "แรงที่ต้องใช้", target_date: "กำหนดแก้", issue_url: "ลิงก์ issue",
  };
  // Secret box and leak alert events: a box's name, never what is in it.
  const secretActions: Record<string, string> = {
    box_created: "สร้างกล่องรหัสลับ", box_version_added: "บันทึกกล่องรหัสลับ", box_key_changed: "เปลี่ยนกุญแจกล่องรหัสลับ",
    box_renamed: "เปลี่ยนชื่อกล่องรหัสลับ", box_opened: "เปิดกล่องรหัสลับ", box_deleted: "ลบกล่องรหัสลับ",
    alert_resolved: "ปิดการแจ้งเตือนรหัสลับรั่วไหล", alert_reopened: "เปิดการแจ้งเตือนรหัสลับอีกครั้ง",
  };
  const actions: Record<string, string> = { added: "เพิ่ม", removed: "ลบ", replaced: "แทนที่" };
  const fieldName = (f: string) => fieldLabels[f] ?? coreFields[f] ?? f.replaceAll("_", " ");
  const what = (r: HistoryRow) => {
    if (r.entity === "system") return r.field === "created" ? "ลงทะเบียนระบบ" : fieldName(r.field);
    if (r.entity === "checklist") return `รายการตรวจสอบ ${r.entity_id}: ${fieldName(r.field)}`;
    if (r.entity === "secret") return `${secretActions[r.field] ?? r.field}${r.entity_id ? ` ${r.entity_id}` : ""}`;
    const entity: Record<string, string> = {
      role: "บทบาท", link: "ลิงก์", dependency: "ระบบที่พึ่งพา", review: "บันทึกการทบทวน",
      watch_out: "ข้อควรระวัง/งานประจำ", open_item: "งานค้าง", guide_doc: "ไฟล์แนบ .md", tech_debt: "หนี้ทางเทคนิค",
    };
    if (!actions[r.field]) return `${entity[r.entity] ?? r.entity}: ${fieldName(r.field)}`;
    return `${actions[r.field] ?? fieldName(r.field)}${entity[r.entity] ?? r.entity}`;
  };
  const value = (v: string | null, hidden: boolean) =>
    hidden ? <span className="italic text-slate-400">ข้อมูลลับ</span> : <span className="prose-plain">{v === null ? "—" : label(v)}</span>;

  return (
    <DataTable value={rows ?? []} loading={rows === null} size="small" stripedRows paginator rows={25}
      className="overflow-hidden rounded-lg border border-slate-200" emptyMessage="ยังไม่มีการบันทึกการเปลี่ยนแปลง">
      <Column header="เมื่อ" body={(r: HistoryRow) => formatDateTime(r.changed_at)} className="whitespace-nowrap" />
      <Column header="ผู้แก้ไข" field="changed_by" />
      <Column header="รายการ" body={what} />
      <Column header="ก่อน" body={(r: HistoryRow) => value(r.old_value, r.hidden)} className="max-w-xs text-slate-500" />
      <Column header="หลัง" body={(r: HistoryRow) => value(r.new_value, r.hidden)} className="max-w-xs" />
    </DataTable>
  );
}
