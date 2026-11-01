// Reads an exported system folder (as a .zip or as a picked folder) into what
// POST /api/systems/import expects. The layout is made by backend/app/transfer.py:
//   <root>/system.json
//   <root>/docs/<number>-<question>/<file>.md
import { strFromU8, unzipSync } from "fflate";
import type { GuideKey } from "./types";

const QUESTIONS: GuideKey[] = ["what", "where", "how", "watch", "deps", "who", "progress"];
// Generous but bounded, so a strange archive can't eat the browser's memory.
const MAX_FILE_BYTES = 1_000_000;
const MAX_FILES = 200;

export type ImportDoc = { question: GuideKey; filename: string; content: string };
export type ImportPayload = {
  data: {
    system: { name: string; type: string };
    people?: unknown[];
    links?: unknown[];
    watch_outs?: unknown[];
    open_items?: unknown[];
    [key: string]: unknown;
  };
  docs: ImportDoc[];
};
export type ParsedFolder = { payload: ImportPayload; skipped: string[] };

const wanted = (name: string) => /\.(json|md|markdown)$/i.test(name);

/** "3-how", "how" and "3" all mean the "how" question. */
function questionOf(dir: string): GuideKey | null {
  const m = /^(\d+)?-?([a-z]*)$/i.exec(dir.trim());
  if (!m) return null;
  const key = m[2].toLowerCase() as GuideKey;
  if (QUESTIONS.includes(key)) return key;
  const n = Number(m[1]);
  return !m[2] && n >= 1 && n <= QUESTIONS.length ? QUESTIONS[n - 1] : null;
}

export async function readZip(file: File): Promise<Map<string, string>> {
  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(new Uint8Array(await file.arrayBuffer()), {
      filter: (f) => wanted(f.name) && f.originalSize <= MAX_FILE_BYTES,
    });
  } catch {
    throw new Error("เปิดไฟล์ .zip นี้ไม่ได้ ไฟล์อาจเสียหาย");
  }
  const names = Object.keys(entries);
  if (names.length > MAX_FILES) throw new Error("ไฟล์ .zip นี้มีไฟล์มากเกินไป");
  return new Map(names.map((n) => [n.replace(/\\/g, "/"), strFromU8(entries[n])]));
}

export async function readFolder(files: FileList): Promise<Map<string, string>> {
  const picked = Array.from(files).filter((f) => wanted(f.name) && f.size <= MAX_FILE_BYTES);
  if (picked.length > MAX_FILES) throw new Error("โฟลเดอร์นี้มีไฟล์มากเกินไป");
  return new Map(await Promise.all(picked.map(async (f) => [f.webkitRelativePath || f.name, await f.text()] as [string, string])));
}

export function toPayload(files: Map<string, string>): ParsedFolder {
  // The shallowest system.json marks the folder's root.
  const jsonPath = [...files.keys()]
    .filter((p) => p.split("/").pop() === "system.json")
    .sort((a, b) => a.split("/").length - b.split("/").length)[0];
  if (!jsonPath) throw new Error("ไม่พบไฟล์ system.json ในโฟลเดอร์นี้");
  const root = jsonPath.slice(0, -"system.json".length);

  let data: ImportPayload["data"];
  try {
    data = JSON.parse(files.get(jsonPath)!);
  } catch {
    throw new Error("system.json ไม่ใช่ JSON ที่ถูกต้อง");
  }
  if (!data?.system?.name) throw new Error("system.json ไม่มีชื่อระบบ");

  const docs: ImportDoc[] = [];
  const skipped: string[] = [];
  for (const [path, content] of files) {
    if (!path.startsWith(`${root}docs/`) || !/\.(md|markdown)$/i.test(path)) continue;
    const parts = path.slice(root.length).split("/"); // ["docs", "3-how", "runbook.md"]
    const question = parts.length === 3 ? questionOf(parts[1]) : null;
    if (question) docs.push({ question, filename: parts[2], content });
    else skipped.push(path.slice(root.length));
  }
  return { payload: { data, docs }, skipped };
}
