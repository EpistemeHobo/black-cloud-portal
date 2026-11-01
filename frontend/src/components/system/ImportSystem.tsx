"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "primereact/button";
import { Message } from "primereact/message";
import { Card } from "@/components/bits";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { readFolder, readZip, toPayload, type ParsedFolder } from "@/lib/systemFolder";
import type { SystemDetail } from "@/lib/types";

/** Register a new system from a folder made by "Export" (picked as a folder, or zipped). */
export default function ImportSystem() {
  const { label, notify } = useSession();
  const router = useRouter();
  const zipInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [parsed, setParsed] = useState<ParsedFolder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load(read: () => Promise<Map<string, string>>) {
    setError(null);
    setParsed(null);
    try {
      setParsed(toPayload(await read()));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function submit() {
    if (!parsed) return;
    setBusy(true);
    try {
      const created = await api<SystemDetail>("/api/systems/import", { method: "POST", body: parsed.payload });
      notify("success", `นำเข้าเป็น ${created.id} แล้ว`, "คุณเป็นเจ้าของฝั่งเทคนิคของระบบนี้");
      router.push(`/system/?id=${encodeURIComponent(created.id)}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const d = parsed?.payload.data;
  const count = (list: unknown[] | undefined) => list?.length ?? 0;

  return (
    <Card title="นำเข้าจากโฟลเดอร์ที่ส่งออกไว้">
      <div
        onDragOver={(e) => { if (e.dataTransfer.types.includes("Files")) { e.preventDefault(); setDragging(true); } }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) load(() => readZip(file));
        }}
        className={`rounded-lg border border-dashed px-4 py-4 text-center ${dragging ? "border-sky-400 bg-sky-50" : "border-slate-300 bg-slate-50"}`}
      >
        <p className="text-sm text-slate-600">
          ใช้โฟลเดอร์ที่ได้จากปุ่ม &quot;ส่งออก&quot; ในหน้าระบบ จะได้ระบบใหม่พร้อมข้อมูลและไฟล์ .md ทั้งหมด
        </p>
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          <Button type="button" label="เลือกไฟล์ .zip" icon="pi pi-file" size="small" outlined onClick={() => zipInput.current?.click()} />
          <Button type="button" label="เลือกโฟลเดอร์" icon="pi pi-folder-open" size="small" outlined onClick={() => folderInput.current?.click()} />
        </div>
        <p className="mt-2 text-xs text-slate-400">หรือลากไฟล์ .zip มาวางที่นี่</p>
        <input ref={zipInput} type="file" accept=".zip,application/zip" hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) load(() => readZip(f)); e.target.value = ""; }} />
        <input ref={folderInput} type="file" hidden multiple
          {...{ webkitdirectory: "", directory: "" }}
          onChange={(e) => { const fs = e.target.files; if (fs?.length) load(() => readFolder(fs)); e.target.value = ""; }} />
      </div>

      {error && <Message severity="error" text={error} className="mt-3 w-full justify-start" />}

      {d && parsed && (
        <div className="mt-4 rounded-lg border border-slate-200 p-4">
          <p className="font-semibold text-slate-900">{d.system.name}</p>
          <p className="text-sm text-slate-500">{label(d.system.type)}</p>
          <ul className="mt-2 grid gap-x-4 text-sm text-slate-700 sm:grid-cols-2">
            <li>บุคคล {count(d.people)} คน</li>
            <li>ลิงก์ {count(d.links)} รายการ</li>
            <li>ข้อควรระวังและงานประจำ {count(d.watch_outs)} รายการ</li>
            <li>งานค้าง {count(d.open_items)} รายการ</li>
            <li>ไฟล์ .md {parsed.payload.docs.length} ไฟล์</li>
          </ul>
          {parsed.skipped.length > 0 && (
            <p className="mt-2 text-xs text-amber-700">
              ข้ามไฟล์ที่ไม่ได้อยู่ในโฟลเดอร์คำถาม: {parsed.skipped.join(", ")}
            </p>
          )}
          <div className="mt-3 flex justify-end gap-2">
            <Button type="button" label="ยกเลิก" text onClick={() => setParsed(null)} />
            <Button type="button" label="นำเข้าเป็นระบบใหม่" icon="pi pi-check" loading={busy} onClick={submit} />
          </div>
        </div>
      )}
    </Card>
  );
}
