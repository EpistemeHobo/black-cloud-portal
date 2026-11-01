"use client";

import { useState } from "react";
import { Button } from "primereact/button";
import { Dropdown } from "primereact/dropdown";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SystemDetail } from "@/lib/types";

export default function StepTracker({ system, onChange }: { system: SystemDetail; onChange: (s: SystemDetail) => void }) {
  const { meta, notify } = useSession();
  const [editing, setEditing] = useState(false);

  async function move(step: number) {
    try {
      const updated = await api<SystemDetail>(`/api/systems/${encodeURIComponent(system.id)}/step`, { method: "PUT", body: { step } });
      onChange(updated);
      setEditing(false);
      notify("success", `ย้ายไปขั้นตอน ${step} แล้ว`);
    } catch (e) {
      notify("error", "เปลี่ยนขั้นตอนไม่สำเร็จ", (e as Error).message);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <ol className="grid grid-cols-7 gap-1" aria-label="ขั้นตอนการพัฒนา">
        {meta.steps.map((s) => {
          const state = s.number < system.step ? "past" : s.number === system.step ? "current" : "future";
          return (
            <li key={s.number} className="flex flex-col items-center text-center" aria-current={state === "current" ? "step" : undefined}>
              <div className="flex w-full items-center">
                <div className={`h-0.5 flex-1 ${s.number === 1 ? "invisible" : state === "future" ? "bg-slate-200" : "bg-sky-600"}`} />
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                    state === "current" ? "bg-sky-700 text-white ring-4 ring-sky-100" :
                    state === "past" ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-400"
                  }`}
                >
                  {state === "past" ? <i className="pi pi-check text-xs" aria-label="เสร็จแล้ว" /> : s.number}
                </span>
                <div className={`h-0.5 flex-1 ${s.number === 7 ? "invisible" : s.number < system.step ? "bg-sky-600" : "bg-slate-200"}`} />
              </div>
              <span className={`mt-1.5 text-xs leading-tight ${state === "current" ? "font-semibold text-sky-900" : state === "past" ? "text-slate-600" : "text-slate-400"}`}>
                {s.name}
              </span>
            </li>
          );
        })}
      </ol>
      {system.can_edit && (
        <div className="mt-3 flex items-center justify-end gap-2 border-t border-slate-100 pt-3">
          {editing ? (
            <>
              <Dropdown
                value={system.step}
                options={meta.steps.map((s) => ({ label: `${s.number}. ${s.name}`, value: s.number }))}
                onChange={(e) => move(e.value)}
                className="w-64"
                aria-label="ย้ายไปขั้นตอน"
              />
              <Button label="ยกเลิก" text size="small" onClick={() => setEditing(false)} />
            </>
          ) : (
            <Button label="เปลี่ยนขั้นตอน" icon="pi pi-arrow-right-arrow-left" size="small" outlined onClick={() => setEditing(true)} />
          )}
        </div>
      )}
    </div>
  );
}
