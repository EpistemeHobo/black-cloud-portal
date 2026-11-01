export type Me = { id: number; name: string; email: string; is_admin: boolean; is_auditor: boolean };

export type FieldSpec = {
  key: string;
  label: string;
  type: "text" | "paragraph" | "choice" | "multi" | "date" | "number";
  choices?: string[];
  help?: string;
  restricted?: boolean;
};

export type Section = { key: string; title: string; fields: FieldSpec[] };
export type KeyLabel = { key: string; label: string };

export type Meta = {
  steps: { number: number; name: string }[];
  system_types: string[];
  lifecycle_states: string[];
  roles: KeyLabel[];
  link_kinds: KeyLabel[];
  checklist_statuses: KeyLabel[];
  review_places: string[];
  watch_out_kinds: KeyLabel[];
  chore_frequencies: KeyLabel[];
  open_item_kinds: KeyLabel[];
  sections: Section[];
  kb_base_url: string | null;
  /** Stored English values (system types, states, choices…) to Thai display labels. */
  choice_labels: Record<string, string>;
};

export type ChecklistSummary = { required_due: number; required_finished: number; open_codes: string[] };

export type SystemSummary = {
  id: string;
  name: string;
  type: string;
  step: number;
  lifecycle_state: string;
  unit: string | null;
  technical_owners: string[];
  criticality: string | null;
  description: string | null;
  checklist: ChecklistSummary;
  guide: { answered: number; total: number };
  updated_at: string | null;
};

export type GuideKey = "what" | "where" | "how" | "watch" | "deps" | "who" | "progress";

export type GuideQuestion = {
  key: GuideKey;
  title: string;
  can_be_empty: boolean;
  answered: boolean;
  /** Answered in the guide's own boxes and lists, not only by an attached file. */
  written: boolean;
  /** The writer marked it as having nothing to list. */
  nothing: boolean;
  updated_at: string | null;
  updated_by: string | null;
};

export type GuideFields = {
  description: string | null;
  if_down: string | null;
  run_steps: string | null;
  deploy_steps: string | null;
  rollback_steps: string | null;
};

/** A markdown file attached to one guide question. */
export type GuideDoc = {
  id: number;
  question: GuideKey;
  filename: string;
  content: string;
  updated_at: string | null;
  updated_by: string | null;
};

export type WatchOut = { id: number; kind: "trap" | "chore"; text: string; how_often: string | null; next_due: string | null };

export type OpenItem = {
  id: number;
  kind: "work" | "promise" | "decision";
  text: string;
  promised_to: string | null;
  due_date: string | null;
  done: boolean;
  done_at: string | null;
  done_by: string | null;
};

export type Role = {
  role: string;
  role_label: string;
  person: PersonRef;
  reachable_until: string | null;
  note: string | null;
  reachable: boolean;
};

export type PersonRef = { id: number; name: string; email: string };

export type SystemDetail = {
  id: string;
  name: string;
  type: string;
  step: number;
  step_name: string;
  lifecycle_state: string;
  owning_unit: { id: number; name: string } | null;
  guide_fields: GuideFields;
  guide: { questions: GuideQuestion[]; answered: number; total: number };
  watch_outs: WatchOut[];
  open_items: OpenItem[];
  docs: GuideDoc[];
  fields: Record<string, string | string[] | number | null>;
  hidden_fields: string[];
  roles: Role[];
  links: { id: number; kind: string; url: string; label: string | null }[];
  depends_on: { to_system_id: string | null; name: string; external: boolean; note: string | null }[];
  used_by: { system_id: string; name: string; note: string | null }[];
  bus_factor: number;
  checklist: ChecklistSummary;
  verified_at: string | null;
  verified_by: PersonRef | null;
  created_at: string | null;
  updated_at: string | null;
  can_edit: boolean;
  can_edit_catalog: boolean;
  /** Technical owners and admins only. */
  can_delete: boolean;
};

export type ChecklistRow = {
  code: string;
  category: string;
  title: string;
  from_step: number;
  level: "required" | "recommended";
  how_to_verify: string;
  kb_url: string | null;
  auto: boolean;
  due: boolean;
  status: string;
  evidence: string | null;
  updated_by: string | null;
  updated_at: string | null;
};

export type Checklist = { items: ChecklistRow[]; summary: ChecklistSummary };

export type ReviewNote = {
  id: number;
  review_date: string;
  place: string;
  step: number;
  note: string;
  reviewer: { id: number; name: string };
  can_delete: boolean;
};

export type HistoryRow = {
  changed_at: string;
  entity: string;
  entity_id: string;
  field: string;
  old_value: string | null;
  new_value: string | null;
  hidden: boolean;
  changed_by: string | null;
};

export type Person = {
  id: number;
  name: string;
  email: string;
  active: boolean;
  is_admin: boolean;
  is_auditor: boolean;
  unit: string | null;
  has_account: boolean;
};

export type AccountStatus = "no_account" | "pending" | "active" | "suspended";

/** A person as the admin users page sees them. */
export type Account = Person & {
  status: AccountStatus;
  email_verified: boolean;
  created_at: string;
  last_sign_in_at: string | null;
  locked: boolean;
};

export type Unit = { id: number; name: string };

export type AttentionReason = { code: string; severity: "high" | "medium" | "low"; label: string };

export type Dashboard = {
  attention: {
    id: string;
    name: string;
    type: string;
    step: number;
    criticality: string | null;
    unit: string | null;
    reasons: AttentionReason[];
  }[];
  overview: {
    total: number;
    live: number;
    in_development: number;
    required_due: number;
    required_finished: number;
    guide_answered: number;
    guide_total: number;
    by_step: { step: number; name: string; count: number }[];
    by_type: { label: string; count: number }[];
    by_unit: { label: string; count: number }[];
  };
  thresholds: { confirm_days: number; review_days: number };
};

