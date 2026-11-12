"use client";

import { Tag } from "primereact/tag";
import { useSession } from "@/lib/session";
import type { ChecklistSummary } from "@/lib/types";

export function StepTag({ step, name }: { step: number; name?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-sky-200 px-2.5 py-0.5 text-xs font-medium text-sky-900">
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-700 text-[10px] text-white">{step}</span>
      {name}
    </span>
  );
}

export function LifecycleTag({ state }: { state: string }) {
  const { label } = useSession();
  if (state === "Active") return null;
  const severity = state === "Retired" ? "secondary" : state === "Deprecated" ? "danger" : "warning";
  return <Tag value={label(state)} severity={severity} />;
}

// `dark` is for use on the site background rather than on a white card.
export function Progress({ summary, dark = false }: { summary: ChecklistSummary; dark?: boolean }) {
  const { required_due: due, required_finished: done } = summary;
  if (due === 0) return <span className={`text-xs ${dark ? "text-slate-500" : "text-slate-400"}`}>ยังไม่มีรายการที่ถึงกำหนด</span>;
  const pct = Math.round((done / due) * 100);
  const color = pct === 100 ? "bg-emerald-500" : pct >= 50 ? "bg-sky-500" : "bg-amber-500";
  return (
    <div className="flex min-w-28 items-center gap-2" title={`รายการจำเป็นที่ทำแล้ว ${done} จาก ${due} รายการ`}>
      <div className={`h-1.5 flex-1 overflow-hidden rounded-full ${dark ? "bg-white/15" : "bg-slate-200"}`}>
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${dark ? "text-slate-300" : "text-slate-600"}`}>{done}/{due}</span>
    </div>
  );
}

export function Card({ title, children, actions, className = "" }: {
  title: React.ReactNode; children: React.ReactNode; actions?: React.ReactNode; className?: string;
}) {
  return (
    <section className={`site-card rounded-xl border border-slate-200 bg-white p-5 ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">{title}</h2>
        <div className="ml-auto flex gap-2">{actions}</div>
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm italic text-slate-400">{children}</p>;
}

export function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-sky-700 hover:underline">
      {children}
      <i className="pi pi-external-link ml-1 text-[10px]" aria-hidden />
    </a>
  );
}

/** How serious a leak alert is. */
export function SeverityTag({ severity }: { severity: string }) {
  const { meta } = useSession();
  const text = meta.alert_severities.find((s) => s.key === severity)?.label ?? severity;
  const tone = severity === "critical" ? "danger" : severity === "high" ? "warning" : "info";
  return <Tag value={text} severity={tone} />;
}

/** A technical debt's risk: High, Medium or Low. */
export function RiskTag({ risk }: { risk: string }) {
  const { label } = useSession();
  const tone = risk === "High" ? "danger" : risk === "Medium" ? "warning" : "secondary";
  return <Tag value={`ความเสี่ยง${label(risk)}`} severity={tone} />;
}

/** A technical debt's status. */
export function DebtStatusTag({ status }: { status: string }) {
  const { meta } = useSession();
  const text = meta.debt_statuses.find((s) => s.key === status)?.label ?? status;
  const tone = status === "paid_off" ? "success" : status === "in_progress" ? "info" : status === "wont_fix" ? "secondary" : undefined;
  return <Tag value={text} severity={tone} />;
}
