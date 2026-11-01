"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Button } from "primereact/button";
import { TabPanel, TabView } from "primereact/tabview";
import { LifecycleTag, Progress } from "@/components/bits";
import HandoverGuide, { GuideProgress } from "@/components/guide/HandoverGuide";
import ChecklistTab from "@/components/system/ChecklistTab";
import DeleteSystem from "@/components/system/DeleteSystem";
import DetailsTab from "@/components/system/DetailsTab";
import HistoryTab from "@/components/system/HistoryTab";
import StepTracker from "@/components/system/StepTracker";
import VerifySystem from "@/components/system/VerifySystem";
import { api, API_BASE, ApiError, formatDate } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SystemDetail } from "@/lib/types";

function SystemPage() {
  const id = useSearchParams().get("id") ?? "";
  const { label, notify } = useSession();
  const [system, setSystem] = useState<SystemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState(0);

  const load = useCallback(() => {
    if (!id) return;
    api<SystemDetail>(`/api/systems/${encodeURIComponent(id)}`)
      .then((s) => {
        setSystem(s);
        document.title = `${s.name} · T2Gen Developer Portal`;
      })
      .catch((e: ApiError) => setError(e.status === 404 ? `ไม่พบระบบ ${id}` : e.message));
  }, [id]);
  useEffect(load, [load]);

  const problem = id ? error : "ยังไม่ได้เลือกระบบ";
  if (problem) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
        <p className="text-slate-700">{problem}</p>
        <Link href="/systems/" className="mt-3 inline-block text-sky-700 hover:underline">กลับไปที่ระบบทั้งหมด</Link>
      </div>
    );
  }
  if (!system) return <p className="text-slate-500">กำลังโหลด…</p>;

  const owner = system.roles.find((r) => r.role === "technical_owner");

  return (
    <div className="space-y-4">
      <nav className="text-sm text-slate-500"><Link href="/systems/" className="hover:text-slate-800 hover:underline">ระบบทั้งหมด</Link> / {system.id}</nav>
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="page-title flex flex-wrap items-center gap-3">
            <span className="metal-ink">{system.name}</span>
            <LifecycleTag state={system.lifecycle_state} />
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            {system.id} · {label(system.type)}
            {system.owning_unit && <> · {system.owning_unit.name}</>}
            {owner && (
              <> · ถามได้ที่ <a href={`mailto:${owner.person.email}`} className="font-medium text-sky-700 hover:underline">{owner.person.name}</a></>
            )}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 text-right">
          <GuideProgress answered={system.guide.answered} total={system.guide.total} />
          <span className="text-xs text-slate-500">
            {system.verified_at
              ? `ยืนยันว่าเป็นปัจจุบันเมื่อ ${formatDate(system.verified_at)} โดย ${system.verified_by?.name}`
              : "ยังไม่เคยยืนยันว่าข้อมูลเป็นปัจจุบัน"}
          </span>
          <div className="flex flex-wrap justify-end gap-1">
            {system.can_edit && <VerifySystem system={system} onChange={setSystem} />}
            {system.can_edit && (
              <a href={`${API_BASE}/api/systems/${encodeURIComponent(system.id)}/export`} download
                className="p-button p-button-text p-button-sm" title="ดาวน์โหลดเป็นโฟลเดอร์ (.zip): system.json และไฟล์ .md">
                <i className="pi pi-download mr-2" aria-hidden />ส่งออก
              </a>
            )}
            {system.can_delete && <DeleteSystem system={system} />}
          </div>
        </div>
      </div>

      <TabView activeIndex={tab} onTabChange={(e) => setTab(e.index)} className="site-tabs rounded-lg" panelContainerClassName="!bg-transparent !px-0">
        <TabPanel header="คู่มือรับช่วงต่อ">
          <HandoverGuide system={system} onChange={setSystem} />
        </TabPanel>
        <TabPanel header="ข้อมูลแค็ตตาล็อก">
          <DetailsTab key={system.updated_at} system={system} onChange={setSystem} />
        </TabPanel>
        <TabPanel header="ขั้นตอนและรายการตรวจสอบ">
          <div className="space-y-4">
            <p className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
              <span>ไม่บังคับ: ใช้เป็นแนวทางเมื่อสร้างระบบใหม่ตามมาตรฐาน T2Gen</span>
              <Progress summary={system.checklist} />
            </p>
            <StepTracker system={system} onChange={setSystem} />
            <ChecklistTab system={system} onProgress={load} />
          </div>
        </TabPanel>
        <TabPanel header="ประวัติการแก้ไข">
          <HistoryTab system={system} />
        </TabPanel>
      </TabView>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-slate-500">กำลังโหลด…</p>}>
      <SystemPage />
    </Suspense>
  );
}
