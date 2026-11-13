/**
 * Encrypting secret boxes in the browser, so the portal never sees a box's key
 * or its contents (backend/app/vault.py, docs/decisions/0009-secrets.md).
 *
 * - A key is 32 random bytes, written as `pvk1_` and 43 base64url characters. The
 *   prefix lets the leak scanner recognise a key pasted where it shouldn't be.
 * - Contents are encrypted with AES-256-GCM: a fresh 12-byte IV each time, and the
 *   box's uid and version number as additional data, so a ciphertext can't be
 *   moved to another box or version without failing to decrypt.
 * - A key check (a fixed text encrypted the same way) tells a wrong key apart.
 * - The key id, the first 8 hex characters of the key's SHA-256, lets people tell
 *   keys apart without showing them.
 *
 * Web Crypto works only on HTTPS (or localhost): cryptoAvailable() says whether it can.
 */

const PREFIX = "pvk1_";
const KEY_PATTERN = /pvk1_[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])/;
const CHECK_TEXT = "portal-box-key-check-v1";
const IV_BYTES = 12;

/** The key doesn't open this box (or the data was changed). */
export class WrongKeyError extends Error {
  constructor() {
    super("กุญแจนี้เปิดกล่องนี้ไม่ได้");
  }
}

/** The text given isn't a box key at all. */
export class KeyFormatError extends Error {
  constructor() {
    super("ไม่พบกุญแจในข้อความนี้ กุญแจขึ้นต้นด้วย pvk1_ และยาว 48 ตัวอักษร");
  }
}

export function cryptoAvailable(): boolean {
  return typeof window !== "undefined" && window.isSecureContext && !!window.crypto?.subtle;
}

function toBase64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function fromBase64(text: string): Uint8Array<ArrayBuffer> {
  const s = atob(text);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

const toBase64Url = (bytes: Uint8Array) => toBase64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromBase64Url = (text: string) => fromBase64(text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4));

/** A new random key. Shown to the person once; never sent to the portal. */
export function generateKey(): string {
  return PREFIX + toBase64Url(crypto.getRandomValues(new Uint8Array(32)));
}

/** The key in some text: pasted on its own, or the whole contents of a downloaded key file. */
export function findKey(text: string): string {
  const match = text.match(KEY_PATTERN);
  if (!match || fromBase64Url(match[0].slice(PREFIX.length)).length !== 32) throw new KeyFormatError();
  return match[0];
}

async function cryptoKey(key: string): Promise<CryptoKey> {
  const raw = fromBase64Url(findKey(key).slice(PREFIX.length));
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function keyId(key: string): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", fromBase64Url(findKey(key).slice(PREFIX.length))));
  return Array.from(digest.slice(0, 4), (b) => b.toString(16).padStart(2, "0")).join("");
}

export const newBoxUid = () => crypto.randomUUID();
const versionData = (uid: string, version: number) => `${uid}:v${version}`;
const checkData = (uid: string) => `${uid}:check`;

async function encrypt(key: string, data: string, text: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const sealed = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: new TextEncoder().encode(data) },
    await cryptoKey(key), new TextEncoder().encode(text),
  );
  const out = new Uint8Array(IV_BYTES + sealed.byteLength);
  out.set(iv);
  out.set(new Uint8Array(sealed), IV_BYTES);
  return toBase64(out);
}

async function decrypt(key: string, data: string, ciphertext: string): Promise<string> {
  const bytes = fromBase64(ciphertext);
  const k = await cryptoKey(key);
  try {
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: bytes.slice(0, IV_BYTES), additionalData: new TextEncoder().encode(data) },
      k, bytes.slice(IV_BYTES),
    );
    return new TextDecoder().decode(plain);
  } catch {
    throw new WrongKeyError();
  }
}

export const encryptVersion = (key: string, uid: string, version: number, text: string) =>
  encrypt(key, versionData(uid, version), text);
export const decryptVersion = (key: string, uid: string, version: number, ciphertext: string) =>
  decrypt(key, versionData(uid, version), ciphertext);
export const makeKeyCheck = (key: string, uid: string) => encrypt(key, checkData(uid), CHECK_TEXT);

/** Whether this key opens the box, judged by its key check alone. */
export async function keyOpens(key: string, uid: string, keyCheck: string): Promise<boolean> {
  try {
    return (await decrypt(key, checkData(uid), keyCheck)) === CHECK_TEXT;
  } catch {
    return false;
  }
}

/** The text of a key file to download: a few lines saying what it opens, then the key. */
export function keyFileText(key: string, id: string, systemName: string, boxName: string): string {
  return [
    `# กุญแจกล่องรหัสลับ "${boxName}" ของระบบ ${systemName} (Developer Portal)`,
    `# รหัสกุญแจ ${id} · สร้างเมื่อ ${new Date().toISOString().slice(0, 10)}`,
    "# พอร์ทัลไม่ได้เก็บกุญแจนี้และกู้คืนให้ไม่ได้ ส่งต่อด้วยโปรแกรมจัดการรหัสผ่านหรือด้วยตัวเอง อย่าส่งทางแชทหรืออีเมล",
    key,
    "",
  ].join("\n");
}

export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
