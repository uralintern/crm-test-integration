import { CheckOutlined, DownOutlined, DownloadOutlined } from "@ant-design/icons";
import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { Dropdown } from "antd";
import type { MenuProps } from "antd";
import { getSpecializations } from "../../../../../api/specializations";
import { exportEventApplicationsXlsx, exportEventDetailsDocx, getEventById, removeEvent as archiveEvent, saveEvent as persistEvent } from "../../../api/events";
import { getRequests } from "../../../../requests/api/requests";
import { getAllUsers } from "../../../../../storage/storage";
import type { Event } from "../../../../../types/event";
import type { User } from "../../../../../types/user";
import AppButton from "../../../../../components/UI/Button";
import DateField, { DateRangeField } from "../../../../../components/UI/DateField";
import AppInput, { AppTextArea } from "../../../../../components/UI/Input";
import Modal from "../../../../../components/Modal/Modal";
import AppSelect from "../../../../../components/UI/Select";
import { useToast } from "../../../../../components/Toast/ToastProvider";
import { AuthContext } from "../../../../../context/AuthContext";
import { isGlobalOrganizer } from "../../../../../utils/access";
import { useWizard } from "../EventWizardModal";
import {
  CREATE_DRAFT_KEY,
  FieldWrap,
  extractVkPeerId,
  extractErrorMessage,
  getUserLabel,
  normalizeDateFieldValue,
  readCreateDraft,
  type EventDraft,
  type SaveState,
  type SpecializationOption,
} from "./EventForm.helpers";
export default function EventForm() {
  const { mode, saveEvent, savedEvent, eventId } = useWizard();
  const seededEvent = savedEvent as Event | undefined;
  const seededEventRef = useRef<Event | undefined>(seededEvent);
  const { showToast } = useToast();
  const { user: currentUser } = useContext(AuthContext);
  const canManageEventOrganizers = isGlobalOrganizer(currentUser);

  const [loadedEvent, setLoadedEvent] = useState<Event | null>(seededEvent ?? null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState(seededEvent?.description ?? "");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [applyDeadline, setApplyDeadline] = useState("");
  const [orgChatUrl, setOrgChatUrl] = useState("");
  const [orgChatPeerId, setOrgChatPeerId] = useState("");
  const [selectedOrganizerIds, setSelectedOrganizerIds] = useState<string[]>([]);
  const [selectedOrganizerId, setSelectedOrganizerId] = useState("");
  const [availableSpecializations, setAvailableSpecializations] = useState<SpecializationOption[]>([]);
  const [specializations, setSpecializations] = useState<SpecializationOption[]>([]);
  const [selectedSpecializationIds, setSelectedSpecializationIds] = useState<string[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [usersList, setUsersList] = useState<User[]>([]);
  const [applicantUserIds, setApplicantUserIds] = useState<Set<number>>(new Set());
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [savedSnapshot, setSavedSnapshot] = useState("");
  const [initialized, setInitialized] = useState(false);
  const [exporting, setExporting] = useState(false);

  const editableEventId = mode === "edit" ? eventId : undefined;
  const organizers = useMemo(() => {
    const eligible = usersList.filter((user) => {
      const role = String(user.role || "").toLowerCase();
      return user.isSuperuser || user.isStaff || role === "organizer" || applicantUserIds.has(Number(user.id));
    });

    return eligible.sort((a, b) => {
      if (Boolean(a.isSuperuser) !== Boolean(b.isSuperuser)) return a.isSuperuser ? -1 : 1;
      if (Boolean(a.isStaff) !== Boolean(b.isStaff)) return a.isStaff ? -1 : 1;
      return getUserLabel(a).localeCompare(getUserLabel(b), "ru");
    });
  }, [applicantUserIds, usersList]);

  const formSnapshot = useMemo(
    () =>
      JSON.stringify({
        title,
        description,
        startDate,
        endDate,
        applyDeadline,
        orgChatUrl,
        orgChatPeerId,
        selectedOrganizerIds,
        specializations,
      }),
    [applyDeadline, description, endDate, orgChatPeerId, orgChatUrl, selectedOrganizerIds, specializations, startDate, title]
  );

  useEffect(() => {
    let mounted = true;

    (async () => {
      const loadedSpecializations = await getSpecializations();
      if (mounted) setAvailableSpecializations(loadedSpecializations);
    })();

    return () => {
      mounted = false;
    };
  }, []);
  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const users = await getAllUsers();
        const normalized = (users || []).map((user) => {
          const raw = user as User & Record<string, unknown>;
          return {
            ...raw,
            name: raw.name ?? String(raw.firstName ?? raw.first_name ?? ""),
            surname: raw.surname ?? String(raw.lastName ?? raw.last_name ?? ""),
          };
        });

        if (mounted) setUsersList(normalized as User[]);
      } catch {
        if (mounted) setUsersList([]);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (mode !== "edit" || !editableEventId) {
        setApplicantUserIds(new Set());
        return;
      }

      try {
        const requests = await getRequests();
        if (!mounted) return;
        setApplicantUserIds(
          new Set(
            requests
              .filter((request) => Number(request.eventId) === Number(editableEventId) && Number(request.ownerId) > 0)
              .map((request) => Number(request.ownerId))
          )
        );
      } catch {
        if (mounted) setApplicantUserIds(new Set());
      }
    })();

    return () => {
      mounted = false;
    };
  }, [editableEventId, mode]);

  useEffect(() => {
    let mounted = true;

    const fillState = (event: Event) => {
      setLoadedEvent(event);
      setTitle(event.title || "");
      setDescription(event.description || "");
      setStartDate(normalizeDateFieldValue(event.startDate));
      setEndDate(normalizeDateFieldValue(event.endDate));
      setApplyDeadline(normalizeDateFieldValue(event.applyDeadline));
      setOrgChatUrl(event.orgChatUrl || "");
      setOrgChatPeerId(event.orgChatPeerId ? String(event.orgChatPeerId) : "");
      setSelectedOrganizerIds((event.organizerIds?.length ? event.organizerIds : event.leader ? [event.leader] : []).map(String));
      setSelectedOrganizerId("");
      setSpecializations((event.specializations || []).map((item) => ({ id: item.id, title: item.title })));
      setSelectedSpecializationIds((event.specializations || []).map((item) => String(item.id)));
      setSaveState("idle");
      setSavedSnapshot("");
      setInitialized(true);
    };

    (async () => {
      if (seededEventRef.current) {
        fillState(seededEventRef.current);
        return;
      }

      if (mode === "edit" && editableEventId) {
        try {
          const event = await getEventById(Number(editableEventId));
          if (!mounted || !event) return;
          fillState(event);
        } catch {
          return;
        }
        return;
      }

      if (mode === "create") {
        const draft = readCreateDraft();
        setLoadedEvent(null);
        setTitle(draft?.title ?? "");
        setDescription(draft?.description ?? "");
        setStartDate(draft?.startDate ?? "");
        setEndDate(draft?.endDate ?? "");
        setApplyDeadline(draft?.applyDeadline ?? "");
        setOrgChatUrl(draft?.orgChatUrl ?? "");
        setOrgChatPeerId(draft?.orgChatPeerId ?? "");
        setSelectedOrganizerIds(draft?.organizerIds ?? []);
        setSelectedOrganizerId("");
        setSpecializations(draft?.specializations ?? []);
        setSelectedSpecializationIds((draft?.specializations ?? []).map((item) => String(item.id)));
        setSaveState("idle");
        setSavedSnapshot("");
        setInitialized(true);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [editableEventId, mode]);

  useEffect(() => {
    if (mode !== "create" || !initialized) return;

    const draft: EventDraft = {
      title,
      description,
      startDate,
      endDate,
      applyDeadline,
      orgChatUrl,
      orgChatPeerId,
      organizerIds: selectedOrganizerIds,
      specializations,
    };

    localStorage.setItem(CREATE_DRAFT_KEY, JSON.stringify(draft));
  }, [applyDeadline, description, endDate, initialized, mode, orgChatPeerId, orgChatUrl, selectedOrganizerIds, specializations, startDate, title]);

  useEffect(() => {
    if (saveState !== "idle" && savedSnapshot && savedSnapshot !== formSnapshot) {
      setSaveState("idle");
    }
  }, [formSnapshot, saveState, savedSnapshot]);

  const handleSpecializationSelect = (value: string | number) => {
    const selectedId = String(value);
    const option = availableSpecializations.find((item) => Number(item.id) === Number(selectedId));
    if (!option) return;

    setSelectedSpecializationIds((prev) =>
      prev.some((id) => Number(id) === Number(selectedId)) ? prev : [...prev, selectedId]
    );
    setSpecializations((prev) =>
      prev.some((item) => Number(item.id) === Number(selectedId))
        ? prev
        : [...prev, { id: option.id, title: option.title }]
    );
    setErrors((prev) => {
      const next = { ...prev };
      delete next.specializations;
      return next;
    });
  };

  const addOrganizer = () => {
    if (!selectedOrganizerId) return;

    setSelectedOrganizerIds((prev) => {
      if (prev.some((id) => String(id) === String(selectedOrganizerId))) return prev;
      return [...prev, selectedOrganizerId];
    });

    setSelectedOrganizerId("");
    setErrors((prev) => {
      const next = { ...prev };
      delete next.organizers;
      return next;
    });
  };

  const removeOrganizer = (id: string) => {
    setSelectedOrganizerIds((prev) => prev.filter((organizerId) => String(organizerId) !== String(id)));
  };

  const removeSpecialization = (id: number) => {
    setSpecializations((prev) => prev.filter((item) => Number(item.id) !== Number(id)));
    setSelectedSpecializationIds((prev) => prev.filter((itemId) => Number(itemId) !== Number(id)));
  };

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    const trimmedTitle = title.trim();

    if (!trimmedTitle) nextErrors.title = "Заполните поле";
    if (!startDate) nextErrors.startDate = "Заполните поле";
    if (!endDate) nextErrors.endDate = "Заполните поле";
    if (!applyDeadline) nextErrors.applyDeadline = "Заполните поле";
    if (canManageEventOrganizers && !selectedOrganizerIds.length) nextErrors.organizers = "Выберите хотя бы одного организатора";
    if (!specializations.length) nextErrors.specializations = "Выберите хотя бы одну специализацию";

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;

    const computedStatus = new Date(endDate) >= new Date() ? "Активно" : "Неактивно";
    const organizerPayload = canManageEventOrganizers
      ? {
          leader: selectedOrganizerIds[0],
          organizerIds: selectedOrganizerIds,
          organizer: selectedOrganizerIds
            .map((id) => organizers.find((organizer) => String(organizer.id) === String(id)))
            .filter((organizer): organizer is User => Boolean(organizer))
            .map(getUserLabel)
            .join(", "),
        }
      : {};

    const payload: Event = {
      ...(loadedEvent ?? {}),
      id: mode === "edit" && eventId ? Number(eventId) : loadedEvent?.id ?? 0,
      title: title.trim(),
      description: description.trim(),
      startDate,
      endDate,
      applyDeadline,
      orgChatUrl: orgChatUrl.trim(),
      orgChatPeerId: orgChatPeerId ? Number(orgChatPeerId) : 0,
      ...organizerPayload,
      specializations,
      status: computedStatus,
      applicationFormFields: loadedEvent?.applicationFormFields,
    };

    if (!canManageEventOrganizers) {
      delete payload.leader;
      delete payload.organizerIds;
      delete payload.organizer;
    }

    try {
      const saved = await persistEvent(payload);
      setLoadedEvent(saved);
      saveEvent?.(saved);
      setSavedSnapshot(formSnapshot);
      setSaveState("synced");
      if (mode === "create") localStorage.removeItem(CREATE_DRAFT_KEY);
      showToast("success", mode === "edit" ? "Данные мероприятия обновлены" : "Мероприятие сохранено");
    } catch (error) {
      showToast("error", extractErrorMessage(error));
    }
  };

  const handleArchive = async () => {
    if (!eventId) {
      showToast("error", "Невозможно архивировать мероприятие: id не найден");
      return;
    }

    try {
      await archiveEvent(Number(eventId));
      setConfirmOpen(false);
      window.dispatchEvent(new CustomEvent("events:archived", { detail: { eventId: Number(eventId) } }));
      showToast("info", "Мероприятие занесено в архив, данные сохранены");
    } catch {
      showToast("error", "Ошибка при архивировании мероприятия");
    }
  };

  const isSynced = saveState === "synced";
  const hasPersistedEvent = mode === "edit" || Boolean(loadedEvent?.id);
  const currentEventId = Number(loadedEvent?.id ?? eventId ?? 0) || 0;
  const saveButtonLabel = isSynced
    ? mode === "edit"
      ? "Изменения сохранены"
      : "Мероприятие сохранено"
    : hasPersistedEvent
      ? "Сохранить изменения"
      : "Сохранить мероприятие";

  const exportMenuItems: MenuProps["items"] = [
    { key: "applications-xlsx", label: "Экспорт заявок xlsx" },
    { key: "details-docx", label: "Экспорт данных мероприятия docx" },
  ];

  const handleExport = async (kind: string) => {
    if (!currentEventId) {
      showToast("error", "Сначала сохраните мероприятие.");
      return;
    }

    setExporting(true);
    try {
      if (kind === "applications-xlsx") {
        await exportEventApplicationsXlsx(currentEventId);
      } else {
        await exportEventDetailsDocx(currentEventId);
      }
      showToast("success", "Файл экспорта сформирован");
    } catch (error) {
      showToast("error", extractErrorMessage(error));
    } finally {
      setExporting(false);
    }
  };

  const handleExportMenuClick: NonNullable<MenuProps["onClick"]> = ({ key }) => {
    void handleExport(String(key));
  };

  return (
    <div className="wizard-form">
      <h2 className="h2">{mode === "create" ? "Добавление мероприятия" : "Редактирование мероприятия"}</h2>

      <FieldWrap name="title" errors={errors}>
        <label className="text-small">
          <span className="wizard-field-label">Название мероприятия</span>
          <AppInput value={title} onChange={(event) => setTitle(event.target.value)} autoComplete="off" spellCheck={false} />
        </label>
      </FieldWrap>

      <label className="text-small">
        <span className="wizard-field-label">Описание</span>
        <AppTextArea value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>

      <label className="text-small">
        <span className="wizard-field-label">Ссылка на организационный чат VK</span>
        <AppInput
          value={orgChatUrl}
          onChange={(event) => setOrgChatUrl(event.target.value)}
          placeholder="https://vk.me/join/..."
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <label className="text-small">
        <span className="wizard-field-label">ID беседы VK для проверки вступления</span>
        <AppInput
          value={orgChatPeerId}
          onChange={(event) => setOrgChatPeerId(extractVkPeerId(event.target.value))}
          placeholder="2000000223 или ссылка из адресной строки беседы"
          autoComplete="off"
          spellCheck={false}
        />
      </label>

      <div className="date-row">
        <div className={`field-wrap ${errors.startDate || errors.endDate ? "error" : ""}`}>
          <DateRangeField
            className="app-date-range-field--compact"
            label="Дата начала и завершения"
            startValue={startDate}
            endValue={endDate}
            placeholders={["Дата начала", "Дата завершения"]}
            onChange={(nextStartDate, nextEndDate) => {
              setStartDate(nextStartDate);
              setEndDate(nextEndDate);
            }}
          />
          {(errors.startDate || errors.endDate) && <div className="field-error">{errors.startDate || errors.endDate}</div>}
        </div>

        <FieldWrap name="applyDeadline" errors={errors}>
          <DateField label="Срок приёма заявок" value={applyDeadline} onChange={setApplyDeadline} placeholder="Срок приёма" />
        </FieldWrap>
      </div>

      <FieldWrap name="organizers" errors={errors}>
        <label className="text-small">
          <span className="wizard-field-label">Организаторы мероприятия</span>
          <div className="wizard-inline-add-row wizard-inline-add-row--specializations">
            <AppSelect
              tone="event"
              value={selectedOrganizerId}
              onChange={(value) => setSelectedOrganizerId(String(value))}
              showSearch
              optionFilterProp="label"
              disabled={!canManageEventOrganizers}
              options={[
                { value: "", label: "Выберите организатора" },
                ...organizers.map((organizer) => ({
                  value: String(organizer.id),
                  label: getUserLabel(organizer),
                })),
              ]}
            />
            <AppButton
              className="primary wizard-inline-add-button wizard-inline-add-button--event"
              type="button"
              onClick={addOrganizer}
              disabled={!canManageEventOrganizers || !selectedOrganizerId}
            >
              Добавить
            </AppButton>
          </div>
        </label>
      </FieldWrap>

      {!canManageEventOrganizers && mode === "edit" && (
        <div className="event-organizers-hint">Менять организаторов может только главный организатор.</div>
      )}
      <div className="tags">
        {selectedOrganizerIds.map((organizerId) => {
          const organizer = organizers.find((item) => String(item.id) === String(organizerId));
          return (
            <div key={organizerId} className="tag">
              {organizer ? getUserLabel(organizer) : `Организатор #${organizerId}`}
              {canManageEventOrganizers && (
                <AppButton
                  className="tag-remove"
                  type="button"
                  onClick={() => removeOrganizer(organizerId)}
                  aria-label="Удалить организатора"
                >
                  x
                </AppButton>
              )}
            </div>
          );
        })}
      </div>

      <FieldWrap name="specializations" errors={errors}>
        <label className="text-small">
          <span className="wizard-field-label">Специализации</span>
          <AppSelect
            tone="event"
            value={undefined}
            onSelect={(value) => {
              if (Array.isArray(value)) return;
              handleSpecializationSelect(value);
            }}
            placeholder={specializations.length ? "Добавить специализацию" : "Выберите специализации"}
            showSearch
            optionFilterProp="label"
            options={availableSpecializations.map((specialization) => ({
              value: String(specialization.id),
              label: specialization.title,
              disabled: selectedSpecializationIds.some((id) => Number(id) === Number(specialization.id)),
            }))}
          />
        </label>
      </FieldWrap>

      <div className="tags">
        {specializations.map((specialization) => (
          <div key={specialization.id} className="tag">
            {specialization.title}
            <AppButton
              className="tag-remove"
              type="button"
              onClick={() => removeSpecialization(specialization.id)}
              aria-label="Удалить специализацию"
            >
              x
            </AppButton>
          </div>
        ))}
      </div>

      <div className="wizard-actions">
        {mode === "edit" && canManageEventOrganizers && (
          <AppButton className="danger-outline" onClick={() => setConfirmOpen(true)} style={{ marginRight: "auto" }}>
            Удалить
          </AppButton>
        )}


        {mode === "edit" && (
          <Dropdown
            menu={{ items: exportMenuItems, onClick: handleExportMenuClick }}
            trigger={["hover"]}
            disabled={exporting || !currentEventId}
          >
            <AppButton className="secondary wizard-export-btn" type="button" disabled={exporting || !currentEventId}>
              <DownloadOutlined />
              {exporting ? "Экспорт..." : "Экспорт"}
              <DownOutlined />
            </AppButton>
          </Dropdown>
        )}

        <AppButton className="primary" onClick={handleSave} type="button" disabled={isSynced}>
          {isSynced && <CheckOutlined />}
          {saveButtonLabel}
        </AppButton>
      </div>

      <Modal isOpen={confirmOpen} onClose={() => setConfirmOpen(false)} title="Подтвердите действие">
        <div style={{ padding: 8 }}>
          <div>
            Мероприятие будет перенесено в архив. Заявки, команды и данные планировщика сохранятся, но перестанут
            отображаться до восстановления из архива.
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <AppButton className="close-btn" onClick={() => setConfirmOpen(false)}>
              Отмена
            </AppButton>
            <AppButton className="danger-outline" onClick={handleArchive}>
              Архивировать
            </AppButton>
          </div>
        </div>
      </Modal>

    </div>
  );
}


