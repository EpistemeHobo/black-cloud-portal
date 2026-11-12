// In production the frontend and API share an origin. During `next dev`, set
// NEXT_PUBLIC_API_BASE=http://localhost:8000 and ALLOWED_ORIGINS on the backend.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class ApiError extends Error {
  /** A machine-readable reason, when the backend sends one (e.g. "unverified"). */
  constructor(public status: number, message: string, public code?: string, public findings?: SecretFinding[]) {
    super(message);
  }
}

/** Something that looks like a secret, in a save the backend refused (code "secret_detected"). */
export type SecretFinding = { rule: string; label: string; severity: string; location: string; line: number; preview: string };

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // {code, message}: a reason the page acts on, plus the text to show.
    if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
    // FastAPI validation errors: a list of {msg, loc}.
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((d) => String(d?.msg ?? "").replace(/^Value error, /, ""))
        .filter(Boolean)
        .join(" ");
    }
  }
  return `เกิดข้อผิดพลาด (HTTP ${status})`;
}

type Options = { method?: string; body?: unknown };

/**
 * Calls the API. A save the backend refuses because it seems to contain a secret
 * (push protection, backend/app/leak_scan.py) asks the person, here, once for
 * every form: remove it, or save anyway, which the owners are then alerted about.
 */
export async function api<T>(path: string, options: Options = {}): Promise<T> {
  try {
    return await request<T>(path, options);
  } catch (e) {
    if (!(e instanceof ApiError) || e.code !== "secret_detected" || !e.findings || typeof window === "undefined") throw e;
    const list = e.findings
      .map((f) => `• ${f.label} (${f.preview}) ที่ ${f.location}${f.line ? ` บรรทัด ${f.line}` : ""}`)
      .join("\n");
    const go = window.confirm(
      `${e.message}\n\n${list}\n\n` +
      "ถ้าเป็นรหัสจริง กด \"ยกเลิก\" แล้วลบออกจากข้อความ จากนั้นเก็บไว้ในแท็บ \"รหัสลับและความปลอดภัย\" ของระบบ\n" +
      "ถ้าไม่ใช่รหัสลับ กด \"ตกลง\" เพื่อบันทึก พอร์ทัลจะซ่อนข้อความนั้นจากคนนอกทีมและแจ้งเจ้าของระบบ",
    );
    if (!go) throw e;
    return request<T>(`${path}${path.includes("?") ? "&" : "?"}allow_secrets=true`, options);
  }
}

async function request<T>(path: string, options: Options): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    credentials: "include",
    headers: options.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, messageFrom(body, res.status), body?.detail?.code, body?.detail?.findings);
  return body as T;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("th-TH", { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("th-TH", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
