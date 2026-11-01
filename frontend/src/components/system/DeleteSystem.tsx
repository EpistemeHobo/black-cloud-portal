"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "primereact/button";
import { Dialog } from "primereact/dialog";
import { InputText } from "primereact/inputtext";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SystemDetail } from "@/lib/types";

/** The owner's delete button, with a pop-up that asks them to type the name first. */
export default function DeleteSystem({ system }: { system: SystemDetail }) {
  const { notify } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const matches = typed.trim() === system.name.trim();

  async function remove() {
    setBusy(true);
    try {
      await api(`/api/systems/${encodeURIComponent(system.id)}`, { method: "DELETE" });
      notify("success", `ลบ ${system.name} แล้ว`);
      router.push("/systems/");
    } catch (e) {
      notify("error", "ลบระบบไม่สำเร็จ", (e as Error).message);
      setBusy(false);
    }
  }

  function close() {
    setOpen(false);
    setTyped("");
  }

  const footer = (
    <div className="flex justify-end gap-2">
      <Button label="ยกเลิก" text onClick={close} autoFocus />
      <Button label="ลบระบบนี้" icon="pi pi-trash" severity="danger" disabled={!matches} loading={busy} onClick={remove} />
    </div>
  );

  return (
    <>
      <Button label="ลบระบบ" icon="pi pi-trash" size="small" text severity="danger" onClick={() => setOpen(true)} />
      <Dialog header={`ลบ ${system.name}?`} visible={open} onHide={close} footer={footer} style={{ width: "32rem" }}
        breakpoints={{ "640px": "92vw" }} draggable={false}>
        <div className="space-y-3 text-sm text-slate-700">
          <p className="rounded-md bg-red-50 px-3 py-2 text-red-800">
            <i className="pi pi-exclamation-triangle mr-1.5" />ลบแล้วกู้คืนไม่ได้
          </p>
          <p>สิ่งที่จะถูกลบไปด้วย:</p>
          <ul className="list-disc space-y-0.5 pl-5">
            <li>คู่มือรับช่วงต่อทั้ง 7 ข้อ{system.docs.length > 0 && ` และไฟล์ .md ที่แนบไว้ ${system.docs.length} ไฟล์`}</li>
            <li>ข้อมูลแค็ตตาล็อก รายการตรวจสอบ และบันทึกการทบทวน</li>
            <li>รายชื่อบุคคลและลิงก์ของระบบนี้</li>
            {system.used_by.length > 0 && (
              <li>ระบบนี้จะหายไปจากรายการพึ่งพาของ {system.used_by.map((u) => u.name).join(", ")}</li>
            )}
          </ul>
          <p className="text-slate-500">ประวัติการแก้ไขยังเก็บไว้ และรหัส {system.id} จะไม่ถูกนำไปใช้ซ้ำ</p>
          <label className="block pt-1">
            พิมพ์ชื่อระบบ <strong className="select-all font-semibold text-slate-900">{system.name}</strong> เพื่อยืนยัน
            <InputText value={typed} onChange={(e) => setTyped(e.target.value)} className="mt-1 w-full"
              onKeyDown={(e) => { if (e.key === "Enter" && matches && !busy) remove(); }} />
          </label>
        </div>
      </Dialog>
    </>
  );
}
