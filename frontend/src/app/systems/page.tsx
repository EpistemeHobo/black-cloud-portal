"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Button } from "primereact/button";
import { Column } from "primereact/column";
import { DataTable } from "primereact/datatable";
import { Dropdown } from "primereact/dropdown";
import { IconField } from "primereact/iconfield";
import { InputIcon } from "primereact/inputicon";
import { InputText } from "primereact/inputtext";
import { Checkbox } from "primereact/checkbox";
import { LifecycleTag, StepTag } from "@/components/bits";
import { GuideProgress } from "@/components/guide/HandoverGuide";
import { api, formatDate } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { SystemSummary } from "@/lib/types";

export default function CatalogPage() {
  const { meta, label, notify } = useSession();
  const [systems, setSystems] = useState<SystemSummary[] | null>(null);
  const [search, setSearch] = useState("");
  const [type, setType] = useState<string | null>(null);
  const [step, setStep] = useState<number | null>(null);
  const [unit, setUnit] = useState<string | null>(null);
  const [showRetired, setShowRetired] = useState(false);

  useEffect(() => {
    api<SystemSummary[]>("/api/systems").then(setSystems).catch((e) => notify("error", "โหลดรายการระบบไม่สำเร็จ", e.message));
  }, [notify]);

  const units = useMemo(
    () => Array.from(new Set((systems ?? []).map((s) => s.unit).filter(Boolean))).sort() as string[],
    [systems],
  );
  const stepName = (n: number) => meta.steps.find((s) => s.number === n)?.name ?? "";

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (systems ?? []).filter((s) =>
      (showRetired || s.lifecycle_state !== "Retired") &&
      (!type || s.type === type) &&
      (!step || s.step === step) &&
      (!unit || s.unit === unit) &&
      (!q || [s.id, s.name, s.description, s.unit, ...s.technical_owners].some((v) => v?.toLowerCase().includes(q))),
    );
  }, [systems, search, type, step, unit, showRetired]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="page-title metal-ink">ระบบทั้งหมด</h1>
          <p className="text-slate-600">
            {systems ? `แสดง ${visible.length} จาก ${systems.length} ระบบ` : "กำลังโหลด…"}
          </p>
        </div>
        <Link href="/new/" className="ml-auto">
          <Button label="ลงทะเบียนระบบ" icon="pi pi-plus" />
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <IconField iconPosition="left" className="min-w-64 flex-1">
          <InputIcon className="pi pi-search" />
          <InputText value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ค้นหาชื่อ, ID, เจ้าของ…" className="w-full" />
        </IconField>
        <Dropdown value={type} options={choiceOptions(meta.system_types, label)} optionLabel="label" optionValue="value" onChange={(e) => setType(e.value)} placeholder="ทุกประเภท" showClear />
        <Dropdown
          value={step}
          options={meta.steps.map((s) => ({ label: `${s.number}. ${s.name}`, value: s.number }))}
          onChange={(e) => setStep(e.value)}
          placeholder="ทุกขั้นตอน"
          showClear
        />
        <Dropdown value={unit} options={units} onChange={(e) => setUnit(e.value)} placeholder="ทุกหน่วยงาน" showClear disabled={units.length === 0} />
        <label className="flex items-center gap-2 px-2 text-sm text-slate-600">
          <Checkbox checked={showRetired} onChange={(e) => setShowRetired(!!e.checked)} />
          แสดงระบบที่เลิกใช้แล้ว
        </label>
      </div>

      <DataTable
        value={visible}
        loading={systems === null}
        dataKey="id"
        sortField="name"
        sortOrder={1}
        removableSort
        size="small"
        stripedRows
        className="overflow-hidden rounded-lg border border-slate-200"
        emptyMessage={systems?.length ? "ไม่มีระบบที่ตรงกับตัวกรองนี้" : "ยังไม่มีระบบ ลงทะเบียนระบบแรกได้เลย"}
      >
        <Column field="id" header="ID" sortable className="whitespace-nowrap text-slate-500" />
        <Column
          field="name"
          header="ระบบ"
          sortable
          body={(s: SystemSummary) => (
            <div>
              <Link href={`/system/?id=${encodeURIComponent(s.id)}`} className="font-medium text-sky-800 hover:underline">
                {s.name}
              </Link>{" "}
              <LifecycleTag state={s.lifecycle_state} />
              {s.description && <div className="line-clamp-1 text-xs text-slate-500">{s.description}</div>}
            </div>
          )}
        />
        <Column field="type" header="ประเภท" sortable body={(s: SystemSummary) => label(s.type)} />
        <Column field="step" header="ขั้นตอน" sortable body={(s: SystemSummary) => <StepTag step={s.step} name={stepName(s.step)} />} />
        <Column header="เจ้าของฝั่งเทคนิค" body={(s: SystemSummary) => s.technical_owners.join(", ")} />
        <Column field="unit" header="หน่วยงาน" sortable />
        <Column field="criticality" header="ความสำคัญ" sortable body={(s: SystemSummary) => (s.criticality ? label(s.criticality) : "")} />
        <Column header="คู่มือรับช่วงต่อ" sortable sortField="guide.answered" field="guide.answered"
          body={(s: SystemSummary) => <GuideProgress answered={s.guide.answered} total={s.guide.total} />} />
        <Column field="updated_at" header="อัปเดตล่าสุด" sortable body={(s: SystemSummary) => formatDate(s.updated_at)} className="whitespace-nowrap" />
      </DataTable>
    </div>
  );
}
