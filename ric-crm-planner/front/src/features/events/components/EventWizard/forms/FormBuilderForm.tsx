import { useEffect, useState } from "react";
import { normalizeApplicationFormFields } from "../../../../../constants/applicationForm";
import { getEventById, saveEvent as persistEvent } from "../../../api/events";
import type { ApplicationFormField, Event } from "../../../../../types/event";
import AppButton from "../../../../../components/UI/Button";
import AppInput, { AppTextArea } from "../../../../../components/UI/Input";
import AppSelect from "../../../../../components/UI/Select";
import { useToast } from "../../../../../components/Toast/ToastProvider";
import { useWizard } from "../EventWizardModal";

function createField(): ApplicationFormField {
  return {
    id: `custom_${Date.now()}`,
    label: "Новое поле",
    type: "text",
    required: false,
    locked: false,
    system: false,
  };
}

function normalizeOptions(options?: string[]) {
  return (options ?? []).map((option) => option.trim()).filter(Boolean);
}

function getFieldType(value: unknown): ApplicationFormField["type"] {
  if (value === "textarea" || value === "select") return value;
  return "text";
}

export default function FormBuilderForm() {
  const { eventId, savedEvent, saveEvent } = useWizard();
  const { showToast } = useToast();
  const [baseEvent, setBaseEvent] = useState<Event | null>(savedEvent ?? null);
  const [fields, setFields] = useState<ApplicationFormField[]>(normalizeApplicationFormFields(savedEvent?.applicationFormFields));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (savedEvent) {
        setBaseEvent(savedEvent);
        setFields(normalizeApplicationFormFields(savedEvent.applicationFormFields));
        return;
      }

      if (!eventId) return;

      const event = await getEventById(Number(eventId)).catch(() => undefined);
      if (!mounted || !event) return;

      setBaseEvent(event);
      setFields(normalizeApplicationFormFields(event.applicationFormFields));
    })();

    return () => {
      mounted = false;
    };
  }, [eventId, savedEvent]);

  const updateField = (id: string, patch: Partial<ApplicationFormField>) => {
    setFields((prev) => prev.map((field) => (field.id === id ? { ...field, ...patch } : field)));
  };

  const updateFieldType = (field: ApplicationFormField, value: unknown) => {
    const type = getFieldType(value);

    updateField(field.id, {
      type,
      options: type === "select" ? (normalizeOptions(field.options).length ? normalizeOptions(field.options) : ["Вариант 1"]) : undefined,
    });
  };

  const removeField = (id: string) => {
    setFields((prev) => prev.filter((field) => field.id !== id));
  };

  const handleSave = async () => {
    const event = baseEvent ?? savedEvent;

    if (!event?.id && !eventId) {
      showToast("error", "Сначала сохраните мероприятие.");
      return;
    }

    const normalizedFields = fields.map((field) => {
      const type = getFieldType(field.type);
      return {
        ...field,
        label: field.label.trim() || "Новое поле",
        type,
        options: type === "select" ? normalizeOptions(field.options) : undefined,
      };
    });

    const invalidSelect = normalizedFields.find((field) => field.type === "select" && !field.options?.length);
    if (invalidSelect) {
      showToast("error", `Добавьте варианты для поля "${invalidSelect.label}"`);
      return;
    }

    setSaving(true);

    try {
      const saved = await persistEvent({
        ...(event ?? { id: Number(eventId) }),
        id: Number(event?.id ?? eventId),
        applicationFormFields: normalizedFields,
      } as Event);

      setBaseEvent(saved);
      setFields(normalizedFields);
      saveEvent?.(saved);
      showToast("success", "Настройки формы сохранены");
    } catch {
      showToast("error", "Не удалось сохранить настройки формы");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="wizard-form">
      <h2 className="h2">Конструктор формы заявки</h2>
      <p className="text-small">
        Дефолтные поля используются во всех заявках. Первые пять системных полей нельзя редактировать, поле «О себе»
        можно настроить.
      </p>

      <div className="wizard-form-list">
        {fields.map((field) => {
          const isLocked = Boolean(field.locked);
          const isSystem = Boolean(field.system);
          const canRemove = !isSystem;

          return (
            <div key={field.id} className="wizard-item-card">
              <div className="wizard-item-card__header">
                <strong>{field.label}</strong>
                {isLocked && <span className="wizard-item-card__badge">Системное</span>}
              </div>

              <label className="text-small">
                Название поля
                <AppInput
                  value={field.label}
                  disabled={isLocked}
                  onChange={(event) => updateField(field.id, { label: event.target.value })}
                />
              </label>

              <div className="wizard-inline-add-row">
                <label className="text-small">
                  Тип поля
                  <AppSelect
                    tone="event"
                    value={field.type}
                    disabled={isLocked}
                    onChange={(value) => updateFieldType(field, value)}
                    options={[
                      { value: "text", label: "Короткий текст" },
                      { value: "textarea", label: "Длинный текст" },
                      { value: "select", label: "Выпадающий список" },
                    ]}
                  />
                </label>

                <label className="text-small">
                  Обязательность
                  <AppSelect
                    tone="event"
                    value={field.required ? "required" : "optional"}
                    disabled={isLocked}
                    onChange={(value) => updateField(field.id, { required: value === "required" })}
                    options={[
                      { value: "optional", label: "Необязательное" },
                      { value: "required", label: "Обязательное" },
                    ]}
                  />
                </label>
              </div>

              {field.type === "select" && (
                <label className="text-small">
                  Варианты списка
                  <AppTextArea
                    value={(field.options ?? []).join("\n")}
                    disabled={isLocked}
                    placeholder={"Каждый вариант с новой строки\nНапример:\nFrontend\nBackend\nДизайн"}
                    onChange={(event) => updateField(field.id, { options: event.target.value.split(/\r?\n/) })}
                  />
                </label>
              )}

              {canRemove && (
                <AppButton className="danger-outline" type="button" onClick={() => removeField(field.id)}>
                  Удалить поле
                </AppButton>
              )}
            </div>
          );
        })}
      </div>

      <div className="wizard-actions">
        <AppButton
          className="close-btn"
          type="button"
          onClick={() => setFields((prev) => [...prev, createField()])}
        >
          Добавить поле
        </AppButton>
        <AppButton className="primary" type="button" onClick={handleSave} disabled={saving}>
          {saving ? "Сохранение..." : "Сохранить форму"}
        </AppButton>
      </div>
    </div>
  );
}


