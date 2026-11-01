"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, Empty, StepTag } from "@/components/bits";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { AttentionReason, Dashboard } from "@/lib/types";

const SEVERITY_STYLE: Record<AttentionReason["severity"], string> = {
  high: "bg-rose-100 text-rose-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-slate-100 text-slate-600",
};

function Stat({ label, value, detail }: { label: string; value: React.ReactNode; detail?: React.ReactNode }) {
  return (
    <div className="site-card rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-3xl font-semibold text-slate-900">{value}</div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}

/** A labelled horizontal bar per row, scaled to the largest count. */
function Bars({ rows }: { rows: { label: React.ReactNode; count: number; key: string | number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (rows.length === 0) return <Empty>ยังไม่มีระบบ</Empty>;
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.key} className="grid grid-cols-[minmax(0,11rem)_1fr_2rem] items-center gap-3 text-sm">
          <span className="truncate text-slate-700">{r.label}</span>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-gradient-to-r from-slate-500 to-slate-800"
              style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
          <span className="text-right font-mono text-xs tabular-nums text-slate-600">{r.count}</span>
        </li>
      ))}
    </ul>
  );
}

export default function DashboardPage() {
  const { meta, label, notify } = useSession();
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    api<Dashboard>("/api/dashboard").then(setData).catch((e) => notify("error", "โหลดแดชบอร์ดไม่สำเร็จ", e.message));
  }, [notify]);

  const stepName = (n: number) => meta.steps.find((s) => s.number === n)?.name ?? "";

  if (!data) return <p className="text-slate-500">กำลังโหลด…</p>;
  const o = data.overview;
  const pct = o.guide_total ? Math.round((o.guide_answered / o.guide_total) * 100) : 0;
  const severities = data.attention.flatMap((a) => a.reasons.map((r) => r.severity));
  const count = (s: AttentionReason["severity"]) => severities.filter((x) => x === s).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title metal-ink">แดชบอร์ด</h1>
        <p className="mt-1 text-slate-600">ระบบที่ใช้งานอยู่ทั้งหมด {o.total} ระบบ ไม่รวมระบบที่เลิกใช้แล้ว</p>
      </div>

      {/* Overview: the headline numbers. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="ระบบ" value={o.total} />
        <Stat label="ใช้งานจริง" value={o.live} detail="อยู่ที่ขั้นตอน 6 หรือ 7" />
        <Stat label="อยู่ระหว่างพัฒนา" value={o.in_development} detail="อยู่ที่ขั้นตอน 1 ถึง 5" />
        <Stat
          label="คู่มือรับช่วงต่อที่เขียนแล้ว"
          value={`${pct}%`}
          detail={
            <span className="flex items-center gap-2">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <span className="block h-full bg-slate-700" style={{ width: `${pct}%` }} />
              </span>
              <span className="font-mono tabular-nums">{o.guide_answered}/{o.guide_total} ข้อ</span>
            </span>
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Needs attention: the systems to talk about, most serious first. */}
        <Card className="lg:col-span-2" title={
          <>
            ต้องให้ความสำคัญ
            {/* A slow red warning light, only while something needs attention. */}
            {data.attention.length > 0 && <span className="attention-light" aria-hidden />}
          </>
        }>
          {data.attention.length === 0 ? (
            <p className="text-sm text-emerald-700"><i className="pi pi-check-circle mr-1" />ขณะนี้ไม่มีระบบที่ต้องให้ความสำคัญ</p>
          ) : (
            <>
              <p className="-mt-1 mb-3 text-xs text-slate-500">
                {data.attention.length} ระบบ · ร้ายแรง {count("high")} · ปานกลาง {count("medium")} · เล็กน้อย {count("low")}
              </p>
              <ul className="soft-divide">
                {data.attention.map((a) => (
                  <li key={a.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start">
                    <div className="min-w-0 sm:w-64 sm:shrink-0">
                      <Link href={`/system/?id=${encodeURIComponent(a.id)}`} className="font-medium text-sky-800 hover:underline">
                        {a.name}
                      </Link>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
                        <span>{a.id}</span>
                        {a.criticality && <span>· {label(a.criticality)}</span>}
                        {a.unit && <span>· {a.unit}</span>}
                      </div>
                      <div className="mt-1"><StepTag step={a.step} name={stepName(a.step)} /></div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {a.reasons.map((r) => (
                        <span key={r.code} className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${SEVERITY_STYLE[r.severity]}`}>
                          {r.label}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>

        {/* Overview: where systems are in their development. */}
        <Card title="ระบบตามขั้นตอน">
          <Bars rows={o.by_step.map((s) => ({ key: s.step, count: s.count, label: `${s.step}. ${s.name}` }))} />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="ระบบตามประเภท">
          <Bars rows={o.by_type.map((t) => ({ key: t.label, count: t.count, label: label(t.label) }))} />
        </Card>
        <Card title="ระบบตามหน่วยงาน">
          <Bars rows={o.by_unit.map((u) => ({ key: u.label, count: u.count, label: u.label }))} />
        </Card>
      </div>
    </div>
  );
}
