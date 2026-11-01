"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "primereact/button";
import { Checkbox } from "primereact/checkbox";
import { Dialog } from "primereact/dialog";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { SelectButton } from "primereact/selectbutton";
import { Empty } from "@/components/bits";
import { api, formatDate } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { GuideKey, OpenItem, Person, SystemDetail, SystemSummary, WatchOut } from "@/lib/types";
import Section, { Field, rowsHelpers, useSystemSave } from "./Section";

type Props = { system: SystemDetail; onChange: (s: SystemDetail) => void };

function useQuestion(system: SystemDetail, key: GuideKey) {
  const index = system.guide.questions.findIndex((q) => q.key === key);
  return { q: system.guide.questions[index], n: index + 1 };
}

const today = () => new Date().toISOString().slice(0, 10);

/** An empty list opens with one blank row, so the writer can start typing at once. */
function orBlank<T>(rows: T[], blank: T): T[] {
  return rows.length ? rows : [blank];
}

// ---------- 1. What is it, and what breaks if it's down ----------

export function WhatItIs({ system, onChange }: Props) {
  const save = useSystemSave(system, onChange);
  const g = system.guide_fields;
  return (
    <Section<{ description: string; if_down: string }>
      {...useQuestion(system, "what")} system={system} onChange={onChange}
      hint="สองสามประโยคพอ เขียนให้คนที่ไม่เคยเห็นระบบนี้อ่านแล้วเข้าใจ"
      view={() => (
        <div className="space-y-3">
          {g.description ? <p className="prose-plain text-[15px] leading-relaxed text-slate-800">{g.description}</p> : <Empty>ยังไม่ได้บอกว่าระบบทำอะไร</Empty>}
          {g.if_down ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800"><i className="pi pi-bolt mr-1" />ถ้าระบบล่ม</p>
              <p className="prose-plain mt-1 text-sm text-amber-950">{g.if_down}</p>
            </div>
          ) : <Empty>ยังไม่ได้บอกว่าถ้าระบบล่มจะกระทบอะไร</Empty>}
        </div>
      )}
      draft={() => ({ description: g.description ?? "", if_down: g.if_down ?? "" })}
      editor={(d, set) => (
        <div className="space-y-4">
          <Field label="ระบบนี้ทำอะไร">
            <InputTextarea value={d.description} onChange={(e) => set({ ...d, description: e.target.value })} rows={2} autoResize className="w-full"
              placeholder="เช่น ให้เจ้าหน้าที่แล็บจองเครื่อง sequencer และดูตารางการใช้งาน" />
          </Field>
          <Field label="ถ้าระบบล่ม ใครเดือดร้อน และจะรู้ตัวเร็วแค่ไหน">
            <InputTextarea value={d.if_down} onChange={(e) => set({ ...d, if_down: e.target.value })} rows={2} autoResize className="w-full"
              placeholder="เช่น เจ้าหน้าที่แล็บจองเครื่องไม่ได้ รู้ภายในหนึ่งชั่วโมง งานวิจัยที่นัดไว้ต้องเลื่อน" />
          </Field>
        </div>
      )}
      save={(d) => save("PATCH", "", d)}
    />
  );
}

// ---------- 2. Where is everything ----------

const LINK_ICONS: Record<string, string> = {
  production_url: "pi-globe", source_repo: "pi-code", logs: "pi-list", dashboard: "pi-chart-line",
  secrets: "pi-key", readme: "pi-book", runbook: "pi-book", architecture: "pi-sitemap",
};
// Offered as one-click buttons when adding links, in this order.
const QUICK_KINDS = ["production_url", "source_repo", "logs", "dashboard", "secrets", "readme"];

/** A best guess at the link kind from its address, so pasting is usually enough. */
function guessKind(url: string): string | null {
  const u = url.toLowerCase();
  if (/gitlab|github|bitbucket/.test(u)) return "source_repo";
  if (/grafana|kibana|prometheus|uptime|zabbix/.test(u)) return u.includes("log") || u.includes("explore") ? "logs" : "dashboard";
  if (/vault|secret|keepass|bitwarden/.test(u)) return "secrets";
  if (/docs\.google|drive\.google|sharepoint|confluence|notion/.test(u)) return "readme";
  return null;
}

type LinkRow = { kind: string; url: string; label: string };

export function WhereEverything({ system, onChange }: Props) {
  const { meta } = useSession();
  const save = useSystemSave(system, onChange);
  const kindLabel = (k: string) => meta.link_kinds.find((x) => x.key === k)?.label ?? k;
  return (
    <Section<LinkRow[]>
      {...useQuestion(system, "where")} system={system} onChange={onChange}
      hint="วางลิงก์ แล้วพอร์ทัลจะเดาประเภทให้ ส่วนรหัสลับให้บอกแค่ว่าเก็บไว้ที่ไหน ห้ามใส่ค่ารหัสจริง"
      view={() => (
        <div className="flex flex-wrap gap-2">
          {system.links.map((l) => (
            <a key={l.id} href={l.url} target="_blank" rel="noopener noreferrer"
              className="group flex min-w-44 items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2 text-sm hover:border-sky-300 hover:bg-sky-50">
              <i className={`pi ${LINK_ICONS[l.kind] ?? "pi-link"} text-slate-400 group-hover:text-sky-700`} />
              <span className="min-w-0">
                <span className="block text-xs text-slate-500">{kindLabel(l.kind)}</span>
                <span className="block max-w-56 truncate font-medium text-slate-800">{l.label || l.url.replace(/^https?:\/\//, "")}</span>
              </span>
            </a>
          ))}
        </div>
      )}
      draft={() => orBlank(system.links.map((l) => ({ kind: l.kind, url: l.url, label: l.label ?? "" })), { kind: "other", url: "", label: "" })}
      editor={(rows, set) => {
        const { update, remove, add } = rowsHelpers(rows, set);
        const missing = QUICK_KINDS.filter((k) => !rows.some((r) => r.kind === k));
        return (
          <div className="space-y-2">
            {rows.map((row, i) => (
              <div key={i} className="flex flex-wrap gap-2">
                <Dropdown value={row.kind} options={meta.link_kinds} optionLabel="label" optionValue="key" onChange={(e) => update(i, { kind: e.value })} className="w-48" />
                <InputText value={row.url} placeholder="https://…" autoFocus={!row.url} className="min-w-64 flex-[2]"
                  onChange={(e) => update(i, { url: e.target.value, ...(row.kind === "other" && guessKind(e.target.value) ? { kind: guessKind(e.target.value)! } : {}) })} />
                <InputText value={row.label} placeholder="ชื่อที่แสดง (ไม่บังคับ)" onChange={(e) => update(i, { label: e.target.value })} className="flex-1" />
                <Button icon="pi pi-times" text severity="secondary" aria-label="ลบ" onClick={() => remove(i)} />
              </div>
            ))}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-xs text-slate-500">เพิ่ม:</span>
              {missing.map((k) => (
                <Button key={k} label={kindLabel(k)} icon={`pi ${LINK_ICONS[k]}`} size="small" outlined className="!py-1 !text-xs" onClick={() => add({ kind: k, url: "", label: "" })} />
              ))}
              <Button label="ลิงก์อื่น" icon="pi pi-plus" size="small" text className="!py-1 !text-xs" onClick={() => add({ kind: "other", url: "", label: "" })} />
            </div>
          </div>
        );
      }}
      save={(rows) => save("PUT", "/links", rows.filter((r) => r.url.trim()).map((r) => ({ ...r, url: r.url.trim(), label: r.label.trim() || null })))}
    />
  );
}

// ---------- 3. How to run, deploy and roll back ----------

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" aria-label="คัดลอกคำสั่ง" title="คัดลอก"
      onClick={() => navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); })}
      className="ml-1 rounded px-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700">
      <i className={`pi ${done ? "pi-check text-emerald-600" : "pi-copy"} text-[11px]`} />
    </button>
  );
}

/** One step per line; `backticks` mark a command, shown in monospace with a copy button. */
function Steps({ text }: { text: string }) {
  const lines = text.split("\n").map((l) => l.trim().replace(/^(\d+[.)]|[-*])\s+/, "")).filter(Boolean);
  return (
    <ol className="space-y-1.5">
      {lines.map((line, i) => (
        <li key={i} className="flex gap-2.5 text-sm text-slate-800">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-medium text-slate-600">{i + 1}</span>
          <span className="min-w-0 break-words">
            {line.split(/(`[^`]+`)/).map((part, j) =>
              part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
                <span key={j} className="inline-flex items-center rounded bg-slate-900 py-0.5 pl-2 pr-0.5 font-mono text-[12.5px] text-slate-100">
                  {part.slice(1, -1)}<CopyButton text={part.slice(1, -1)} />
                </span>
              ) : <span key={j}>{part}</span>,
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

const HOW = [
  { key: "run_steps", title: "รันบนเครื่องตัวเอง", icon: "pi-desktop", example: "git clone …\n`pip install -r requirements.txt`\n`uvicorn app.main:app --reload`" },
  { key: "deploy_steps", title: "ติดตั้งขึ้นระบบจริง", icon: "pi-cloud-upload", example: "Merge เข้า main\nรอ GitLab CI ผ่านทุกขั้น\nเปิดเว็บตรวจว่าใช้งานได้" },
  { key: "rollback_steps", title: "ย้อนกลับเมื่อมีปัญหา", icon: "pi-replay", example: "เปิด GitLab > Pipelines\nกด Retry ที่ job deploy ของรุ่นก่อนหน้า" },
] as const;

type HowDraft = Record<(typeof HOW)[number]["key"], string>;

export function HowToRun({ system, onChange }: Props) {
  const save = useSystemSave(system, onChange);
  const g = system.guide_fields;
  return (
    <Section<HowDraft>
      {...useQuestion(system, "how")} system={system} onChange={onChange}
      hint="หนึ่งบรรทัดต่อหนึ่งขั้นตอน ครอบคำสั่งด้วย `backtick` เพื่อให้คนอ่านกดคัดลอกได้"
      view={() => (
        <div className="grid gap-5 lg:grid-cols-3">
          {HOW.map((h) => (
            <div key={h.key}>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><i className={`pi ${h.icon} mr-1.5`} />{h.title}</p>
              {g[h.key] ? <Steps text={g[h.key]!} /> : <Empty>ยังไม่ได้เขียน</Empty>}
            </div>
          ))}
        </div>
      )}
      draft={() => ({ run_steps: g.run_steps ?? "", deploy_steps: g.deploy_steps ?? "", rollback_steps: g.rollback_steps ?? "" })}
      editor={(d, set) => (
        <div className="grid gap-4 lg:grid-cols-3">
          {HOW.map((h) => (
            <Field key={h.key} label={h.title}>
              <InputTextarea value={d[h.key]} onChange={(e) => set({ ...d, [h.key]: e.target.value })} rows={5} autoResize
                className="w-full font-mono !text-[13px]" placeholder={h.example} />
            </Field>
          ))}
        </div>
      )}
      save={(d) => save("PATCH", "", d)}
    />
  );
}

// ---------- 4. Watch out ----------

type WatchRow = Omit<WatchOut, "id"> & { id: number | null };

export function WatchOutFor({ system, onChange }: Props) {
  const { meta } = useSession();
  const save = useSystemSave(system, onChange);
  const often = (k: string | null) => meta.chore_frequencies.find((f) => f.key === k)?.label;
  const traps = system.watch_outs.filter((w) => w.kind === "trap");
  const chores = system.watch_outs.filter((w) => w.kind === "chore")
    .sort((a, b) => (a.next_due ?? "9999").localeCompare(b.next_due ?? "9999"));
  return (
    <Section<WatchRow[]>
      {...useQuestion(system, "watch")} system={system} onChange={onChange}
      hint="สิ่งที่คุณรู้แต่คนใหม่ไม่รู้: จุดที่พังง่าย สิ่งที่ดูผิดแต่ตั้งใจทำ และงานที่ต้องทำเองเป็นประจำ"
      view={() => (
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">ข้อควรระวัง</p>
            {traps.length === 0 ? <Empty>ไม่มี</Empty> : (
              <ul className="space-y-2">
                {traps.map((w) => (
                  <li key={w.id} className="flex gap-2 text-sm text-slate-800">
                    <i className="pi pi-exclamation-triangle mt-0.5 text-amber-500" />
                    <span className="prose-plain">{w.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">งานที่ต้องทำเป็นประจำ</p>
            {chores.length === 0 ? <Empty>ไม่มี</Empty> : (
              <ul className="space-y-2">
                {chores.map((w) => {
                  const overdue = !!w.next_due && w.next_due < today();
                  return (
                    <li key={w.id} className="flex gap-2 text-sm">
                      <i className={`pi pi-calendar mt-0.5 ${overdue ? "text-red-600" : "text-slate-400"}`} />
                      <span>
                        <span className="text-slate-800">{w.text}</span>
                        <span className="block text-xs text-slate-500">
                          {often(w.how_often)}
                          {w.next_due && <> · ครั้งถัดไป <span className={overdue ? "font-semibold text-red-600" : ""}>{formatDate(w.next_due)}{overdue && " (เลยกำหนด)"}</span></>}
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
      draft={() => orBlank<WatchRow>(system.watch_outs.map((w) => ({ ...w })), { id: null, kind: "trap", text: "", how_often: null, next_due: null })}
      editor={(rows, set) => {
        const { update, remove, add } = rowsHelpers(rows, set);
        return (
          <div className="space-y-3">
            {rows.map((row, i) => (
              <div key={i} className="flex flex-wrap items-start gap-2 rounded-lg bg-slate-50 p-2">
                <SelectButton value={row.kind} options={meta.watch_out_kinds} optionLabel="label" optionValue="key" allowEmpty={false}
                  onChange={(e) => update(i, { kind: e.value })} pt={{ button: { className: "!py-1.5 !text-xs" } }} />
                <InputTextarea value={row.text} rows={1} autoResize className="min-w-64 flex-1" autoFocus={!row.text}
                  placeholder={row.kind === "trap" ? "เช่น อย่า restart ระหว่างนำเข้าข้อมูลตอนตีหนึ่ง" : "เช่น ต่ออายุใบรับรอง TLS"}
                  onChange={(e) => update(i, { text: e.target.value })} />
                {row.kind === "chore" && (
                  <>
                    <Dropdown value={row.how_often} options={meta.chore_frequencies} optionLabel="label" optionValue="key" placeholder="ความถี่" onChange={(e) => update(i, { how_often: e.value })} className="w-36" />
                    <InputText type="date" value={row.next_due ?? ""} title="ครั้งถัดไป" onChange={(e) => update(i, { next_due: e.target.value || null })} className="w-40" />
                  </>
                )}
                <Button icon="pi pi-times" text severity="secondary" aria-label="ลบ" onClick={() => remove(i)} />
              </div>
            ))}
            <div className="flex gap-2">
              <Button label="ข้อควรระวัง" icon="pi pi-plus" size="small" outlined onClick={() => add({ id: null, kind: "trap", text: "", how_often: null, next_due: null })} />
              <Button label="งานประจำ" icon="pi pi-plus" size="small" outlined onClick={() => add({ id: null, kind: "chore", text: "", how_often: "monthly", next_due: null })} />
            </div>
          </div>
        );
      }}
      save={(rows) => save("PUT", "/watch-outs", rows.filter((r) => r.text.trim()))}
    />
  );
}

// ---------- 5. Depends on / used by ----------

type DepRow = { to_system_id: string | null; external_name: string; note: string };

export function Dependencies({ system, onChange }: Props) {
  const save = useSystemSave(system, onChange);
  const [systems, setSystems] = useState<SystemSummary[]>([]);
  const options = systems.filter((s) => s.id !== system.id).map((s) => ({ label: `${s.name} (${s.id})`, value: s.id }));
  const loadSystems = () => { if (systems.length === 0) api<SystemSummary[]>("/api/systems").then(setSystems).catch(() => undefined); };
  const sysLink = (id: string, name: string) => <Link href={`/system/?id=${encodeURIComponent(id)}`} className="text-sky-700 hover:underline">{name}</Link>;
  return (
    <Section<DepRow[]>
      {...useQuestion(system, "deps")} system={system} onChange={onChange}
      hint="ระบบ ฐานข้อมูล API หรือบริการภายนอกที่ระบบนี้ต้องใช้ ส่วนรายการ 'ระบบที่ใช้ระบบนี้' จะขึ้นให้เอง"
      view={() => (
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">ระบบนี้พึ่งพา</p>
            {system.depends_on.length === 0 ? <Empty>ไม่มี</Empty> : (
              <ul className="space-y-1 text-sm">
                {system.depends_on.map((d, i) => (
                  <li key={i}>
                    {d.to_system_id ? sysLink(d.to_system_id, d.name) : <span>{d.name} <span className="text-xs text-slate-400">(นอกพอร์ทัล)</span></span>}
                    {d.note && <span className="text-slate-500"> · {d.note}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">ระบบที่ใช้ระบบนี้</p>
            {system.used_by.length === 0 ? <Empty>ไม่มี</Empty> : (
              <ul className="space-y-1 text-sm">
                {system.used_by.map((u) => <li key={u.system_id}>{sysLink(u.system_id, u.name)}{u.note && <span className="text-slate-500"> · {u.note}</span>}</li>)}
              </ul>
            )}
          </div>
        </div>
      )}
      draft={() => {
        loadSystems();
        return orBlank(system.depends_on.map((d) => ({ to_system_id: d.to_system_id, external_name: d.external ? d.name : "", note: d.note ?? "" })),
          { to_system_id: null, external_name: "", note: "" });
      }}
      editor={(rows, set) => {
        const { update, remove, add } = rowsHelpers(rows, set);
        return (
          <div className="space-y-2">
            {rows.map((row, i) => (
              <div key={i} className="flex flex-wrap gap-2">
                <Dropdown value={row.to_system_id} options={options} filter showClear placeholder="ระบบในพอร์ทัล" onChange={(e) => update(i, { to_system_id: e.value ?? null })} className="min-w-56 flex-1" />
                <InputText value={row.external_name} disabled={!!row.to_system_id} placeholder="…หรือพิมพ์ชื่อบริการภายนอก" onChange={(e) => update(i, { external_name: e.target.value })} className="flex-1" />
                <InputText value={row.note} placeholder="ใช้ทำอะไร" onChange={(e) => update(i, { note: e.target.value })} className="flex-1" />
                <Button icon="pi pi-times" text severity="secondary" aria-label="ลบ" onClick={() => remove(i)} />
              </div>
            ))}
            <Button label="เพิ่มรายการ" icon="pi pi-plus" size="small" outlined onClick={() => add({ to_system_id: null, external_name: "", note: "" })} />
          </div>
        );
      }}
      save={(rows) => save("PUT", "/dependencies", rows.filter((r) => r.to_system_id || r.external_name.trim()).map((r) => ({
        to_system_id: r.to_system_id || null, external_name: r.to_system_id ? null : r.external_name.trim(), note: r.note.trim() || null,
      })))}
    />
  );
}

// ---------- 6. Who to ask ----------

type RoleRow = { person_id: number | null; role: string; reachable_until: string | null; note: string };

export function WhoToAsk({ system, onChange }: Props) {
  const { meta, notify } = useSession();
  const save = useSystemSave(system, onChange);
  const [people, setPeople] = useState<Person[]>([]);
  const [adding, setAdding] = useState<((id: number) => void) | null>(null);
  const [newPerson, setNewPerson] = useState({ name: "", email: "" });
  const loadPeople = () => { api<Person[]>("/api/people").then(setPeople).catch(() => undefined); };

  async function addPerson(e: React.FormEvent) {
    e.preventDefault();
    try {
      const p = await api<Person>("/api/people", { method: "POST", body: newPerson });
      setPeople((list) => [...list, p].sort((a, b) => a.name.localeCompare(b.name)));
      adding?.(p.id);
      setNewPerson({ name: "", email: "" });
      setAdding(null);
    } catch (err) {
      notify("error", "เพิ่มบุคคลไม่สำเร็จ", (err as Error).message);
    }
  }

  return (
    <Section<RoleRow[]>
      {...useQuestion(system, "who")} system={system} onChange={onChange}
      hint="ใส่เจ้าของเดิมพร้อมวันที่ยังติดต่อได้ และเขียนสั้น ๆ ว่าควรถามแต่ละคนเรื่องอะไร"
      view={() => (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {system.roles.map((r) => (
            <li key={`${r.role}-${r.person.id}`} className={`rounded-lg border px-3 py-2.5 ${r.reachable ? "border-slate-200" : "border-slate-100 bg-slate-50 opacity-60"}`}>
              <p className="text-xs text-slate-500">{r.role_label}</p>
              <p className="font-medium text-slate-900">{r.person.name}</p>
              <a href={`mailto:${r.person.email}`} className="text-xs text-sky-700 hover:underline">{r.person.email}</a>
              {r.note && <p className="mt-1 text-sm text-slate-700">{r.note}</p>}
              {r.reachable_until && (
                <p className={`mt-1 text-xs ${r.reachable ? "text-slate-500" : "text-slate-400"}`}>
                  {r.reachable ? `ติดต่อได้ถึง ${formatDate(r.reachable_until)}` : `ติดต่อไม่ได้แล้วตั้งแต่ ${formatDate(r.reachable_until)}`}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      draft={() => { loadPeople(); return system.roles.map((r) => ({ person_id: r.person.id, role: r.role, reachable_until: r.reachable_until, note: r.note ?? "" })); }}
      editor={(rows, set) => {
        const { update, remove, add } = rowsHelpers(rows, set);
        return (
          <div className="space-y-2">
            {rows.map((row, i) => (
              <div key={i} className="flex flex-wrap gap-2 rounded-lg bg-slate-50 p-2">
                <Dropdown value={row.person_id} options={people.filter((p) => p.active)} optionLabel="name" optionValue="id" filter placeholder="เลือกบุคคล"
                  onChange={(e) => update(i, { person_id: e.value })} className="min-w-52 flex-1"
                  itemTemplate={(p: Person) => <span>{p.name} <span className="text-xs text-slate-500">{p.email}</span></span>} />
                <Dropdown value={row.role} options={meta.roles} optionLabel="label" optionValue="key" onChange={(e) => update(i, { role: e.value })} className="w-48" />
                <InputText value={row.note} placeholder="ถามเรื่องอะไร (ไม่บังคับ)" onChange={(e) => update(i, { note: e.target.value })} className="min-w-48 flex-1" />
                {row.role === "previous_owner" && (
                  <InputText type="date" value={row.reachable_until ?? ""} title="ติดต่อได้ถึงวันที่" onChange={(e) => update(i, { reachable_until: e.target.value || null })} className="w-40" />
                )}
                <Button icon="pi pi-times" text severity="secondary" aria-label="ลบ" onClick={() => remove(i)} />
              </div>
            ))}
            <div className="flex flex-wrap gap-2">
              <Button label="เพิ่มบุคคล" icon="pi pi-plus" size="small" outlined onClick={() => add({ person_id: null, role: "developer", reachable_until: null, note: "" })} />
              <Button label="ส่งต่อจากเจ้าของเดิม" icon="pi pi-history" size="small" outlined onClick={() => add({ person_id: null, role: "previous_owner", reachable_until: null, note: "" })} />
              <Button label="คนที่ยังไม่อยู่ในรายชื่อ" icon="pi pi-user-plus" size="small" text
                onClick={() => setAdding(() => (id: number) => add({ person_id: id, role: "developer", reachable_until: null, note: "" }))} />
            </div>
            <p className="text-xs text-slate-500">ต้องมีเจ้าของฝั่งเทคนิคอย่างน้อยหนึ่งคน เจ้าของเดิมดูคู่มือได้แต่แก้ไขไม่ได้</p>
            <Dialog header="เพิ่มบุคคล" visible={adding !== null} onHide={() => setAdding(null)} style={{ width: "28rem" }}>
              <form onSubmit={addPerson} className="space-y-3">
                <p className="text-sm text-slate-600">สำหรับคนที่ยังไม่เคยเข้าพอร์ทัล เมื่อเขาเข้าสู่ระบบด้วยอีเมลนี้ครั้งแรก จะได้บทบาทนี้ทันที</p>
                <Field label="ชื่อ"><InputText value={newPerson.name} onChange={(e) => setNewPerson({ ...newPerson, name: e.target.value })} required className="w-full" /></Field>
                <Field label="อีเมลที่ทำงาน"><InputText type="email" value={newPerson.email} onChange={(e) => setNewPerson({ ...newPerson, email: e.target.value })} required className="w-full" /></Field>
                <div className="flex justify-end"><Button type="submit" label="เพิ่ม" /></div>
              </form>
            </Dialog>
          </div>
        );
      }}
      save={(rows) => save("PUT", "/roles", rows.filter((r) => r.person_id !== null).map((r) => ({ ...r, note: r.note.trim() || null })))}
    />
  );
}

// ---------- 7. In progress ----------

type ItemRow = Omit<OpenItem, "id" | "done_at" | "done_by"> & { id: number | null };

export function InProgress({ system, onChange }: Props) {
  const { meta } = useSession();
  const save = useSystemSave(system, onChange);
  const [showDone, setShowDone] = useState(false);
  const kind = (k: string) => meta.open_item_kinds.find((x) => x.key === k)?.label ?? k;
  const open = system.open_items.filter((o) => !o.done);
  const done = system.open_items.filter((o) => o.done);

  // Ticking is allowed straight from the reading view: it is the most common edit.
  const toggle = (item: OpenItem) => save("PUT", "/open-items", system.open_items.map((o) => ({ ...o, done: o.id === item.id ? !o.done : o.done })));

  const row = (o: OpenItem) => (
    <li key={o.id} className="flex items-start gap-2.5 text-sm">
      <Checkbox checked={o.done} disabled={!system.can_edit} onChange={() => toggle(o)} aria-label={o.done ? "ยังไม่เสร็จ" : "ทำเสร็จแล้ว"} className="mt-0.5" />
      <span className={o.done ? "text-slate-400 line-through" : "text-slate-800"}>
        {o.text}
        <span className="block text-xs text-slate-500 no-underline">
          {kind(o.kind)}
          {o.promised_to && <> · ให้ {o.promised_to}</>}
          {o.due_date && <> · ภายใน <span className={!o.done && o.due_date < today() ? "font-semibold text-red-600" : ""}>{formatDate(o.due_date)}</span></>}
          {o.done && o.done_by && <> · เสร็จโดย {o.done_by}</>}
        </span>
      </span>
    </li>
  );

  return (
    <Section<ItemRow[]>
      {...useQuestion(system, "progress")} system={system} onChange={onChange}
      hint="งานที่ทำค้างไว้ สิ่งที่สัญญากับผู้ใช้ และเรื่องที่ยังไม่ได้ตัดสินใจ คนรับช่วงต่อจะได้ไม่ต้องเริ่มคิดใหม่"
      view={() => (
        <div>
          {open.length === 0 ? <p className="text-sm text-emerald-700"><i className="pi pi-check-circle mr-1" />ไม่มีงานค้าง</p> : <ul className="space-y-2.5">{open.map(row)}</ul>}
          {done.length > 0 && (
            <div className="mt-3">
              <button type="button" onClick={() => setShowDone(!showDone)} className="text-xs text-slate-500 hover:text-slate-800">
                <i className={`pi ${showDone ? "pi-chevron-down" : "pi-chevron-right"} mr-1 text-[10px]`} />เสร็จแล้ว {done.length} รายการ
              </button>
              {showDone && <ul className="mt-2 space-y-2.5">{done.map(row)}</ul>}
            </div>
          )}
        </div>
      )}
      draft={() => orBlank<ItemRow>(system.open_items.map(({ done_at: _a, done_by: _b, ...o }) => o),
        { id: null, kind: "work", text: "", promised_to: null, due_date: null, done: false })}
      editor={(rows, set) => {
        const { update, remove, add } = rowsHelpers(rows, set);
        return (
          <div className="space-y-3">
            {rows.map((r, i) => (
              <div key={i} className="flex flex-wrap items-start gap-2 rounded-lg bg-slate-50 p-2">
                <Dropdown value={r.kind} options={meta.open_item_kinds} optionLabel="label" optionValue="key" onChange={(e) => update(i, { kind: e.value })} className="w-52" />
                <InputTextarea value={r.text} rows={1} autoResize className="min-w-64 flex-1" autoFocus={!r.text} onChange={(e) => update(i, { text: e.target.value })}
                  placeholder={r.kind === "promise" ? "เช่น เพิ่มปุ่มส่งออก CSV" : r.kind === "decision" ? "เช่น จะย้ายไป PostgreSQL หรือไม่" : "เช่น ย้ายระบบนำเข้าข้อมูลไปใช้คิว"} />
                {r.kind === "promise" && <InputText value={r.promised_to ?? ""} placeholder="สัญญากับใคร" onChange={(e) => update(i, { promised_to: e.target.value })} className="w-44" />}
                <InputText type="date" value={r.due_date ?? ""} title="ภายในวันที่ (ไม่บังคับ)" onChange={(e) => update(i, { due_date: e.target.value || null })} className="w-40" />
                <Button icon="pi pi-times" text severity="secondary" aria-label="ลบ" onClick={() => remove(i)} />
              </div>
            ))}
            <Button label="เพิ่มรายการ" icon="pi pi-plus" size="small" outlined onClick={() => add({ id: null, kind: "work", text: "", promised_to: null, due_date: null, done: false })} />
          </div>
        );
      }}
      save={(rows) => save("PUT", "/open-items", rows.filter((r) => r.text.trim()))}
    />
  );
}
