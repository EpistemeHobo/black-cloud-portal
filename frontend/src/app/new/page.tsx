"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "primereact/button";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { Message } from "primereact/message";
import { Card } from "@/components/bits";
import ImportSystem from "@/components/system/ImportSystem";
import { api } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { SystemDetail } from "@/lib/types";

export default function NewSystemPage() {
  const { meta, label, notify } = useSession();
  const router = useRouter();
  // Only question 1 of the guide; the rest is written on the system page.
  const [form, setForm] = useState({ name: "", type: "", description: "", if_down: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api<SystemDetail>("/api/systems", { method: "POST", body: form });
      notify("success", `ลงทะเบียน ${created.id} แล้ว`, "คุณเป็นเจ้าของฝั่งเทคนิคของระบบนี้");
      router.push(`/system/?id=${encodeURIComponent(created.id)}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <h1 className="page-title metal-ink">ลงทะเบียนระบบ</h1>
          <p className="mt-1 text-slate-600">
            แอป แพลตฟอร์ม เครื่องมือ SaaS ฐานข้อมูล ไปป์ไลน์ หรือสคริปต์ใดก็ได้ รวมถึงระบบที่ไม่ได้อยู่ใน Git
            กรอกแค่นี้ก่อนก็พอ คำถามที่เหลือในคู่มือรับช่วงต่อค่อยเขียนทีละข้อในหน้าระบบ คุณจะเป็นเจ้าของฝั่งเทคนิคของระบบนี้
          </p>
          <p className="mt-2 text-sm">
            <a href="#import" className="text-sky-700 hover:underline"><i className="pi pi-upload mr-1 text-xs" aria-hidden />มีโฟลเดอร์ที่ส่งออกไว้แล้ว? นำเข้าได้ด้านล่าง</a>
          </p>
        </div>

        <Card title="ข้อมูลหลัก">
          <div className="space-y-4">
            <label className="block">
              <span className="text-sm font-medium">ชื่อ *</span>
              <InputText value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required maxLength={200} className="mt-1 w-full" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">ประเภท *</span>
              <Dropdown value={form.type} options={choiceOptions(meta.system_types, label)} optionLabel="label" optionValue="value" onChange={(e) => setForm({ ...form, type: e.value })} placeholder="เลือกประเภท" className="mt-1 w-full" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">ระบบนี้ทำอะไร</span>
              <InputTextarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} autoResize className="mt-1 w-full" placeholder="เช่น ให้เจ้าหน้าที่แล็บจองเครื่อง sequencer และดูตารางการใช้งาน" />
            </label>
            <label className="block">
              <span className="text-sm font-medium">ถ้าระบบล่ม ใครเดือดร้อน และจะรู้ตัวเร็วแค่ไหน</span>
              <InputTextarea value={form.if_down} onChange={(e) => setForm({ ...form, if_down: e.target.value })} rows={2} autoResize className="mt-1 w-full" placeholder="เช่น เจ้าหน้าที่แล็บจองเครื่องไม่ได้ รู้ภายในหนึ่งชั่วโมง" />
            </label>
          </div>
        </Card>

        {error && <Message severity="error" text={error} className="w-full justify-start" />}
        <div className="flex justify-end gap-2">
          <Button type="button" label="ยกเลิก" text onClick={() => router.push("/systems/")} />
          <Button type="submit" label="ลงทะเบียน" icon="pi pi-check" loading={busy} disabled={!form.name.trim() || !form.type} />
        </div>
      </form>
      <div id="import" className="scroll-mt-24"><ImportSystem /></div>
    </div>
  );
}
