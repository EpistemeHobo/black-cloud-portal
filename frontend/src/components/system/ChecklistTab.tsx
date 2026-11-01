"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { Empty, ExternalLink } from "@/components/bits";
import { api, formatDate } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Checklist, ChecklistRow, SystemDetail } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  done: "bg-emerald-100 text-emerald-800",
  not_applicable: "bg-slate-100 text-slate-600",
  partly: "bg-amber-100 text-amber-800",
  missing: "bg-rose-100 text-rose-800",
};

function Item({ row, system, onSaved }: { row: ChecklistRow; system: SystemDetail; onSaved: (c: Checklist) => void }) {
  const { meta, label: choiceLabel, notify } = useSession();
  const [status, setStatus] = useState(row.status);
  const [evidence, setEvidence] = useState(row.evidence ?? "");
  const dirty = status !== row.status || evidence !== (row.evidence ?? "");
  const label = meta.checklist_statuses.find((s) => s.key === row.status)?.label ?? row.status;
  const editable = system.can_edit && !row.auto;

  async function save() {
    try {
      onSaved(await api<Checklist>(
        `/api/systems/${encodeURIComponent(system.id)}/checklist/${row.code}`,
        { method: "PUT", body: { status, evidence } },
      ));
      notify("success", `บันทึก ${row.code} แล้ว`);
    } catch (e) {
      notify("error", `บันทึก ${row.code} ไม่สำเร็จ`, (e as Error).message);
    }
  }

  return (
    <li className={`flex flex-col gap-2 py-3 md:flex-row md:items-start ${row.due ? "" : "opacity-55"}`}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-slate-500">{row.code}</span>
          <span className="font-medium text-slate-900">{row.title}</span>
          {row.level === "recommended" && <span className="rounded bg-slate-100 px-1.5 text-xs text-slate-600">{choiceLabel("recommended")}</span>}
        </div>
        <p className="mt-0.5 text-xs text-slate-600">
          {row.how_to_verify}
          {row.kb_url && <> · <ExternalLink href={row.kb_url}>วิธีดำเนินการ</ExternalLink></>}
        </p>
        {!editable && row.evidence && <p className="prose-plain mt-1 text-xs text-slate-700">หลักฐาน: {row.evidence}</p>}
        {row.updated_by && (
          <p className="mt-0.5 text-[11px] text-slate-400">อัปเดตล่าสุดโดย {row.updated_by} เมื่อ {formatDate(row.updated_at)}</p>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 md:w-[26rem] md:justify-end">
        {!row.due && <span className="text-xs text-slate-500">เริ่มที่ขั้นตอน {row.from_step}</span>}
        {row.auto && <span className="text-xs text-slate-500" title="พอร์ทัลตรวจสอบรายการนี้ให้เอง">อัตโนมัติ</span>}
        {editable ? (
          <>
            <Dropdown
              value={status}
              options={meta.checklist_statuses}
              optionLabel="label"
              optionValue="key"
              onChange={(e) => setStatus(e.value)}
              className="w-36"
              aria-label={`สถานะของ ${row.code}`}
            />
            <InputText value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="หลักฐานหรือลิงก์" className="w-40 flex-1" aria-label={`หลักฐานของ ${row.code}`} />
            <Button icon="pi pi-check" size="small" aria-label={`บันทึก ${row.code}`} disabled={!dirty} onClick={save} />
          </>
        ) : (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLE[row.status] ?? ""}`}>{label}</span>
        )}
      </div>
    </li>
  );
}

export default function ChecklistTab({ system, onProgress }: { system: SystemDetail; onProgress: () => void }) {
  const { meta, notify } = useSession();
  const [checklist, setChecklist] = useState<Checklist | null>(null);

  const load = useCallback(() => {
    api<Checklist>(`/api/systems/${encodeURIComponent(system.id)}/checklist`)
      .then(setChecklist)
      .catch((e) => notify("error", "โหลดรายการตรวจสอบไม่สำเร็จ", e.message));
  }, [system.id, notify]);
  useEffect(load, [load, system.step, system.links, system.roles]);

  if (!checklist) return <Empty>กำลังโหลด…</Empty>;

  const saved = (c: Checklist) => {
    setChecklist(c);
    onProgress();
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        สิ่งที่แต่ละขั้นตอนต้องมีตามมาตรฐานของ Cloud รายการของขั้นตอนถัดไปแสดงไว้ด้วยเพื่อให้วางแผนล่วงหน้าได้
        รายการเหล่านี้ไม่ได้ห้ามการย้ายระบบไปยังขั้นตอนอื่น
      </p>
      {meta.steps.map((step) => {
        const rows = checklist.items.filter((i) => i.from_step === step.number);
        if (rows.length === 0) return null;
        return (
          <section key={step.number} className="rounded-lg border border-slate-200 bg-white px-5 py-3">
            <h3 className="flex items-center gap-2 border-b border-slate-100 pb-2 font-semibold text-slate-900">
              ตั้งแต่ขั้นตอน {step.number}: {step.name}
              {step.number === system.step && <span className="rounded bg-sky-100 px-1.5 text-xs font-medium text-sky-800">ขั้นตอนปัจจุบัน</span>}
            </h3>
            <ul className="divide-y divide-slate-100">
              {rows.map((row) => (
                <Item key={`${row.code}-${row.status}-${row.evidence}`} row={row} system={system} onSaved={saved} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
