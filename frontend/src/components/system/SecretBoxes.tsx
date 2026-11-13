"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "primereact/button";
import { Checkbox } from "primereact/checkbox";
import { Dialog } from "primereact/dialog";
import { InputText } from "primereact/inputtext";
import { InputTextarea } from "primereact/inputtextarea";
import { Tag } from "primereact/tag";
import { Card, Empty } from "@/components/bits";
import { api, ApiError, formatDate, formatDateTime } from "@/lib/api";
import {
  cryptoAvailable, decryptVersion, downloadText, encryptVersion, findKey, generateKey, keyFileText, keyId,
  keyOpens, makeKeyCheck, newBoxUid,
} from "@/lib/boxCrypto";
import { useSession } from "@/lib/session";
import type { BoxVersion, SecretBox, SecretBoxes, SystemDetail } from "@/lib/types";

// An open box locks itself after this long: the key and contents leave memory.
const AUTO_LOCK_MINUTES = 10;

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));
const safeName = (s: string) => s.replace(/[^\p{L}\p{N}._-]+/gu, "-").replace(/^-+|-+$/g, "") || "box";

/**
 * The new key, shown once: copy or download it, and confirm it's kept before going on.
 * The portal never sees it again.
 */
function KeyReveal({ keyText, id, systemName, boxName, saved, onSaved }: {
  keyText: string; id: string; systemName: string; boxName: string; saved: boolean; onSaved: (v: boolean) => void;
}) {
  const { notify } = useSession();
  return (
    <div className="space-y-3">
      <div className="rounded-md bg-slate-900 p-3">
        <p className="text-xs text-slate-400">กุญแจ (รหัส {id})</p>
        <p className="mt-1 break-all font-mono text-sm text-emerald-200">{keyText}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button label="คัดลอกกุญแจ" icon="pi pi-copy" size="small" outlined onClick={async () => {
          await navigator.clipboard.writeText(keyText);
          notify("success", "คัดลอกแล้ว", "วางลงในโปรแกรมจัดการรหัสผ่านของคุณ");
        }} />
        <Button label="ดาวน์โหลดไฟล์กุญแจ" icon="pi pi-download" size="small" outlined
          onClick={() => downloadText(`${safeName(systemName)}-${safeName(boxName)}.key.txt`, keyFileText(keyText, id, systemName, boxName))} />
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
        <li><b>พอร์ทัลไม่ได้เก็บกุญแจนี้</b> และจะไม่แสดงอีก ถ้าทำหาย ไม่มีใครเปิดกล่องนี้ได้ รวมทั้งผู้ดูแลพอร์ทัล</li>
        <li>เก็บไว้ในโปรแกรมจัดการรหัสผ่าน และส่งต่อให้ผู้รับช่วงต่อด้วยฟีเจอร์แชร์ของโปรแกรมนั้นหรือบอกด้วยตัวเอง อย่าส่งทางแชทหรืออีเมล</li>
        <li>อย่าวางกุญแจในหน้าใดของพอร์ทัล พอร์ทัลจะแจ้งเตือนว่ากุญแจรั่ว</li>
      </ul>
      <label className="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
        <Checkbox checked={saved} onChange={(e) => onSaved(!!e.checked)} className="mt-0.5" />
        <span>ฉันเก็บกุญแจไว้แล้ว และต้นฉบับของรหัสลับในกล่องนี้ยังอยู่ที่อื่นด้วย (เช่น ไฟล์ .env ที่ไม่ขึ้น Git)</span>
      </label>
    </div>
  );
}

function ContentView({ text }: { text: string }) {
  const { notify } = useSession();
  const [shown, setShown] = useState(false);
  return (
    <div className="mt-2 rounded-md bg-slate-900 p-2">
      <div className="mb-1 flex justify-end gap-1">
        <Button label={shown ? "ซ่อน" : "แสดง"} icon={shown ? "pi pi-eye-slash" : "pi pi-eye"} size="small" text
          className="!text-slate-200" onClick={() => setShown(!shown)} />
        <Button icon="pi pi-copy" size="small" text rounded className="!text-slate-200" aria-label="คัดลอกทั้งหมด"
          onClick={async () => {
            await navigator.clipboard.writeText(text);
            notify("success", "คัดลอกแล้ว", "อย่าวางค่าเหล่านี้ในแชท เอกสาร หรือหน้าอื่นของพอร์ทัล");
          }} />
      </div>
      <pre className={`max-h-80 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-emerald-200 ${shown ? "" : "select-none blur-sm"}`}>
        {text || "(กล่องว่าง)"}
      </pre>
    </div>
  );
}

/** One box: locked until someone gives its key; then its contents, versions and key. */
function BoxRow({ box, system, canUse, base, onChange, setData }: {
  box: SecretBox; system: SystemDetail; canUse: boolean; base: string; onChange: () => void;
  setData: (d: SecretBoxes) => void;
}) {
  const { notify } = useSession();
  const url = `${base}/${box.id}`;
  const [key, setKey] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState<string | null>(null);
  const [content, setContent] = useState<{ version: number; text: string } | null>(null);
  const [editing, setEditing] = useState<{ text: string; note: string } | null>(null);
  const [versions, setVersions] = useState<BoxVersion[] | null>(null);
  const [viewing, setViewing] = useState<{ version: number; text: string } | null>(null);
  const [newKey, setNewKey] = useState<{ key: string; id: string; saved: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const lock = useCallback(() => {
    setKey(null); setContent(null); setEditing(null); setViewing(null); setVersions(null); setNewKey(null);
  }, []);
  // Forget the key after a while, and when the page goes away.
  useEffect(() => {
    if (!key) return;
    const timer = setTimeout(() => { lock(); notify("info", `ล็อกกล่อง ${box.name} แล้ว`, "ครบเวลาเปิดค้างไว้"); }, AUTO_LOCK_MINUTES * 60_000);
    return () => clearTimeout(timer);
  }, [key, lock, notify, box.name]);

  async function readVersion(k: string, version: number): Promise<string> {
    const v = await api<{ ciphertext: string }>(`${url}/versions/${version}`);
    return decryptVersion(k, box.uid, version, v.ciphertext);
  }

  async function unlock(text: string) {
    setBusy(true);
    try {
      const k = findKey(text);
      if (!(await keyOpens(k, box.uid, box.key_check))) throw new Error(`กุญแจนี้ไม่ใช่ของกล่องนี้ (กล่องนี้ใช้กุญแจรหัส ${box.key_id})`);
      setContent({ version: box.current_version, text: await readVersion(k, box.current_version) });
      setKey(k);
      setKeyInput(null);
      api(`${url}/opened`, { method: "POST" }).then(onChange).catch(() => undefined);
    } catch (e) {
      notify("error", "เปิดกล่องไม่สำเร็จ", errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function save(text: string, note: string) {
    if (!key || !content) return;
    setBusy(true);
    try {
      const next = content.version + 1;
      const ciphertext = await encryptVersion(key, box.uid, next, text);
      setData(await api<SecretBoxes>(`${url}/versions`, {
        method: "POST", body: { expected_version: content.version, ciphertext, note: note.trim() || null },
      }));
      setContent({ version: next, text });
      setEditing(null); setViewing(null); setVersions(null);
      notify("success", `บันทึกเป็นเวอร์ชัน ${next} แล้ว`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        notify("error", "มีคนบันทึกกล่องนี้ก่อนคุณ", "ล็อกแล้วเปิดกล่องใหม่เพื่อดูค่าล่าสุด แล้วแก้อีกครั้ง");
        onChange();
      } else {
        notify("error", "บันทึกไม่สำเร็จ", errorText(e));
      }
    } finally {
      setBusy(false);
    }
  }

  async function showVersions() {
    try {
      setVersions(versions ? null : await api<BoxVersion[]>(`${url}/versions`));
    } catch (e) {
      notify("error", "โหลดประวัติไม่สำเร็จ", errorText(e));
    }
  }

  async function view(version: number) {
    if (!key) return;
    try {
      setViewing({ version, text: await readVersion(key, version) });
    } catch (e) {
      notify("error", "เปิดเวอร์ชันนี้ไม่สำเร็จ", errorText(e));
    }
  }

  async function startKeyChange() {
    const k = generateKey();
    setNewKey({ key: k, id: await keyId(k), saved: false });
  }

  async function changeKey() {
    if (!key || !newKey) return;
    setBusy(true);
    try {
      // Every version, decrypted with the old key and encrypted again with the new one.
      const all = await api<{ current_version: number; versions: { version: number; ciphertext: string }[] }>(`${url}/ciphertexts`);
      const versionsOut = [];
      for (const v of all.versions) {
        const text = await decryptVersion(key, box.uid, v.version, v.ciphertext);
        versionsOut.push({ version: v.version, ciphertext: await encryptVersion(newKey.key, box.uid, v.version, text) });
      }
      setData(await api<SecretBoxes>(`${url}/key`, {
        method: "PUT",
        body: { expected_version: all.current_version, key_id: newKey.id, key_check: await makeKeyCheck(newKey.key, box.uid), versions: versionsOut },
      }));
      setKey(newKey.key);
      setNewKey(null);
      notify("success", "เปลี่ยนกุญแจแล้ว", "กุญแจเดิมเปิดกล่องนี้ไม่ได้อีก ส่งกุญแจใหม่ให้คนที่ยังอยู่ในทีม");
    } catch (e) {
      notify("error", "เปลี่ยนกุญแจไม่สำเร็จ", errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`ลบกล่อง "${box.name}" และทุกเวอร์ชันหรือไม่?\n\nลบแล้วกู้คืนไม่ได้ ตรวจว่าต้นฉบับยังอยู่ที่อื่นก่อน`)) return;
    try {
      setData(await api<SecretBoxes>(url, { method: "DELETE" }));
      notify("success", `ลบกล่อง ${box.name} แล้ว`);
    } catch (e) {
      notify("error", "ลบไม่สำเร็จ", errorText(e));
    }
  }

  return (
    <li className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <i className={`pi ${key ? "pi-lock-open text-emerald-600" : "pi-lock text-slate-400"}`} aria-hidden />
        <span className="font-semibold text-slate-900">{box.name}</span>
        <Tag value={`เวอร์ชัน ${box.current_version}`} severity="info" />
        <span className="font-mono text-xs text-slate-500" title="รหัสกุญแจ: บอกว่ากุญแจที่ถืออยู่ใช่ของกล่องนี้หรือไม่">กุญแจ {box.key_id}</span>
        {canUse && (
          <span className="ml-auto flex flex-wrap gap-1">
            {key ? (
              <Button label="ล็อก" icon="pi pi-lock" size="small" text onClick={lock} />
            ) : (
              <Button label="เปิดกล่อง" icon="pi pi-key" size="small" outlined disabled={!cryptoAvailable()}
                onClick={() => setKeyInput(keyInput === null ? "" : null)} />
            )}
            <Button icon="pi pi-trash" text rounded size="small" severity="secondary" aria-label="ลบกล่อง" onClick={remove} />
          </span>
        )}
      </div>
      {box.description && <p className="mt-1 text-sm text-slate-600">{box.description}</p>}
      {box.left_since_key_change.length > 0 && (
        <p className="mt-2 rounded-md bg-amber-50 p-2 text-xs text-amber-900">
          <i className="pi pi-exclamation-triangle mr-1" aria-hidden />
          {box.left_since_key_change.join(", ")} ออกจากทีมหลังเปลี่ยนกุญแจครั้งล่าสุด และอาจยังมีกุญแจอยู่: เปิดกล่องแล้วกด &quot;เปลี่ยนกุญแจ&quot;
          {" "}และเปลี่ยนรหัสลับที่ต้นทางถ้าคนนั้นเคยเห็น
        </p>
      )}
      <p className="mt-1 text-xs text-slate-500">
        สร้างโดย {box.created_by ?? "–"} {formatDate(box.created_at)} · เปลี่ยนกุญแจล่าสุด {formatDate(box.key_changed_at)}
        {box.last_opened_at ? <> · เปิดล่าสุด {formatDateTime(box.last_opened_at)} โดย {box.last_opened_by}</> : <> · ยังไม่มีใครเปิด</>}
      </p>

      {keyInput !== null && !key && (
        <form className="mt-2 flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); unlock(keyInput); }}>
          <InputText type="password" value={keyInput} onChange={(e) => setKeyInput(e.target.value)} autoFocus autoComplete="off"
            placeholder="วางกุญแจ pvk1_…" className="min-w-64 flex-1 font-mono text-sm" />
          <Button type="submit" label="เปิด" size="small" loading={busy} disabled={!keyInput.trim()} />
          <Button type="button" label="ใช้ไฟล์กุญแจ" icon="pi pi-file" size="small" text onClick={() => fileRef.current?.click()} />
          <input ref={fileRef} type="file" accept=".txt,.key,text/plain" className="hidden"
            onChange={async (e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unlock(await f.text()); }} />
          <p className="w-full text-xs text-slate-500">กุญแจใช้ในเบราว์เซอร์นี้เท่านั้น ไม่ถูกส่งไปที่พอร์ทัล และจะถูกลืมเมื่อล็อก ปิดหน้า หรือครบ {AUTO_LOCK_MINUTES} นาที</p>
        </form>
      )}

      {key && content && (
        <div className="mt-2">
          {editing ? (
            <div className="space-y-2">
              <InputTextarea value={editing.text} onChange={(e) => setEditing({ ...editing, text: e.target.value })} rows={8} autoResize
                spellCheck={false} autoComplete="off" className="w-full font-mono text-sm" />
              <InputText value={editing.note} onChange={(e) => setEditing({ ...editing, note: e.target.value })} maxLength={300}
                className="w-full" placeholder="เปลี่ยนอะไร (ไม่บังคับ ไม่ถูกเข้ารหัส: อย่าใส่ค่าใด ๆ) เช่น เปลี่ยน SMTP key" />
              <div className="flex justify-end gap-2">
                <Button label="ยกเลิก" text size="small" onClick={() => setEditing(null)} />
                <Button label={`บันทึกเป็นเวอร์ชัน ${content.version + 1}`} icon="pi pi-check" size="small" loading={busy}
                  disabled={editing.text === content.text} onClick={() => save(editing.text, editing.note)} />
              </div>
            </div>
          ) : (
            <>
              <ContentView text={content.text} />
              <div className="mt-2 flex flex-wrap gap-1">
                <Button label="แก้ไข" icon="pi pi-pencil" size="small" text onClick={() => setEditing({ text: content.text, note: "" })} />
                <Button label={versions ? "ซ่อนประวัติ" : "ประวัติเวอร์ชัน"} icon="pi pi-history" size="small" text onClick={showVersions} />
                <Button label="เปลี่ยนกุญแจ" icon="pi pi-refresh" size="small" text onClick={startKeyChange} />
              </div>
            </>
          )}
          {versions && (
            <ol className="mt-2 space-y-1 border-l-2 border-slate-200 pl-3 text-sm">
              {versions.map((v) => (
                <li key={v.version} className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">เวอร์ชัน {v.version}</span>
                  <span className="text-xs text-slate-500">{formatDateTime(v.created_at)} · {v.created_by}</span>
                  {v.note && <span className="text-xs text-slate-700">“{v.note}”</span>}
                  <Button label="ดู" size="small" text className="!py-0" onClick={() => view(v.version)} />
                </li>
              ))}
            </ol>
          )}
          {viewing && (
            <div className="mt-2 rounded-md border border-slate-200 p-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium">เวอร์ชัน {viewing.version}</span>
                <span className="ml-auto flex gap-1">
                  {viewing.version !== content.version && (
                    <Button label="ใช้เวอร์ชันนี้" size="small" outlined loading={busy}
                      onClick={() => save(viewing.text, `คืนค่าจากเวอร์ชัน ${viewing.version}`)} />
                  )}
                  <Button icon="pi pi-times" size="small" text rounded aria-label="ปิด" onClick={() => setViewing(null)} />
                </span>
              </div>
              <ContentView text={viewing.text} />
            </div>
          )}
        </div>
      )}

      <Dialog header={`เปลี่ยนกุญแจของกล่อง ${box.name}`} visible={newKey !== null} onHide={() => setNewKey(null)} className="w-full max-w-lg"
        footer={
          <div className="flex justify-end gap-2">
            <Button label="ยกเลิก" text onClick={() => setNewKey(null)} />
            <Button label="เปลี่ยนกุญแจ" icon="pi pi-check" loading={busy} disabled={!newKey?.saved} onClick={changeKey} />
          </div>
        }>
        {newKey && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              ทุกเวอร์ชันของกล่องจะถูกเข้ารหัสใหม่ในเบราว์เซอร์นี้ด้วยกุญแจใหม่ กุญแจเดิม ({box.key_id}) จะเปิดกล่องนี้ไม่ได้อีก
              ใช้เมื่อมีคนออกจากทีมหรือกุญแจอาจรั่ว แล้วส่งกุญแจใหม่ให้คนที่ยังอยู่
            </p>
            <KeyReveal keyText={newKey.key} id={newKey.id} systemName={system.name} boxName={box.name}
              saved={newKey.saved} onSaved={(saved) => setNewKey({ ...newKey, saved })} />
          </div>
        )}
      </Dialog>
    </li>
  );
}

type Draft = { name: string; description: string; text: string; note: string };

/** Make a box: fill it, then see its new key once, then it is encrypted here and uploaded. */
function CreateBox({ system, base, onCreated, onClose }: {
  system: SystemDetail; base: string; onCreated: (d: SecretBoxes) => void; onClose: () => void;
}) {
  const { notify } = useSession();
  const [draft, setDraft] = useState<Draft>({ name: "", description: "", text: "", note: "" });
  const [key, setKey] = useState<{ key: string; id: string; saved: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  async function next() {
    const k = generateKey();
    setKey({ key: k, id: await keyId(k), saved: false });
  }

  async function create() {
    if (!key) return;
    setBusy(true);
    try {
      const uid = newBoxUid();
      onCreated(await api<SecretBoxes>(base, {
        method: "POST",
        body: {
          uid, name: draft.name.trim(), description: draft.description.trim() || null, key_id: key.id,
          key_check: await makeKeyCheck(key.key, uid), ciphertext: await encryptVersion(key.key, uid, 1, draft.text),
          note: draft.note.trim() || null,
        },
      }));
      notify("success", `สร้างกล่อง ${draft.name} แล้ว`, "เก็บกุญแจไว้ให้ดี พอร์ทัลแสดงกุญแจนี้ครั้งเดียว");
      onClose();
    } catch (e) {
      notify("error", "สร้างกล่องไม่สำเร็จ", errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog header={key ? "กุญแจของกล่องนี้" : "สร้างกล่องรหัสลับ"} visible onHide={onClose} className="w-full max-w-2xl"
      footer={
        <div className="flex justify-end gap-2">
          {key ? <Button label="ย้อนกลับ" text onClick={() => setKey(null)} /> : <Button label="ยกเลิก" text onClick={onClose} />}
          {key
            ? <Button label="เข้ารหัสและสร้างกล่อง" icon="pi pi-lock" loading={busy} disabled={!key.saved} onClick={create} />
            : <Button label="ถัดไป: สร้างกุญแจ" icon="pi pi-arrow-right" iconPos="right" disabled={!draft.name.trim()} onClick={next} />}
        </div>
      }>
      {key ? (
        <KeyReveal keyText={key.key} id={key.id} systemName={system.name} boxName={draft.name}
          saved={key.saved} onSaved={(saved) => setKey({ ...key, saved })} />
      ) : (
        <div className="space-y-3">
          <label className="block text-sm">
            ชื่อกล่อง
            <InputText value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} maxLength={100} autoFocus
              className="mt-1 w-full" placeholder="เช่น prod .env, staging .env, บัญชีผู้ดูแลระบบภายนอก" />
          </label>
          <label className="block text-sm">
            ใช้ทำอะไร (ไม่ถูกเข้ารหัส)
            <InputText value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} maxLength={500}
              className="mt-1 w-full" placeholder="เช่น ค่าตั้งค่าของเครื่องจริง ใช้ตอนติดตั้งใหม่" />
          </label>
          <label className="block text-sm">
            เนื้อหา (ถูกเข้ารหัสในเบราว์เซอร์นี้ก่อนส่ง)
            <InputTextarea value={draft.text} onChange={(e) => setDraft({ ...draft, text: e.target.value })} rows={8} autoResize
              spellCheck={false} autoComplete="off" className="mt-1 w-full font-mono text-sm"
              placeholder={"DB_PASSWORD=...\nSMTP_PASSWORD=...\n# หรือวางไฟล์ .env ทั้งไฟล์"} />
          </label>
          <label className="block text-sm">
            หมายเหตุของเวอร์ชันนี้ (ไม่บังคับ ไม่ถูกเข้ารหัส)
            <InputText value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} maxLength={300}
              className="mt-1 w-full" placeholder="เช่น คัดลอกจาก .env ของเครื่องจริง 12 พ.ย." />
          </label>
        </div>
      )}
    </Dialog>
  );
}

/** The system's secret boxes. Contents are encrypted in the browser with keys only people hold. */
export default function SecretBoxesCard({ system }: { system: SystemDetail }) {
  const { notify } = useSession();
  const [data, setData] = useState<SecretBoxes | null>(null);
  const [creating, setCreating] = useState(false);
  const base = `/api/systems/${encodeURIComponent(system.id)}/boxes`;

  const load = useCallback(() => {
    api<SecretBoxes>(base).then(setData).catch((e) => notify("error", "โหลดกล่องรหัสลับไม่สำเร็จ", e.message));
  }, [base, notify]);
  useEffect(load, [load]);

  const canUse = data?.can_use ?? false;
  const available = cryptoAvailable();

  return (
    <Card
      title={<><i className="pi pi-lock text-slate-500" aria-hidden />กล่องรหัสลับ</>}
      actions={canUse && available && <Button label="สร้างกล่อง" icon="pi pi-plus" size="small" outlined onClick={() => setCreating(true)} />}
    >
      <p className="-mt-1 mb-3 text-sm text-slate-600">
        เก็บรหัสผ่าน คีย์ API และไฟล์ .env ของระบบไว้ในกล่อง แทนการเขียนลงคู่มือหรือไฟล์แนบ แต่ละกล่องมีกุญแจของตัวเอง
        ที่สร้างในเบราว์เซอร์และไม่เคยถูกส่งมาที่พอร์ทัล ทุกครั้งที่บันทึกจะเก็บเป็นเวอร์ชันใหม่
      </p>
      <p className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <i className="pi pi-info-circle mr-1" aria-hidden />
        <b>เก็บต้นฉบับไว้ที่อื่นเสมอ</b> เช่น ไฟล์ .env ที่ไม่ขึ้น Git หรือโปรแกรมจัดการรหัสผ่าน พอร์ทัลเป็นสำเนาสำรองสำหรับส่งต่องาน
        ไม่ใช่ที่เก็บหลัก และกู้คืนกุญแจที่หายให้ไม่ได้
      </p>
      {!available && (
        <p className="mb-3 rounded-md bg-rose-50 p-3 text-sm text-rose-900">
          เบราว์เซอร์นี้เข้ารหัสไม่ได้ เพราะไม่ได้เปิดพอร์ทัลผ่าน HTTPS เปิดผ่านที่อยู่ HTTPS ของพอร์ทัลเพื่อใช้กล่องรหัสลับ
        </p>
      )}
      {data === null ? <Empty>กำลังโหลด…</Empty> : data.items.length === 0 ? (
        <Empty>ยังไม่มีกล่องรหัสลับ</Empty>
      ) : (
        <ul className="space-y-2">
          {data.items.map((b) => (
            <BoxRow key={b.id} box={b} system={system} canUse={canUse} base={base} onChange={load} setData={setData} />
          ))}
        </ul>
      )}
      {data && (
        <div className="mt-4 border-t border-slate-100 pt-3 text-sm">
          <p className="font-medium text-slate-700">ผู้ที่ดาวน์โหลดกล่องได้</p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {data.access.map((p) => (
              <li key={p.email} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                {p.name} <span className="text-slate-500">· {p.roles.join(", ")}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">
            คือเจ้าของ ผู้ดูแลสำรอง และนักพัฒนาของระบบ (แก้ได้ในคำถาม &quot;ถามใครได้บ้าง&quot; ของคู่มือ) การเปิดกล่องต้องมีกุญแจของกล่องนั้นด้วย
            ผู้ดูแลพอร์ทัลเห็นเฉพาะชื่อกล่องและประวัติ
            {!canUse && " คุณเห็นหน้านี้ในฐานะผู้ดูแลพอร์ทัล"}
          </p>
        </div>
      )}
      {creating && <CreateBox system={system} base={base} onCreated={setData} onClose={() => setCreating(false)} />}
    </Card>
  );
}
