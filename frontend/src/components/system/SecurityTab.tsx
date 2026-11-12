"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "primereact/button";
import { Dialog } from "primereact/dialog";
import { Dropdown } from "primereact/dropdown";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { SelectButton } from "primereact/selectbutton";
import { Tag } from "primereact/tag";
import { Card, Empty, SeverityTag } from "@/components/bits";
import { api, formatDate, formatDateTime } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { SecretAlert, SystemDetail, Vault, VaultSecret } from "@/lib/types";

// A value nobody has changed in a year is worth rotating.
const ROTATE_AFTER_DAYS = 365;
// How long a revealed value stays on screen.
const REVEAL_SECONDS = 30;

type SecretDraft = { name: string; environment: string; description: string; value: string };

function age(iso: string | null): number {
  return iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000) : 0;
}

/** One vault entry, with its value shown for a short while when asked. */
function SecretRow({ s, canUse, base, onEdit, onDelete, onRevealed }: {
  s: VaultSecret; canUse: boolean; base: string; onEdit: () => void; onDelete: () => void; onRevealed: () => void;
}) {
  const { label, notify } = useSession();
  const [value, setValue] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  async function reveal() {
    try {
      const r = await api<{ value: string }>(`${base}/${s.id}/reveal`, { method: "POST" });
      setValue(r.value);
      onRevealed();
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setValue(null), REVEAL_SECONDS * 1000);
    } catch (e) {
      notify("error", "เปิดดูค่าไม่สำเร็จ", (e as Error).message);
    }
  }

  async function copy() {
    if (value === null) return;
    await navigator.clipboard.writeText(value);
    notify("success", "คัดลอกแล้ว", "อย่าวางค่านี้ในแชท เอกสาร หรือหน้าอื่นของพอร์ทัล");
  }

  const stale = age(s.rotated_at) > ROTATE_AFTER_DAYS;
  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <i className="pi pi-key text-slate-400" aria-hidden />
        <span className="font-mono text-sm font-semibold text-slate-900">{s.name}</span>
        <Tag value={label(s.environment)} severity={s.environment === "Prod" ? "danger" : "info"} />
        {stale && <Tag value={`ไม่ได้เปลี่ยนค่ามา ${age(s.rotated_at)} วัน`} severity="warning" icon="pi pi-refresh" />}
        {canUse && (
          <span className="ml-auto flex gap-1">
            <Button label={value === null ? "ดูค่า" : "ซ่อน"} icon={value === null ? "pi pi-eye" : "pi pi-eye-slash"} size="small" text
              onClick={value === null ? reveal : () => setValue(null)} />
            <Button icon="pi pi-pencil" text rounded size="small" severity="secondary" aria-label="แก้ไขหรือเปลี่ยนค่า" onClick={onEdit} />
            <Button icon="pi pi-trash" text rounded size="small" severity="secondary" aria-label="ลบ" onClick={onDelete} />
          </span>
        )}
      </div>
      {s.description && <p className="mt-1 text-sm text-slate-600">{s.description}</p>}
      {value !== null && (
        <div className="mt-2 flex items-start gap-2 rounded-md bg-slate-900 p-2">
          <pre className="max-h-48 flex-1 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-emerald-200">{value}</pre>
          <Button icon="pi pi-copy" text rounded size="small" className="!text-slate-200" aria-label="คัดลอก" onClick={copy} />
        </div>
      )}
      <p className="mt-1 text-xs text-slate-500">
        เปลี่ยนค่าล่าสุด {formatDate(s.rotated_at)}
        {s.updated_by && <> โดย {s.updated_by}</>}
        {s.last_revealed_at ? <> · เปิดดูล่าสุด {formatDateTime(s.last_revealed_at)} โดย {s.last_revealed_by}</> : <> · ยังไม่มีใครเปิดดู</>}
      </p>
    </li>
  );
}

function VaultCard({ system }: { system: SystemDetail }) {
  const { meta, label, notify } = useSession();
  const [vault, setVault] = useState<Vault | null>(null);
  const [editing, setEditing] = useState<{ id: number | null; draft: SecretDraft } | null>(null);
  const [busy, setBusy] = useState(false);
  const base = `/api/systems/${encodeURIComponent(system.id)}/secrets`;

  const load = useCallback(() => {
    api<Vault>(base).then(setVault).catch((e) => notify("error", "โหลดตู้เซฟรหัสลับไม่สำเร็จ", e.message));
  }, [base, notify]);
  useEffect(load, [load]);

  async function save() {
    if (!editing) return;
    setBusy(true);
    try {
      const { draft, id } = editing;
      const body = { ...draft, value: draft.value || undefined };
      setVault(await api<Vault>(id ? `${base}/${id}` : base, { method: id ? "PUT" : "POST", body }));
      setEditing(null);
      notify("success", id && draft.value ? "เปลี่ยนค่าแล้ว" : "บันทึกแล้ว",
        "ถ้าค่านี้เคยอยู่ในข้อความหรือไฟล์ของระบบ พอร์ทัลจะแจ้งเตือนในหัวข้อด้านล่าง");
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(s: VaultSecret) {
    if (!window.confirm(`ลบ ${s.name} ออกจากตู้เซฟหรือไม่? ลบแล้วกู้คืนไม่ได้`)) return;
    try {
      setVault(await api<Vault>(`${base}/${s.id}`, { method: "DELETE" }));
    } catch (e) {
      notify("error", "ลบไม่สำเร็จ", (e as Error).message);
    }
  }

  const canUse = vault?.can_use ?? false;
  const draft = editing?.draft;
  const setDraft = (d: Partial<SecretDraft>) => editing && setEditing({ ...editing, draft: { ...editing.draft, ...d } });

  return (
    <Card
      title={<><i className="pi pi-lock text-slate-500" aria-hidden />ตู้เซฟรหัสลับ</>}
      actions={canUse && vault?.enabled && (
        <Button label="เก็บรหัสลับ" icon="pi pi-plus" size="small" outlined
          onClick={() => setEditing({ id: null, draft: { name: "", environment: "All", description: "", value: "" } })} />
      )}
    >
      <p className="-mt-1 mb-3 text-sm text-slate-600">
        เก็บรหัสผ่าน คีย์ API และค่าตั้งค่าลับของระบบไว้ที่นี่ แทนการเขียนลงในคู่มือหรือไฟล์แนบ
        ค่าถูกเข้ารหัสก่อนบันทึก และเปิดดูได้เฉพาะคนในทีมของระบบตามรายชื่อด้านล่าง ทุกครั้งที่เปิดดูจะถูกบันทึกในประวัติการแก้ไข
      </p>
      {vault === null ? <Empty>กำลังโหลด…</Empty> : !vault.enabled ? (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          ตู้เซฟยังไม่เปิดใช้: ผู้ดูแลพอร์ทัลต้องตั้งค่า <code>SECRETS_ENCRYPTION_KEY</code> ก่อน
        </p>
      ) : vault.items.length === 0 ? (
        <Empty>ยังไม่มีรหัสลับในตู้เซฟ</Empty>
      ) : (
        <ul className="space-y-2">
          {vault.items.map((s) => (
            <SecretRow key={s.id} s={s} canUse={canUse} base={base} onDelete={() => remove(s)} onRevealed={load}
              onEdit={() => setEditing({ id: s.id, draft: { name: s.name, environment: s.environment, description: s.description ?? "", value: "" } })} />
          ))}
        </ul>
      )}
      {vault && (
        <div className="mt-4 border-t border-slate-100 pt-3 text-sm">
          <p className="font-medium text-slate-700">ผู้ที่เปิดดูค่าได้</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {vault.access.map((p) => (
              <li key={p.email} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                {p.name} <span className="text-slate-500">· {p.roles.join(", ")}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">
            คือเจ้าของ ผู้ดูแลสำรอง และนักพัฒนาของระบบ (แก้ได้ในคำถาม &quot;ถามใครได้บ้าง&quot; ของคู่มือ) เมื่อมีคนออกจากทีม ให้นำชื่อออกและเปลี่ยนค่าที่เขาเคยเห็น
            ผู้ดูแลพอร์ทัลเห็นเฉพาะชื่อรายการ ไม่เห็นค่า
            {!canUse && " คุณเห็นหน้านี้ในฐานะผู้ดูแลพอร์ทัล"}
          </p>
        </div>
      )}

      <Dialog header={editing?.id ? "แก้ไขรหัสลับ" : "เก็บรหัสลับ"} visible={editing !== null} onHide={() => setEditing(null)}
        className="w-full max-w-lg" footer={
          <div className="flex justify-end gap-2">
            <Button label="ยกเลิก" text onClick={() => setEditing(null)} />
            <Button label="บันทึก" icon="pi pi-check" loading={busy}
              disabled={!draft?.name.trim() || (!editing?.id && !draft?.value)} onClick={save} />
          </div>
        }>
        {draft && (
          <div className="space-y-3">
            <label className="block text-sm">
              ชื่อ
              <InputText value={draft.name} onChange={(e) => setDraft({ name: e.target.value })} maxLength={100} autoFocus
                className="mt-1 w-full font-mono" placeholder="เช่น DB_PASSWORD" />
            </label>
            <label className="block text-sm">
              สภาพแวดล้อม
              <Dropdown value={draft.environment} options={choiceOptions(meta.secret_environments, label)} optionLabel="label"
                optionValue="value" onChange={(e) => setDraft({ environment: e.value })} className="mt-1 flex w-full" />
            </label>
            <label className="block text-sm">
              ใช้ทำอะไร
              <InputText value={draft.description} onChange={(e) => setDraft({ description: e.target.value })} maxLength={500}
                className="mt-1 w-full" placeholder="เช่น รหัสผ่านผู้ใช้ portal_app ของฐานข้อมูลจริง" />
            </label>
            <label className="block text-sm">
              {editing?.id ? "ค่าใหม่ (เว้นว่างถ้าไม่เปลี่ยน)" : "ค่า"}
              <InputTextarea value={draft.value} onChange={(e) => setDraft({ value: e.target.value })} rows={3} autoResize
                spellCheck={false} autoComplete="off" className="mt-1 w-full font-mono text-sm" />
            </label>
            <p className="text-xs text-slate-500">ถ้าค่านี้เคยถูกเขียนไว้ในหน้าใดของพอร์ทัลหรือส่งต่อในแชท ให้เปลี่ยนค่าที่ต้นทางก่อน แล้วเก็บค่าใหม่</p>
          </div>
        )}
      </Dialog>
    </Card>
  );
}

function AlertsCard({ system, onChange }: { system: SystemDetail; onChange: () => void }) {
  const { meta, notify } = useSession();
  const [alerts, setAlerts] = useState<SecretAlert[] | null>(null);
  const [show, setShow] = useState<"open" | "all">("open");
  const [closing, setClosing] = useState<{ alert: SecretAlert; resolution: string; note: string } | null>(null);
  const base = `/api/systems/${encodeURIComponent(system.id)}/secret-alerts`;

  const load = useCallback(() => {
    api<SecretAlert[]>(base).then(setAlerts).catch((e) => notify("error", "โหลดการแจ้งเตือนไม่สำเร็จ", e.message));
  }, [base, notify]);
  useEffect(load, [load]);

  async function resolve(alert: SecretAlert, resolution: string | null, note?: string) {
    try {
      setAlerts(await api<SecretAlert[]>(`${base}/${alert.id}`, { method: "PUT", body: { resolution, note } }));
      setClosing(null);
      onChange();
    } catch (e) {
      notify("error", "บันทึกไม่สำเร็จ", (e as Error).message);
    }
  }

  const resolutionLabel = (k: string | null) => meta.alert_resolutions.find((r) => r.key === k)?.label ?? k;
  const visible = (alerts ?? []).filter((a) => show === "all" || a.status === "open");

  return (
    <Card
      title={<><i className="pi pi-shield text-slate-500" aria-hidden />การแจ้งเตือนรหัสลับรั่วไหล</>}
      actions={<SelectButton value={show} onChange={(e) => e.value && setShow(e.value)} allowEmpty={false}
        options={[{ label: "ยังไม่ปิด", value: "open" }, { label: "ทั้งหมด", value: "all" }]} className="p-selectbutton-sm" />}
    >
      <p className="-mt-1 mb-3 text-sm text-slate-600">
        พอร์ทัลตรวจทุกข้อความและไฟล์แนบของระบบเมื่อบันทึก และตรวจซ้ำทั้งหมดเป็นระยะ หากพบข้อความที่ดูเหมือนรหัสลับ
        คนนอกทีมจะเห็นข้อความนั้นถูกซ่อนไว้ จนกว่าจะปิดการแจ้งเตือนว่าไม่ใช่รหัสลับ
      </p>
      <ol className="mb-3 list-decimal space-y-0.5 pl-5 text-xs text-slate-600">
        <li>ถือว่ารหัสนั้นรั่วแล้ว: เปลี่ยนหรือยกเลิกที่ต้นทางก่อน (เช่น หน้าตั้งค่า token ของ GitLab หรือ IAM ของ AWS)</li>
        <li>ลบรหัสออกจากข้อความหรือไฟล์ แล้วเก็บค่าใหม่ไว้ในตู้เซฟด้านบน</li>
        <li>ปิดการแจ้งเตือนพร้อมเหตุผล ข้อความเก่ายังอยู่ในประวัติการแก้ไข จึงต้องเปลี่ยนค่าเสมอ ไม่ใช่แค่ลบออก</li>
      </ol>
      {alerts === null ? <Empty>กำลังโหลด…</Empty> : visible.length === 0 ? (
        <Empty>{show === "open" ? "ไม่มีการแจ้งเตือนที่ยังไม่ปิด" : "ยังไม่เคยพบรหัสลับในระบบนี้"}</Empty>
      ) : (
        <ul className="space-y-2">
          {visible.map((a) => (
            <li key={a.id} className={`rounded-lg border p-3 ${a.status === "open" ? "border-rose-200 bg-rose-50/40" : "border-slate-200 bg-slate-50"}`}>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityTag severity={a.severity} />
                <span className="font-medium text-slate-900">{a.rule_label}</span>
                <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700 ring-1 ring-slate-200">{a.preview}</code>
                {a.status === "open" ? (
                  <Tag value={a.still_present ? "ยังอยู่ในข้อความ" : "ลบออกจากข้อความแล้ว"} severity={a.still_present ? "danger" : "warning"} />
                ) : (
                  <Tag value={`ปิดแล้ว: ${resolutionLabel(a.resolution)}`} severity="success" />
                )}
                <span className="ml-auto">
                  {a.status === "open" ? (
                    <Button label="ปิดการแจ้งเตือน" size="small" outlined
                      onClick={() => setClosing({ alert: a, resolution: a.still_present ? "false_positive" : "revoked", note: "" })} />
                  ) : (
                    <Button label="เปิดอีกครั้ง" size="small" text onClick={() => resolve(a, null)} />
                  )}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                พบที่ {a.location_label}{a.line ? ` บรรทัด ${a.line}` : ""} · ครั้งแรก {formatDateTime(a.first_seen_at)}
                {" "}({a.source === "save" ? "ตอนบันทึก" : a.source === "scheduled" ? "การตรวจตามรอบ" : "การตรวจที่ผู้ดูแลสั่ง"})
                {a.status === "resolved" && <> · ปิดโดย {a.resolved_by} {formatDateTime(a.resolved_at)}{a.resolution_note && `: ${a.resolution_note}`}</>}
              </p>
            </li>
          ))}
        </ul>
      )}

      <Dialog header="ปิดการแจ้งเตือน" visible={closing !== null} onHide={() => setClosing(null)} className="w-full max-w-lg" footer={
        closing && (
          <div className="flex justify-end gap-2">
            <Button label="ยกเลิก" text onClick={() => setClosing(null)} />
            <Button label="ปิดการแจ้งเตือน" icon="pi pi-check" onClick={() => resolve(closing.alert, closing.resolution, closing.note)} />
          </div>
        )
      }>
        {closing && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">{closing.alert.rule_label} <code>{closing.alert.preview}</code> ที่ {closing.alert.location_label}</p>
            <label className="block text-sm">
              เหตุผล
              <Dropdown value={closing.resolution} options={meta.alert_resolutions} optionLabel="label" optionValue="key"
                onChange={(e) => setClosing({ ...closing, resolution: e.value })} className="mt-1 flex w-full" />
            </label>
            {(closing.resolution === "false_positive" || closing.resolution === "used_in_tests") && (
              <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900">
                เหตุผลนี้จะทำให้ทุกคนเห็นข้อความนั้นอีกครั้ง เลือกเฉพาะเมื่อแน่ใจว่าไม่ใช่รหัสที่ใช้งานได้จริง
              </p>
            )}
            {closing.resolution === "moved_to_vault" && closing.alert.still_present && (
              <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900">ข้อความนี้ยังอยู่ในระบบ ลบออกจากข้อความก่อนปิด</p>
            )}
            <label className="block text-sm">
              หมายเหตุ
              <InputText value={closing.note} onChange={(e) => setClosing({ ...closing, note: e.target.value })} maxLength={500}
                className="mt-1 w-full" placeholder="เช่น เปลี่ยน token ใน GitLab แล้วเมื่อ 11 พ.ย." />
            </label>
          </div>
        )}
      </Dialog>
    </Card>
  );
}

/** The system's secrets vault and its leak alerts. Shown only to its people (and admins). */
export default function SecurityTab({ system, onChange }: { system: SystemDetail; onChange: () => void }) {
  return (
    <div className="space-y-4">
      <AlertsCard system={system} onChange={onChange} />
      <VaultCard system={system} />
    </div>
  );
}
