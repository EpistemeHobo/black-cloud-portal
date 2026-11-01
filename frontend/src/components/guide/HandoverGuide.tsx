"use client";

import type { SystemDetail } from "@/lib/types";
import ReviewNotes from "@/components/system/ReviewNotes";
import { Dependencies, HowToRun, InProgress, WatchOutFor, WhatItIs, WhereEverything, WhoToAsk } from "./questions";

type Props = { system: SystemDetail; onChange: (s: SystemDetail) => void };

export function GuideProgress({ answered, total, dark = false }: { answered: number; total: number; dark?: boolean }) {
  const pct = Math.round((answered / total) * 100);
  return (
    <div className="flex min-w-28 items-center gap-2" title={`คู่มือรับช่วงต่อตอบแล้ว ${answered} จาก ${total} ข้อ`}>
      <div className={`h-1.5 flex-1 overflow-hidden rounded-full ${dark ? "bg-white/15" : "bg-slate-200"}`}>
        <div className={`h-full ${answered === total ? "bg-emerald-500" : "bg-sky-500"}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${dark ? "text-slate-300" : "text-slate-600"}`}>{answered}/{total}</span>
    </div>
  );
}

/** The system page's main view: seven questions in reading order, each edited in place. */
export default function HandoverGuide({ system, onChange }: Props) {
  const { questions, answered, total } = system.guide;
  return (
    <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <nav aria-label="สารบัญคู่มือ" className="hidden lg:block">
        <div className="sticky top-20 space-y-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">คู่มือรับช่วงต่อ</p>
            <div className="mt-2"><GuideProgress answered={answered} total={total} /></div>
          </div>
          <ol className="space-y-0.5">
            {questions.map((q, i) => (
              <li key={q.key}>
                <a href={`#q-${q.key}`} className="flex items-start gap-2 rounded-md px-2 py-1.5 text-sm text-slate-700 hover:bg-white hover:text-slate-950">
                  <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] ${q.answered ? "bg-emerald-600 text-white" : "text-slate-400 ring-1 ring-slate-300"}`}>
                    {q.answered ? <i className="pi pi-check text-[8px]" /> : i + 1}
                  </span>
                  <span className="leading-snug">{q.title}</span>
                </a>
              </li>
            ))}
          </ol>
        </div>
      </nav>

      <div className="min-w-0 space-y-4">
        <WhatItIs system={system} onChange={onChange} />
        <WhereEverything system={system} onChange={onChange} />
        <HowToRun system={system} onChange={onChange} />
        <WatchOutFor system={system} onChange={onChange} />
        <Dependencies system={system} onChange={onChange} />
        <WhoToAsk system={system} onChange={onChange} />
        <InProgress system={system} onChange={onChange} />
        <ReviewNotes system={system} />
      </div>
    </div>
  );
}
