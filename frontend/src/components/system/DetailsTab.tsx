"use client";

import { useState } from "react";
import { Button } from "primereact/button";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { MultiSelect } from "primereact/multiselect";
import { Card } from "@/components/bits";
import { api, formatDate } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { FieldSpec, SystemDetail } from "@/lib/types";

type Value = string | string[] | number | null;

function show(spec: FieldSpec, value: Value, label: (v: string) => string) {
  if (value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) {
    return <span className="italic text-slate-400">ยังไม่ได้กรอก</span>;
  }
  if (Array.isArray(value)) return value.map(label).join(", ");
  if (spec.type === "date") return formatDate(String(value));
  if (spec.type === "choice") return label(String(value));
  return <span className="prose-plain">{String(value)}</span>;
}

function Input({ spec, value, onChange }: { spec: FieldSpec; value: Value; onChange: (v: Value) => void }) {
  const { label } = useSession();
  const id = `field-${spec.key}`;
  switch (spec.type) {
    case "paragraph":
      return <InputTextarea id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} rows={2} autoResize className="w-full" />;
    case "choice":
      return <Dropdown inputId={id} value={value} options={choiceOptions(spec.choices, label)} optionLabel="label" optionValue="value" onChange={(e) => onChange(e.value ?? null)} showClear placeholder="เลือก" className="w-full" />;
    case "multi":
      return <MultiSelect inputId={id} value={(value as string[]) ?? []} options={choiceOptions(spec.choices, label)} optionLabel="label" optionValue="value" onChange={(e) => onChange(e.value)} display="chip" placeholder="เลือกได้หลายรายการ" className="w-full" />;
    case "date":
      return <InputText id={id} type="date" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || null)} className="w-full" />;
    default:
      return <InputText id={id} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} className="w-full" />;
  }
}

export default function DetailsTab({ system, onChange }: { system: SystemDetail; onChange: (s: SystemDetail) => void }) {
  const { meta, label, notify } = useSession();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, Value>>({});
  const [core, setCore] = useState({ name: system.name, type: system.type, lifecycle_state: system.lifecycle_state });
  const [busy, setBusy] = useState(false);

  function start() {
    setDraft({ ...system.fields });
    setCore({ name: system.name, type: system.type, lifecycle_state: system.lifecycle_state });
    setEditing(true);
  }

  async function save() {
    const changed: Record<string, Value> = {};
    for (const [k, v] of Object.entries(draft)) {
      if (JSON.stringify(v ?? null) !== JSON.stringify(system.fields[k] ?? null)) changed[k] = v;
    }
    for (const [k, v] of Object.entries(core)) {
      if (v !== system[k as keyof typeof core]) changed[k] = v;
    }
    if (Object.keys(changed).length === 0) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      onChange(await api<SystemDetail>(`/api/systems/${encodeURIComponent(system.id)}`, { method: "PATCH", body: changed }));
      setEditing(false);
      notify("success", "บันทึกข้อมูลแค็ตตาล็อกแล้ว");
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const actions = system.can_edit_catalog ? (
    editing ? (
      <>
        <Button label="ยกเลิก" text size="small" onClick={() => setEditing(false)} />
        <Button label="บันทึก" icon="pi pi-check" size="small" loading={busy} onClick={save} />
      </>
    ) : (
      <Button label="แก้ไขข้อมูลแค็ตตาล็อก" icon="pi pi-pencil" size="small" outlined onClick={start} />
    )
  ) : null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        <i className="pi pi-info-circle mr-1" />ข้อมูลสำหรับการตรวจสอบและทะเบียนระบบ เจ้าหน้าที่ตรวจสอบหรือทีมไอทีเป็นผู้กรอก นักพัฒนาไม่จำเป็นต้องกรอก
      </p>
      {system.hidden_fields.length > 0 && (
        <p className="text-sm text-slate-500">
          <i className="pi pi-lock mr-1" />ข้อมูลลับบางส่วนจะแสดงเฉพาะเจ้าของและนักพัฒนาของระบบนี้เท่านั้น
        </p>
      )}
      <Card title="ข้อมูลพื้นฐาน" actions={actions}>
        {editing ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="text-sm">ชื่อ
              <InputText value={core.name} onChange={(e) => setCore({ ...core, name: e.target.value })} className="mt-1 w-full" />
            </label>
            <label className="text-sm">ประเภท
              <Dropdown value={core.type} options={choiceOptions(meta.system_types, label)} optionLabel="label" optionValue="value" onChange={(e) => setCore({ ...core, type: e.value })} className="mt-1 w-full" />
            </label>
            <label className="text-sm">สถานะวงจรชีวิต
              <Dropdown value={core.lifecycle_state} options={choiceOptions(meta.lifecycle_states, label)} optionLabel="label" optionValue="value" onChange={(e) => setCore({ ...core, lifecycle_state: e.value })} className="mt-1 w-full" />
            </label>
          </div>
        ) : (
          <dl className="grid gap-4 text-sm sm:grid-cols-3">
            <div><dt className="text-slate-500">ชื่อ</dt><dd>{system.name}</dd></div>
            <div><dt className="text-slate-500">ประเภท</dt><dd>{label(system.type)}</dd></div>
            <div><dt className="text-slate-500">สถานะวงจรชีวิต</dt><dd>{label(system.lifecycle_state)}</dd></div>
          </dl>
        )}
      </Card>
      {meta.sections.map((section) => {
        const fields = section.fields.filter((f) => !system.hidden_fields.includes(f.key));
        return (
          <Card key={section.key} title={section.title}>
            <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              {fields.map((spec) => (
                <div key={spec.key} className={spec.type === "paragraph" ? "sm:col-span-2" : ""}>
                  <dt className="text-sm text-slate-500">
                    <label htmlFor={`field-${spec.key}`}>{spec.label}</label>
                    {spec.restricted && <i className="pi pi-lock ml-1 text-[10px]" title="ข้อมูลลับ" />}
                  </dt>
                  <dd className="mt-1 text-sm">
                    {editing ? <Input spec={spec} value={draft[spec.key] ?? null} onChange={(v) => setDraft({ ...draft, [spec.key]: v })} /> : show(spec, system.fields[spec.key], label)}
                  </dd>
                  {editing && spec.help && <p className="mt-1 text-xs text-slate-500">{spec.help}</p>}
                </div>
              ))}
            </dl>
          </Card>
        );
      })}
      {editing && (
        <div className="sticky bottom-4 flex justify-end gap-2 rounded-lg border border-slate-200 bg-white/95 p-3 shadow">
          <Button label="ยกเลิก" text onClick={() => setEditing(false)} />
          <Button label="บันทึกข้อมูลแค็ตตาล็อก" icon="pi pi-check" loading={busy} onClick={save} />
        </div>
      )}
    </div>
  );
}
