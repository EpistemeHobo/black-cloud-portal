"use client";

import { Button } from "primereact/button";
import { confirmPopup, ConfirmPopup } from "primereact/confirmpopup";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SystemDetail } from "@/lib/types";

/**
 * "This page is up to date" with a light check first: a small pop-up by the
 * button, no typing (unlike deleting). Warns when guide questions are unanswered.
 */
export default function VerifySystem({ system, onChange }: { system: SystemDetail; onChange: (s: SystemDetail) => void }) {
  const { notify } = useSession();
  const { answered, total } = system.guide;

  async function verify() {
    try {
      onChange(await api<SystemDetail>(`/api/systems/${encodeURIComponent(system.id)}/verify`, { method: "POST" }));
      notify("success", "ยืนยันว่าข้อมูลเป็นปัจจุบันแล้ว");
    } catch (e) {
      notify("error", "ยืนยันไม่สำเร็จ", (e as Error).message);
    }
  }

  function ask(event: React.MouseEvent<HTMLButtonElement>) {
    confirmPopup({
      target: event.currentTarget,
      icon: "pi pi-verified",
      message: (
        <div className="max-w-72 space-y-1.5 text-sm">
          <p className="font-medium text-slate-900">ยืนยันว่าข้อมูลหน้านี้ยังถูกต้องและเป็นปัจจุบัน?</p>
          <p className="text-slate-600">พอร์ทัลจะบันทึกชื่อคุณและวันนี้ไว้ และนับเวลาเตือนให้ตรวจใหม่จากวันนี้</p>
          {answered < total && (
            <p className="text-amber-700">
              <i className="pi pi-exclamation-triangle mr-1 text-xs" />คู่มือรับช่วงต่อยังตอบไม่ครบ ({answered}/{total} ข้อ)
            </p>
          )}
        </div>
      ),
      acceptLabel: "ยืนยัน",
      rejectLabel: "ยกเลิก",
      acceptIcon: "pi pi-check",
      // Cancel is the default, so a stray Enter doesn't confirm.
      defaultFocus: "reject",
      accept: verify,
    });
  }

  return (
    <>
      <ConfirmPopup />
      <Button label="ยืนยันว่าข้อมูลหน้านี้เป็นปัจจุบัน" icon="pi pi-verified" size="small" text onClick={ask} />
    </>
  );
}
