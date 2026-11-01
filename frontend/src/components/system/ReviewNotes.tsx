"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { Card, Empty, StepTag } from "@/components/bits";
import { api, formatDate } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { ReviewNote, SystemDetail } from "@/lib/types";

const today = () => new Date().toISOString().slice(0, 10);

export default function ReviewNotes({ system }: { system: SystemDetail }) {
  const { meta, label, notify } = useSession();
  const [notes, setNotes] = useState<ReviewNote[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ review_date: today(), place: "Team meeting", note: "" });
  const base = `/api/systems/${encodeURIComponent(system.id)}/reviews`;

  const load = useCallback(() => {
    api<ReviewNote[]>(base).then(setNotes).catch((e) => notify("error", "โหลดบันทึกการทบทวนไม่สำเร็จ", e.message));
  }, [base, notify]);
  useEffect(load, [load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      setNotes(await api<ReviewNote[]>(base, { method: "POST", body: form }));
      setForm({ review_date: today(), place: "Team meeting", note: "" });
      setAdding(false);
      notify("success", "เพิ่มบันทึกการทบทวนแล้ว");
    } catch (err) {
      notify("error", "เพิ่มบันทึกไม่สำเร็จ", (err as Error).message);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("ลบบันทึกการทบทวนนี้หรือไม่?")) return;
    try {
      setNotes(await api<ReviewNote[]>(`${base}/${id}`, { method: "DELETE" }));
    } catch (err) {
      notify("error", "ลบบันทึกไม่สำเร็จ", (err as Error).message);
    }
  }

  const stepName = (n: number) => meta.steps.find((s) => s.number === n)?.name;

  return (
    <Card
      title="บันทึกการทบทวน"
      actions={!adding && <Button label="เพิ่มบันทึกการทบทวน" icon="pi pi-plus" size="small" outlined onClick={() => setAdding(true)} />}
    >
      <p className="-mt-1 mb-3 text-xs text-slate-500">
        ความเห็นของหัวหน้าและเพื่อนร่วมงานหลังทบทวนระบบนี้ ทั้งในที่ประชุมหรือจากการอ่านหน้านี้
      </p>
      {adding && (
        <form onSubmit={save} className="mb-4 space-y-3 rounded-md bg-slate-50 p-3">
          <div className="flex flex-wrap gap-3">
            <label className="text-sm">
              วันที่
              <InputText type="date" value={form.review_date} max={today()} onChange={(e) => setForm({ ...form, review_date: e.target.value })} required className="mt-1 block" />
            </label>
            <label className="text-sm">
              ที่ไหน
              <Dropdown value={form.place} options={choiceOptions(meta.review_places, label)} optionLabel="label" optionValue="value" onChange={(e) => setForm({ ...form, place: e.value })} className="mt-1 flex w-48" />
            </label>
          </div>
          <label className="block text-sm">
            บันทึก
            <InputTextarea value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} rows={3} autoResize required maxLength={5000}
              className="mt-1 w-full" placeholder="สิ่งที่ตกลงกัน สิ่งที่ต้องตรวจสอบ และสิ่งที่ต้องเปลี่ยนแปลง" />
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" label="ยกเลิก" text size="small" onClick={() => setAdding(false)} />
            <Button type="submit" label="บันทึก" size="small" disabled={!form.note.trim()} />
          </div>
        </form>
      )}
      {notes === null ? <Empty>กำลังโหลด…</Empty> : notes.length === 0 ? (
        <Empty>ยังไม่มีบันทึกการทบทวน</Empty>
      ) : (
        <ol className="space-y-3">
          {notes.map((n) => (
            <li key={n.id} className="border-l-2 border-sky-200 pl-3">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                <span className="font-medium text-slate-700">{n.reviewer.name}</span>
                <span>{formatDate(n.review_date)}</span>
                <span>· {label(n.place)}</span>
                <StepTag step={n.step} name={stepName(n.step)} />
                {n.can_delete && (
                  <Button icon="pi pi-trash" text rounded size="small" severity="secondary" aria-label="ลบบันทึก" className="!h-6 !w-6" onClick={() => remove(n.id)} />
                )}
              </div>
              <p className="prose-plain mt-1 text-sm text-slate-800">{n.note}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
