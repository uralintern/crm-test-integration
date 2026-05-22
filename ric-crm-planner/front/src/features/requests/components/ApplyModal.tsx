import { useContext, useEffect, useMemo, useState } from "react";
import client from "../../../api/client";
import { getDirectionsByEvent } from "../../events/api/directions";
import { normalizeApplicationFormFields, SYSTEM_APPLICATION_FIELD_IDS } from "../../../constants/applicationForm";
import { REQUEST_STATUS } from "../../../constants/requestProgress";
import { AuthContext } from "../../../context/AuthContext";
import type { ApplicationFormField } from "../../../types/event";
import type { Direction } from "../../../types/direction";
import type { Request } from "../../../types/request";
import Modal from "../../../components/Modal/Modal";
import { useToast } from "../../../components/Toast/ToastProvider";
import AppButton from "../../../components/UI/Button";
import AppInput, { AppTextArea } from "../../../components/UI/Input";
import AppSelect from "../../../components/UI/Select";
import { requireVKBotConfirmation } from "../../../components/VKBotConfirmation/VKBotConfirmationGuard";

type ProfileResponse = {
  vk?: string;
  telegram?: string;
  university?: string;
  course?: string | number;
  specialty?: string;
  about?: string;
};

function resolveProfileSpecialization(profileSpecialty: unknown, fallbackSpecialty: unknown, availableSpecializations: { title: string }[]) {
  const raw = String(profileSpecialty ?? fallbackSpecialty ?? "");
  const candidates = raw
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);

  const matched = candidates.find((candidate) =>
    availableSpecializations.some((specialization) => specialization.title === candidate)
  );

  return matched ?? availableSpecializations[0]?.title ?? candidates[0] ?? "";
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId?: number;
  projectTitle?: string;
  eventId?: number;
  eventTitle?: string;
  directionId?: number;
  specializations?: { id: number; title: string }[];
  applicationFormFields?: ApplicationFormField[];
  onSubmit: (req: Request) => boolean | Promise<boolean>;
}

export default function ApplyModal({
  isOpen,
  onClose,
  projectId,
  projectTitle,
  eventId,
  eventTitle,
  directionId,
  specializations = [],
  applicationFormFields,
  onSubmit,
}: Props) {
  const { user } = useContext(AuthContext);
  const { showToast } = useToast();

  const [studentName, setStudentName] = useState("");
  const [telegram, setTelegram] = useState("");
  const [university, setUniversity] = useState("");
  const [course, setCourse] = useState("");
  const [specialization, setSpecialization] = useState<string>(specializations[0]?.title || "");
  const [eventDirections, setEventDirections] = useState<Direction[]>([]);
  const [selectedDirectionId, setSelectedDirectionId] = useState("");
  const [customFields, setCustomFields] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const fields = useMemo(() => normalizeApplicationFormFields(applicationFormFields), [applicationFormFields]);
  const customApplicationFields = useMemo(
    () => fields.filter((field) => !SYSTEM_APPLICATION_FIELD_IDS.has(field.id)),
    [fields]
  );
  const labelById = useMemo(() => new Map(fields.map((field) => [field.id, field.label])), [fields]);
  const showDirectionSelect = !directionId && eventDirections.length > 0;

  useEffect(() => {
    if (!isOpen) return;
    let mounted = true;

    (async () => {
      try {
        const profile = user && !client.USE_MOCK ? await client.get<ProfileResponse>("/api/users/profile/") : undefined;
        const userRecord = (user ?? {}) as Record<string, unknown>;
        if (!mounted) return;

        setStudentName(user ? `${user.name || ""} ${user.surname || ""}`.trim() : "");
        setTelegram(String(profile?.vk ?? userRecord.vk ?? profile?.telegram ?? userRecord.telegram ?? ""));
        setUniversity(String(profile?.university ?? userRecord.university ?? ""));
        setCourse(String(profile?.course ?? userRecord.course ?? ""));
        setSpecialization(resolveProfileSpecialization(profile?.specialty, userRecord.specialty, specializations));
        setSelectedDirectionId("");
        setCustomFields(
          customApplicationFields.some((field) => field.id === "about")
            ? { about: String(profile?.about ?? userRecord.about ?? "") }
            : {}
        );
        setErrors({});
      } catch {
        if (!mounted) return;
        setStudentName(user ? `${user.name || ""} ${user.surname || ""}`.trim() : "");
        const userRecord = (user ?? {}) as Record<string, unknown>;
        setTelegram(String(userRecord.vk ?? userRecord.telegram ?? ""));
        setUniversity("");
        setCourse("");
        setSpecialization(resolveProfileSpecialization(undefined, userRecord.specialty, specializations));
        setSelectedDirectionId("");
        setCustomFields({});
        setErrors({});
      }
    })();

    return () => {
      mounted = false;
    };
  }, [customApplicationFields, isOpen, specializations, user]);

  useEffect(() => {
    if (!isOpen || !eventId) {
      setEventDirections([]);
      return;
    }

    let mounted = true;

    getDirectionsByEvent(Number(eventId))
      .then((items) => {
        if (mounted) setEventDirections(Array.isArray(items) ? items : []);
      })
      .catch(() => {
        if (mounted) setEventDirections([]);
      });

    return () => {
      mounted = false;
    };
  }, [eventId, isOpen]);

  const validate = () => {
    const nextErrors: Record<string, string> = {};

    if (!studentName.trim()) nextErrors.studentName = "Введите ФИО";
    if (!telegram.trim()) nextErrors.telegram = "Укажите аккаунт в ВК";
    if (!university.trim()) nextErrors.university = "Укажите университет";
    if (!course.trim()) nextErrors.course = "Укажите курс";
    if (!specialization.trim()) nextErrors.specialization = "Выберите специализацию";
    if (!eventId) nextErrors.event = "Не найдено мероприятие";
    if (showDirectionSelect && !selectedDirectionId) nextErrors.direction = "Выберите направление";

    customApplicationFields.forEach((field) => {
      if (field.required && !customFields[field.id]?.trim()) nextErrors[field.id] = "Заполните поле";
    });

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSend = () => {
    if (!validate()) {
      showToast("error", "Заполните обязательные поля.");
      return;
    }

    const selectedSpecialization = specializations.find((item) => item.title === specialization);
    const effectiveDirectionId = directionId ?? (selectedDirectionId ? Number(selectedDirectionId) : undefined);
    const selectedDirection = eventDirections.find((direction) => Number(direction.id) === Number(effectiveDirectionId));
    const filteredCustomFields = Object.fromEntries(
      Object.entries(customFields)
        .map(([key, value]) => [key, value.trim()])
        .filter(([, value]) => value)
    );

    const request: Request = {
      id: 0,
      studentName: studentName.trim(),
      telegram: telegram.trim(),
      university: university.trim(),
      course: course.trim(),
      projectId,
      projectTitle,
      eventId,
      eventTitle,
      directionId: effectiveDirectionId,
      directionTitle: selectedDirection?.title,
      specializationId: selectedSpecialization?.id,
      specialization,
      about: filteredCustomFields.about ?? "",
      customFields: filteredCustomFields,
      status: REQUEST_STATUS.SUBMITTED,
      createdAt: new Date().toISOString(),
      ownerId: user?.id,
    };

    const result = onSubmit(request);
    Promise.resolve(result).then((ok) => {
      if (ok) {
        requireVKBotConfirmation();
        onClose();
      }
    });
  };

  const clearError = (key: string) => {
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Подать заявку" hideActions>
      <div className="apply-form">
        <div className="apply-header">
          <div className="apply-project">{eventTitle || projectTitle || "Выбранное мероприятие"}</div>
        </div>

        <div className="form-body">
          <div className="form-field">
            <label className="text-small">{labelById.get("studentName") ?? "ФИО"}</label>
            <AppInput
              className="text-regular"
              value={studentName}
              onChange={(event) => {
                setStudentName(event.target.value);
                clearError("studentName");
              }}
              aria-invalid={!!errors.studentName}
            />
            {errors.studentName && <div className="field-error">{errors.studentName}</div>}
          </div>

          <div className="form-field">
            <label className="text-small">{labelById.get("telegram") ?? "Аккаунт в ВК"}</label>
            <AppInput
              className="text-regular"
              value={telegram}
              onChange={(event) => {
                setTelegram(event.target.value);
                clearError("telegram");
              }}
              aria-invalid={!!errors.telegram}
            />
            {errors.telegram && <div className="field-error">{errors.telegram}</div>}
          </div>

          <div className="form-field">
            <label className="text-small">{labelById.get("university") ?? "Университет"}</label>
            <AppInput
              className="text-regular"
              value={university}
              onChange={(event) => {
                setUniversity(event.target.value);
                clearError("university");
              }}
              aria-invalid={!!errors.university}
            />
            {errors.university && <div className="field-error">{errors.university}</div>}
          </div>

          <div className="form-field">
            <label className="text-small">{labelById.get("course") ?? "Курс"}</label>
            <AppInput
              className="text-regular"
              value={course}
              onChange={(event) => {
                setCourse(event.target.value);
                clearError("course");
              }}
              aria-invalid={!!errors.course}
            />
            {errors.course && <div className="field-error">{errors.course}</div>}
          </div>

          {showDirectionSelect && (
            <div className="form-field">
              <label className="text-small">Направление</label>
              <AppSelect
                className="text-regular"
                value={selectedDirectionId}
                onChange={(value) => {
                  setSelectedDirectionId(String(value));
                  clearError("direction");
                }}
                aria-invalid={!!errors.direction}
                options={[
                  { value: "", label: "Выберите направление" },
                  ...eventDirections.map((direction) => ({ value: String(direction.id), label: direction.title })),
                ]}
              />
              {errors.direction && <div className="field-error">{errors.direction}</div>}
            </div>
          )}

          <div className="form-field">
            <label className="text-small">{labelById.get("specialization") ?? "Специализация"}</label>
            <AppSelect
              className="text-regular"
              value={specialization}
              onChange={(value) => {
                setSpecialization(String(value));
                clearError("specialization");
              }}
              aria-invalid={!!errors.specialization}
              options={[
                { value: "", label: "-" },
                ...specializations.map((item) => ({ value: item.title, label: item.title })),
              ]}
            />
            {errors.specialization && <div className="field-error">{errors.specialization}</div>}
          </div>

          {customApplicationFields.map((field) => (
            <div className="form-field" key={field.id}>
              <label className="text-small">
                {field.label}
                {!field.required ? " (необязательно)" : ""}
              </label>
              {field.type === "textarea" ? (
                <AppTextArea
                  value={customFields[field.id] ?? ""}
                  onChange={(event) => {
                    setCustomFields((prev) => ({ ...prev, [field.id]: event.target.value }));
                    clearError(field.id);
                  }}
                />
              ) : field.type === "select" ? (
                <AppSelect
                  className="text-regular"
                  value={customFields[field.id] ?? ""}
                  onChange={(value) => {
                    setCustomFields((prev) => ({ ...prev, [field.id]: String(value) }));
                    clearError(field.id);
                  }}
                  aria-invalid={!!errors[field.id]}
                  options={[
                    { value: "", label: "Выберите значение" },
                    ...(field.options ?? []).map((option) => ({ value: option, label: option })),
                  ]}
                />
              ) : (
                <AppInput
                  className="text-regular"
                  value={customFields[field.id] ?? ""}
                  onChange={(event) => {
                    setCustomFields((prev) => ({ ...prev, [field.id]: event.target.value }));
                    clearError(field.id);
                  }}
                  aria-invalid={!!errors[field.id]}
                />
              )}
              {errors[field.id] && <div className="field-error">{errors[field.id]}</div>}
            </div>
          ))}
        </div>

        <div className="apply-actions">
          <AppButton type="button" className="apply-btn-cancel" onClick={onClose}>
            Отмена
          </AppButton>
          <AppButton type="button" className="apply-btn-send" onClick={handleSend}>
            Отправить
          </AppButton>
        </div>
      </div>
    </Modal>
  );
}


