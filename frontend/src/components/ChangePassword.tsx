"use client";

import { useState } from "react";
import { Button } from "primereact/button";
import { Dialog } from "primereact/dialog";
import { Message } from "primereact/message";
import { Password } from "primereact/password";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

/** The header's key button: change your own password, knowing the current one. */
export default function ChangePassword({ tabIndex }: { tabIndex?: number }) {
  const { notify } = useSession();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function close() {
    setOpen(false);
    setCurrent("");
    setNext("");
    setConfirm("");
    setError(null);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (next !== confirm) {
      setError("รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api("/api/auth/password", { method: "PUT", body: { current_password: current, new_password: next } });
      notify("success", "เปลี่ยนรหัสผ่านแล้ว");
      close();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const field = (label: string, value: string, set: (v: string) => void, autoComplete: string) => (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <Password value={value} onChange={(e) => set(e.target.value)} feedback={false} toggleMask required
        autoComplete={autoComplete} className="mt-1 w-full" inputClassName="w-full" />
    </label>
  );

  return (
    <>
      <Button icon="pi pi-key" text rounded className="!text-slate-200" onClick={() => setOpen(true)}
        tabIndex={tabIndex} aria-label="เปลี่ยนรหัสผ่าน" tooltip="เปลี่ยนรหัสผ่าน" tooltipOptions={{ position: "bottom" }} />
      <Dialog header="เปลี่ยนรหัสผ่าน" visible={open} onHide={close} className="w-full max-w-md" modal>
        <form onSubmit={save} className="space-y-4">
          {field("รหัสผ่านปัจจุบัน", current, setCurrent, "current-password")}
          {field("รหัสผ่านใหม่ (อย่างน้อย 8 ตัวอักษร)", next, setNext, "new-password")}
          {field("ยืนยันรหัสผ่านใหม่", confirm, setConfirm, "new-password")}
          {error && <Message severity="error" text={error} className="w-full justify-start" />}
          <div className="flex justify-end gap-2">
            <Button type="button" label="ยกเลิก" text onClick={close} />
            <Button type="submit" label="บันทึก" loading={busy} />
          </div>
        </form>
      </Dialog>
    </>
  );
}
