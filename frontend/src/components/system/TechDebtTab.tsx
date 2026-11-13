"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { Dialog } from "primereact/dialog";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { Tag } from "primereact/tag";
import { Card, DebtStatusTag, Empty, ExternalLink, RiskTag } from "@/components/bits";
import { api, formatDate } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { SystemDetail, TechDebt, TechDebtList } from "@/lib/types";

type Draft = Omit<TechDebt, "id" | "overdue" | "created_by" | "created_at" | "updated_at" | "closed_at">;

const EMPTY: Draft = {
  title: "", description: null, reason: null, impact: null, fix_plan: null, risk: "Medium",
  effort: null, target_date: null, issue_url: null, status: "open",
};

// The four questions of docs/technical_debt.md, in its order.
const QUESTIONS: { key: "description" | "reason" | "impact" | "fix_plan"; label: string; hint: string }[] = [
  { key: "description", label: "หนี้นี้คืออะไร", hint: "ทางลัดที่ใช้ หรือสิ่งที่ยังทำไม่ครบ" },
  { key: "reason", label: "ทำไมจึงเลือกทางนี้", hint: "เช่น ต้องเปิดใช้ให้ทันกำหนด" },
  { key: "impact", label: "ถ้าปล่อยไว้จะเกิดอะไร", hint: "ความเสี่ยงหรือต้นทุนที่เพิ่มขึ้นเรื่อย ๆ" },
  { key: "fix_plan", label: "จะแก้อย่างไร", hint: "ขั้นตอนคร่าว ๆ หนึ่งบรรทัดต่อหนึ่งขั้น" },
];

function DebtForm({ draft, setDraft }: { draft: Draft; setDraft: (d: Draft) => void }) {
  const { meta, label } = useSession();
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });
  return (
    <div className="space-y-3">
      <label className="block text-sm">
        ชื่อรายการ
        <InputText value={draft.title} onChange={(e) => set("title", e.target.value)} maxLength={200} required autoFocus
          className="mt-1 w-full" placeholder="เช่น ยังไม่มีการทดสอบอัตโนมัติของระบบออกใบแจ้งหนี้" />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          ความเสี่ยง
          <Dropdown value={draft.risk} options={choiceOptions(meta.debt_risks, label)} optionLabel="label" optionValue="value"
            onChange={(e) => set("risk", e.value)} className="mt-1 flex w-full" />
        </label>
        <label className="text-sm">
          สถานะ
          <Dropdown value={draft.status} options={meta.debt_statuses} optionLabel="label" optionValue="key"
            onChange={(e) => set("status", e.value)} className="mt-1 flex w-full" />
        </label>
        <label className="text-sm">
          แผนจะแก้ภายในวันที่
          <InputText type="date" value={draft.target_date ?? ""} onChange={(e) => set("target_date", e.target.value || null)} className="mt-1 w-full" />
        </label>
        <label className="text-sm">
          แรงที่ต้องใช้โดยประมาณ
          <InputText value={draft.effort ?? ""} onChange={(e) => set("effort", e.target.value || null)} maxLength={50}
            className="mt-1 w-full" placeholder="เช่น 3 วัน" />
        </label>
      </div>
      {QUESTIONS.map((q) => (
        <label key={q.key} className="block text-sm">
          {q.label}
          <InputTextarea value={draft[q.key] ?? ""} onChange={(e) => set(q.key, e.target.value || null)} rows={2} autoResize
            maxLength={5000} className="mt-1 w-full" placeholder={q.hint} />
        </label>
      ))}
      <label className="block text-sm">
        ลิงก์ issue
        <InputText value={draft.issue_url ?? ""} onChange={(e) => set("issue_url", e.target.value || null)} maxLength={1000}
          className="mt-1 w-full" placeholder="https://gitlab…/-/issues/123 (ติดป้าย technical-debt)" />
      </label>
    </div>
  );
}

function DebtItem({ d, canEdit, onEdit, onDelete }: { d: TechDebt; canEdit: boolean; onEdit: () => void; onDelete: () => void }) {
  const closed = d.status === "paid_off" || d.status === "wont_fix";
  return (
    <li className={`rounded-lg border p-4 ${closed ? "border-slate-200 bg-slate-50" : d.overdue ? "border-rose-200 bg-rose-50/40" : "border-slate-200 bg-white"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className={`font-medium ${closed ? "text-slate-500 line-through decoration-slate-300" : "text-slate-900"}`}>{d.title}</h3>
        <RiskTag risk={d.risk} />
        <DebtStatusTag status={d.status} />
        {d.overdue && <Tag value="เลยกำหนดแก้" severity="danger" icon="pi pi-clock" />}
        {canEdit && (
          <span className="ml-auto flex gap-1">
            <Button icon="pi pi-pencil" text rounded size="small" severity="secondary" aria-label="แก้ไข" onClick={onEdit} />
            <Button icon="pi pi-trash" text rounded size="small" severity="secondary" aria-label="ลบ" onClick={onDelete} />
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {d.target_date ? `แผนแก้ภายใน ${formatDate(d.target_date)}` : "ยังไม่ได้กำหนดวันแก้"}
        {d.effort && <> · ใช้แรงประมาณ {d.effort}</>}
        {d.created_by && <> · บันทึกโดย {d.created_by} เมื่อ {formatDate(d.created_at)}</>}
        {d.closed_at && <> · ปิดเมื่อ {formatDate(d.closed_at)}</>}
      </p>
      <dl className="mt-2 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {QUESTIONS.filter((q) => d[q.key]).map((q) => (
          <div key={q.key}>
            <dt className="text-xs font-medium text-slate-500">{q.label}</dt>
            <dd className="prose-plain text-slate-800">{d[q.key]}</dd>
          </div>
        ))}
      </dl>
      {d.issue_url && <p className="mt-2 text-sm"><ExternalLink href={d.issue_url}>issue</ExternalLink></p>}
    </li>
  );
}

/** A system's technical debt: shortcuts taken on purpose, and when they'll be paid off. */
export default function TechDebtTab({ system, onCount }: { system: SystemDetail; onCount?: () => void }) {
  const { notify } = useSession();
  const [data, setData] = useState<TechDebtList | null>(null);
  const [editing, setEditing] = useState<{ id: number | null; draft: Draft } | null>(null);
  const [showClosed, setShowClosed] = useState(false);
  const [busy, setBusy] = useState(false);
  const base = `/api/systems/${encodeURIComponent(system.id)}/tech-debt`;

  const load = useCallback(() => {
    api<TechDebtList>(base).then(setData).catch((e) => notify("error", "โหลดหนี้ทางเทคนิคไม่สำเร็จ", e.message));
  }, [base, notify]);
  useEffect(load, [load]);

  async function save() {
    if (!editing) return;
    setBusy(true);
    try {
      const url = editing.id ? `${base}/${editing.id}` : base;
      setData(await api<TechDebtList>(url, { method: editing.id ? "PUT" : "POST", body: editing.draft }));
      setEditing(null);
      notify("success", "บันทึกหนี้ทางเทคนิคแล้ว");
      onCount?.();
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(d: TechDebt) {
    if (!window.confirm(`ลบ "${d.title}" หรือไม่? ถ้าแก้แล้ว ให้เปลี่ยนสถานะเป็น "แก้แล้ว" แทน เพื่อเก็บไว้เป็นประวัติ`)) return;
    try {
      setData(await api<TechDebtList>(`${base}/${d.id}`, { method: "DELETE" }));
      onCount?.();
    } catch (e) {
      notify("error", "ลบไม่สำเร็จ", (e as Error).message);
    }
  }

  const items = data?.items ?? [];
  const open = items.filter((d) => d.status === "open" || d.status === "in_progress");
  const closed = items.filter((d) => !open.includes(d));
  const s = data?.summary;

  return (
    <Card
      title="หนี้ทางเทคนิค"
      actions={data?.can_edit && (
        <Button label="เพิ่มรายการ" icon="pi pi-plus" size="small" outlined onClick={() => setEditing({ id: null, draft: EMPTY })} />
      )}
    >
      <p className="-mt-1 mb-3 text-sm text-slate-600">
        ทางลัดที่ทีมเลือกใช้โดยตั้งใจและวางแผนจะแก้ เช่น ข้ามการทดสอบเพื่อให้ทันกำหนด บันทึกไว้ที่นี่ให้คนรับช่วงต่อและหัวหน้าเห็นความเสี่ยงและวางแผนได้
        {s && s.open > 0 && (
          <span className="ml-1 font-medium text-slate-800">
            ค้างอยู่ {s.open} รายการ{s.high_open > 0 && ` · ความเสี่ยงสูง ${s.high_open}`}{s.overdue > 0 && ` · เลยกำหนด ${s.overdue}`}
          </span>
        )}
      </p>
      {data === null ? <Empty>กำลังโหลด…</Empty> : open.length === 0 ? (
        <Empty>ไม่มีหนี้ทางเทคนิคที่ค้างอยู่</Empty>
      ) : (
        <ul className="space-y-3">
          {open.map((d) => (
            <DebtItem key={d.id} d={d} canEdit={data.can_edit} onDelete={() => remove(d)}
              onEdit={() => setEditing({ id: d.id, draft: { ...d } })} />
          ))}
        </ul>
      )}
      {closed.length > 0 && (
        <div className="mt-4">
          <Button text size="small" icon={showClosed ? "pi pi-chevron-up" : "pi pi-chevron-down"}
            label={`${showClosed ? "ซ่อน" : "แสดง"}รายการที่ปิดแล้ว (${closed.length})`} onClick={() => setShowClosed(!showClosed)} />
          {showClosed && (
            <ul className="mt-2 space-y-3">
              {closed.map((d) => (
                <DebtItem key={d.id} d={d} canEdit={data?.can_edit ?? false} onDelete={() => remove(d)}
                  onEdit={() => setEditing({ id: d.id, draft: { ...d } })} />
              ))}
            </ul>
          )}
        </div>
      )}

      <Dialog header={editing?.id ? "แก้ไขหนี้ทางเทคนิค" : "เพิ่มหนี้ทางเทคนิค"} visible={editing !== null} onHide={() => setEditing(null)}
        className="w-full max-w-2xl" footer={
          <div className="flex justify-end gap-2">
            <Button label="ยกเลิก" text onClick={() => setEditing(null)} />
            <Button label="บันทึก" icon="pi pi-check" loading={busy} disabled={!editing?.draft.title.trim()} onClick={save} />
          </div>
        }>
        {editing && <DebtForm draft={editing.draft} setDraft={(draft) => setEditing({ ...editing, draft })} />}
      </Dialog>
    </Card>
  );
}
