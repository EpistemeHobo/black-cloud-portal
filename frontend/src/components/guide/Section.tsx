"use client";

import { useRef, useState } from "react";
import { Button } from "primereact/button";
import MarkdownView from "@/components/MarkdownView";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { GuideDoc, GuideQuestion, SystemDetail } from "@/lib/types";

const relative = new Intl.RelativeTimeFormat("th", { numeric: "auto" });

/** "3 เดือนที่แล้ว" style age of an ISO date. */
export function ago(iso: string): string {
  const days = Math.round((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return "วันนี้";
  if (days < 30) return relative.format(-days, "day");
  if (days < 365) return relative.format(-Math.round(days / 30), "month");
  return relative.format(-Math.round(days / 365), "year");
}

/** Saves to the system API and hands back the updated system; false on failure. */
export function useSystemSave(system: SystemDetail, onChange: (s: SystemDetail) => void) {
  const { notify } = useSession();
  return async (method: "PUT" | "PATCH" | "POST" | "DELETE", path: string, body?: unknown, done = "บันทึกแล้ว"): Promise<boolean> => {
    try {
      const url = `/api/systems/${encodeURIComponent(system.id)}${path}`;
      onChange(await api<SystemDetail>(url, { method, body }));
      notify("success", done);
      return true;
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
      return false;
    }
  };
}

// Same limits as the backend (enums.DOC_EXTENSIONS, DOC_MAX_CHARS).
const DOC_EXTENSIONS = [".md", ".markdown"];
const DOC_MAX_CHARS = 200_000;
// Longer files start folded so they don't push the next question far down.
const FOLD_OVER_CHARS = 1500;

function download(doc: GuideDoc) {
  const url = URL.createObjectURL(new Blob([doc.content], { type: "text/markdown;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = doc.filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** One attached markdown file: rendered, downloadable, removable by editors. */
function DocCard({ doc, canEdit, onRemove }: { doc: GuideDoc; canEdit: boolean; onRemove: () => void }) {
  const long = doc.content.length > FOLD_OVER_CHARS;
  const [open, setOpen] = useState(!long);
  return (
    <article className="overflow-hidden rounded-lg border border-slate-200">
      <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
        <i className="pi pi-file text-slate-400" aria-hidden />
        <span className="font-mono text-sm font-medium text-slate-800">{doc.filename}</span>
        {doc.updated_at && (
          <span className="text-xs text-slate-400">อัปเดตล่าสุด {ago(doc.updated_at)}{doc.updated_by && <> โดย {doc.updated_by}</>}</span>
        )}
        <span className="ml-auto flex gap-1">
          <Button icon="pi pi-download" label="ดาวน์โหลด" size="small" text className="!py-1 !text-xs" onClick={() => download(doc)} />
          {canEdit && (
            <Button icon="pi pi-trash" size="small" text severity="secondary" className="!py-1" aria-label={`ลบ ${doc.filename}`}
              onClick={() => { if (window.confirm(`ลบไฟล์ ${doc.filename} ออกจากคำถามนี้?`)) onRemove(); }} />
          )}
        </span>
      </header>
      <div className="px-5 py-4">
        <div className={open ? "" : "md-folded"}>
          <MarkdownView content={doc.content} />
        </div>
        {long && (
          <button type="button" onClick={() => setOpen(!open)} className="mt-2 text-sm text-sky-700 hover:underline">
            {open ? "ย่อ" : "แสดงทั้งหมด"}
          </button>
        )}
      </div>
    </article>
  );
}

type Props<D> = {
  system: SystemDetail;
  onChange: (s: SystemDetail) => void;
  n: number;
  q: GuideQuestion;
  /** One line under the title telling the writer what to put here. */
  hint: string;
  /** Draws the written answer for readers. Only called when there is one. */
  view: () => React.ReactNode;
  /** The draft to edit, made from the saved answer. */
  draft: () => D;
  editor: (draft: D, set: (d: D) => void) => React.ReactNode;
  save: (draft: D) => Promise<boolean>;
};

/**
 * One handover question: the same card for reading and for editing in place.
 * Editors can also attach markdown files (button or drag and drop); readers see
 * them rendered under the answer and can download them.
 */
export default function Section<D>({ system, onChange, n, q, hint, view, draft, editor, save }: Props<D>) {
  const { notify } = useSession();
  const [editing, setEditing] = useState<D | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const saveTo = useSystemSave(system, onChange);
  const owner = system.roles.find((r) => r.role === "technical_owner");
  const docs = system.docs.filter((d) => d.question === q.key);
  const canEdit = system.can_edit;

  function start() {
    setEditing(draft());
  }

  async function submit() {
    if (editing === null) return;
    setBusy(true);
    if (await save(editing)) setEditing(null);
    setBusy(false);
  }

  async function markNothing() {
    const nothing = system.guide.questions.filter((x) => x.nothing).map((x) => x.key);
    await saveTo("PATCH", "", { guide_nothing: [...nothing, q.key] });
  }

  async function upload(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      if (!DOC_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))) {
        notify("error", `แนบ ${file.name} ไม่ได้`, "รับเฉพาะไฟล์ Markdown (.md)");
        continue;
      }
      const content = await file.text();
      if (content.length > DOC_MAX_CHARS) {
        notify("error", `แนบ ${file.name} ไม่ได้`, "ไฟล์ใหญ่เกิน 200,000 ตัวอักษร");
        continue;
      }
      const replacing = docs.some((d) => d.filename === file.name);
      await saveTo("POST", "/docs", { question: q.key, filename: file.name, content },
        replacing ? `แทนที่ ${file.name} แล้ว` : `แนบ ${file.name} แล้ว`);
    }
  }

  // Drag and drop a file anywhere on the card.
  const dropProps = canEdit ? {
    onDragOver: (e: React.DragEvent) => {
      if (!e.dataTransfer.types.includes("Files")) return;
      e.preventDefault();
      setDragging(true);
    },
    onDragLeave: (e: React.DragEvent) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
    },
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length) upload(e.dataTransfer.files);
    },
  } : {};

  const empty = !q.answered && editing === null;
  const attachButton = (
    <Button label="แนบไฟล์ .md" icon="pi pi-paperclip" size="small" text onClick={() => fileInput.current?.click()} />
  );

  return (
    <section id={`q-${q.key}`} {...dropProps}
      className={`site-card relative scroll-mt-24 rounded-xl border bg-white p-5 ${dragging ? "border-sky-400 ring-2 ring-sky-200" : "border-slate-200"}`}>
      {dragging && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-sky-50/90 text-sm font-medium text-sky-800">
          <i className="pi pi-upload mr-2" />วางไฟล์ .md เพื่อแนบกับคำถามนี้
        </div>
      )}
      {canEdit && (
        <input ref={fileInput} type="file" accept=".md,.markdown,text/markdown" multiple hidden
          onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
      )}

      <header className="flex flex-wrap items-start gap-3">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
            q.answered ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-500 ring-1 ring-slate-300"
          }`}
          aria-label={q.answered ? "ตอบแล้ว" : "ยังไม่ได้ตอบ"}
        >
          {q.answered ? <i className="pi pi-check text-xs" /> : n}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-slate-900">{q.title}</h2>
          {editing !== null ? (
            <p className="mt-0.5 text-sm text-slate-500">{hint}</p>
          ) : q.updated_at ? (
            <p className="mt-0.5 text-xs text-slate-400">
              อัปเดตล่าสุด {ago(q.updated_at)}{q.updated_by && <> โดย {q.updated_by}</>}
            </p>
          ) : null}
        </div>
        {canEdit && (
          <div className="flex gap-1">
            {editing !== null ? (
              <>
                <Button label="ยกเลิก" text size="small" onClick={() => setEditing(null)} />
                <Button label="บันทึก" icon="pi pi-check" size="small" loading={busy} onClick={submit} />
              </>
            ) : !empty ? (
              <>
                {attachButton}
                <Button label={q.written ? "แก้ไข" : "เขียนคำตอบ"} icon="pi pi-pencil" size="small" text onClick={start} />
              </>
            ) : null}
          </div>
        )}
      </header>

      <div className="mt-4 space-y-4 sm:pl-10">
        {editing !== null ? (
          editor(editing, setEditing)
        ) : empty ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-center">
            <p className="text-sm text-slate-500">
              ยังไม่ได้เขียน
              {!canEdit && owner && <> · สอบถามได้ที่ <strong className="text-slate-700">{owner.person.name}</strong> ({owner.role_label})</>}
            </p>
            {canEdit && (
              <>
                <p className="mx-auto mt-1 max-w-md text-xs text-slate-400">{hint}</p>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  <Button label="เริ่มเขียน" icon="pi pi-pencil" size="small" onClick={start} />
                  <Button label="แนบไฟล์ .md" icon="pi pi-paperclip" size="small" outlined onClick={() => fileInput.current?.click()} />
                  {q.can_be_empty && <Button label="ไม่มีรายการ" size="small" outlined onClick={markNothing} />}
                </div>
                <p className="mt-2 text-xs text-slate-400">หรือลากไฟล์ .md มาวางที่นี่</p>
              </>
            )}
          </div>
        ) : q.nothing ? (
          <p className="text-sm text-slate-500"><i className="pi pi-minus-circle mr-1.5 text-slate-400" />ไม่มีรายการ</p>
        ) : q.written ? (
          view()
        ) : null}

        {editing === null && docs.map((d) => (
          <DocCard key={d.id} doc={d} canEdit={canEdit}
            onRemove={() => saveTo("DELETE", `/docs/${d.id}`, undefined, `ลบ ${d.filename} แล้ว`)} />
        ))}
      </div>
    </section>
  );
}

/** A label above an input, with an optional hint underneath. */
export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="mt-1 block">{children}</span>
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

/** Add/remove rows of a list editor. */
export function rowsHelpers<T>(rows: T[], set: (rows: T[]) => void) {
  return {
    update: (i: number, patch: Partial<T>) => set(rows.map((r, j) => (j === i ? { ...r, ...patch } : r))),
    remove: (i: number) => set(rows.filter((_, j) => j !== i)),
    add: (row: T) => set([...rows, row]),
  };
}
