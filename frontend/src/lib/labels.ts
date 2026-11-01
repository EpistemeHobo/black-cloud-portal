import type { Meta } from "./types";

/** The Thai display label for a stored English value (system type, state, choice…), or the value itself. */
export function choiceLabel(meta: Meta | null, value: string): string {
  return meta?.choice_labels?.[value] ?? value;
}

/** Dropdown/MultiSelect options that show Thai labels but keep the stored English value. */
export function choiceOptions(values: string[] | undefined, label: (value: string) => string) {
  return (values ?? []).map((v) => ({ label: label(v), value: v }));
}
