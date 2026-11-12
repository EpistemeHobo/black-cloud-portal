"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Column } from "primereact/column";
import { DataTable } from "primereact/datatable";
import { Dropdown } from "primereact/dropdown";
import { IconField } from "primereact/iconfield";
import { InputIcon } from "primereact/inputicon";
import { InputText } from "primereact/inputtext";
import { SelectButton } from "primereact/selectbutton";
import { Tag } from "primereact/tag";
import { DebtStatusTag, RiskTag } from "@/components/bits";
import { api, formatDate } from "@/lib/api";
import { choiceOptions } from "@/lib/labels";
import { useSession } from "@/lib/session";
import type { TechDebt } from "@/lib/types";

type Row = TechDebt & { system: { id: string; name: string; criticality: string | null } };

/** Every system's technical debt in one list, for planning across systems. */
export default function DebtPage() {
  const { meta, label, notify } = useSession();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [show, setShow] = useState<"open" | "all">("open");
  const [risk, setRisk] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api<Row[]>("/api/tech-debt").then(setRows).catch((e) => notify("error", "โหลดหนี้ทางเทคนิคไม่สำเร็จ", e.message));
  }, [notify]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (rows ?? []).filter((r) =>
      (show === "all" || r.status === "open" || r.status === "in_progress") &&
      (!risk || r.risk === risk) &&
      (!q || [r.title, r.system.name, r.system.id, r.description].some((v) => v?.toLowerCase().includes(q))),
    );
  }, [rows, show, risk, search]);

  const open = (rows ?? []).filter((r) => r.status === "open" || r.status === "in_progress");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="page-title metal-ink">หนี้ทางเทคนิค</h1>
        <p className="text-slate-600">
          ทางลัดที่แต่ละระบบเลือกใช้โดยตั้งใจ พร้อมแผนการแก้ ค้างอยู่ {open.length} รายการ
          {" "}(ความเสี่ยงสูง {open.filter((r) => r.risk === "High").length}, เลยกำหนด {open.filter((r) => r.overdue).length})
          {" "}เพิ่มหรือแก้ไขได้ที่แท็บหนี้ทางเทคนิคของแต่ละระบบ
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <IconField iconPosition="left" className="min-w-64 flex-1">
          <InputIcon className="pi pi-search" />
          <InputText value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ค้นหาชื่อรายการหรือระบบ…" className="w-full" />
        </IconField>
        <Dropdown value={risk} onChange={(e) => setRisk(e.value)} showClear placeholder="ทุกระดับความเสี่ยง"
          options={choiceOptions(meta.debt_risks, label)} optionLabel="label" optionValue="value" />
        <SelectButton value={show} onChange={(e) => e.value && setShow(e.value)} allowEmpty={false}
          options={[{ label: "ยังค้างอยู่", value: "open" }, { label: "ทั้งหมด", value: "all" }]} />
      </div>

      <DataTable value={visible} loading={rows === null} dataKey="id" stripedRows size="small" paginator rows={50}
        emptyMessage="ไม่มีหนี้ทางเทคนิคที่ตรงกับตัวกรอง" className="rounded-lg border border-slate-200 bg-white">
        <Column header="ระบบ" body={(r: Row) => (
          <Link href={`/system/?id=${encodeURIComponent(r.system.id)}&tab=debt`} className="font-medium text-sky-700 hover:underline">
            {r.system.name}
          </Link>
        )} />
        <Column header="รายการ" body={(r: Row) => (
          <div>
            <p className="font-medium text-slate-900">{r.title}</p>
            {r.impact && <p className="line-clamp-2 text-xs text-slate-500">ถ้าปล่อยไว้: {r.impact}</p>}
          </div>
        )} />
        <Column header="ความเสี่ยง" body={(r: Row) => <RiskTag risk={r.risk} />} />
        <Column header="สถานะ" body={(r: Row) => <DebtStatusTag status={r.status} />} />
        <Column header="กำหนดแก้" body={(r: Row) => (
          <span className="flex items-center gap-2 whitespace-nowrap text-sm">
            {r.target_date ? formatDate(r.target_date) : "–"}
            {r.overdue && <Tag value="เลยกำหนด" severity="danger" />}
          </span>
        )} />
        <Column header="แรงที่ต้องใช้" body={(r: Row) => <span className="text-sm text-slate-600">{r.effort ?? "–"}</span>} />
      </DataTable>
    </div>
  );
}
