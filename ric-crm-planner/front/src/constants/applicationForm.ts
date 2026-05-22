import type { ApplicationFormField } from "../types/event";

export const SYSTEM_APPLICATION_FIELD_IDS = new Set(["studentName", "telegram", "university", "course", "specialization"]);
const DEFAULT_APPLICATION_FIELD_IDS = new Set([...SYSTEM_APPLICATION_FIELD_IDS, "about"]);

export const DEFAULT_APPLICATION_FORM_FIELDS: ApplicationFormField[] = [
  {
    id: "studentName",
    label: "ФИО",
    type: "text",
    required: true,
    locked: true,
    system: true,
  },
  {
    id: "telegram",
    label: "Аккаунт в ВК",
    type: "text",
    required: true,
    locked: true,
    system: true,
  },
  {
    id: "university",
    label: "Университет",
    type: "text",
    required: true,
    locked: true,
    system: true,
  },
  {
    id: "course",
    label: "Курс",
    type: "text",
    required: true,
    locked: true,
    system: true,
  },
  {
    id: "specialization",
    label: "Специализация",
    type: "text",
    required: true,
    locked: true,
    system: true,
  },
  {
    id: "about",
    label: "О себе",
    type: "textarea",
    required: false,
    locked: false,
    system: false,
  },
];

function normalizeFieldType(type: unknown): ApplicationFormField["type"] {
  if (type === "textarea" || type === "select") return type;
  return "text";
}

function normalizeFieldOptions(options: unknown): string[] | undefined {
  if (!Array.isArray(options)) return undefined;

  const normalized = options.map((option) => String(option).trim()).filter(Boolean);
  return normalized.length > 0 ? normalized : undefined;
}

export function normalizeApplicationFormFields(fields?: ApplicationFormField[]): ApplicationFormField[] {
  const sourceFields = fields ?? [];
  const isInitialConfig = !fields || sourceFields.length === 0;
  const byId = new Map(sourceFields.map((field) => [field.id, field]));
  const normalizedDefaults = DEFAULT_APPLICATION_FORM_FIELDS.filter(
    (field) => field.locked || isInitialConfig || byId.has(field.id)
  ).map((field) => {
    const override = byId.get(field.id);

    if (!override) return field;

    if (field.locked) return field;

    return {
      ...field,
      label: override.label?.trim() || field.label,
      type: normalizeFieldType(override.type),
      options: normalizeFieldType(override.type) === "select" ? normalizeFieldOptions(override.options) : undefined,
      required: Boolean(override.required),
    };
  });

  const customFields = (fields ?? [])
    .filter((field) => field.id && !DEFAULT_APPLICATION_FIELD_IDS.has(field.id))
    .map<ApplicationFormField>((field) => ({
      id: field.id,
      label: field.label?.trim() || "Новое поле",
      type: normalizeFieldType(field.type),
      options: normalizeFieldType(field.type) === "select" ? normalizeFieldOptions(field.options) : undefined,
      required: Boolean(field.required),
      locked: false,
      system: false,
    }));

  return [...normalizedDefaults, ...customFields];
}
