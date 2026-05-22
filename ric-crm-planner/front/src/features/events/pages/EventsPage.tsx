import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../../../api/client";
import { createTestingSSOLink } from "../../../api/testing";
import { getEvents } from "../api/events";
import { getRequests as apiGetRequests, saveRequest, updateRequestStatus } from "../../requests/api/requests";
import EventWizardModal, { type WizardLaunchContext } from "../components/EventWizard/EventWizardModal";
import TableHeader from "../../../components/Layout/TableHeader";
import InfoModal from "../../../components/Modal/InfoModal";
import Modal from "../../../components/Modal/Modal";
import ApplyModal from "../../requests/components/ApplyModal";
import Table from "../../../components/Table/Table";
import { useToast } from "../../../components/Toast/ToastProvider";
import { buildMockRequestTransitionUrl, REQUEST_STATUS } from "../../../constants/requestProgress";
import { AuthContext } from "../../../context/AuthContext";
import { useNotifications } from "../../../context/NotificationsContext";
import { useSearchSubmitFeedback } from "../../../hooks/useSearchSubmitFeedback";
import type { Event } from "../../../types/event";
import type { Request as RequestType } from "../../../types/request";
import "../../../styles/page-colors.scss";
import AppButton from "../../../components/UI/Button";

interface TestingImportMetaEnv {
  VITE_TESTING_URL?: string;
}

const TESTING_BASE_URL =
  ((import.meta as ImportMeta & { env?: TestingImportMetaEnv }).env?.VITE_TESTING_URL || "").trim() || "https://example.com/testing";

function buildTestingUrl(req: RequestType) {
  try {
    const url = new URL(TESTING_BASE_URL, window.location.origin);
    if (req.id) url.searchParams.set("applicationId", String(req.id));
    if (req.eventId) url.searchParams.set("eventId", String(req.eventId));
    if (req.ownerId) url.searchParams.set("ownerId", String(req.ownerId));
    return url.toString();
  } catch {
    return TESTING_BASE_URL;
  }
}

function extractErrorMessage(error: unknown): string | undefined {
  if (!error) return undefined;
  if (typeof error === "string") return error;

  if (Array.isArray(error)) {
    const firstText = error.find((item) => typeof item === "string" && item.trim());
    return typeof firstText === "string" ? firstText : undefined;
  }

  if (typeof error !== "object") return undefined;

  const record = error as Record<string, unknown>;
  const preferredKeys = ["detail", "message", "event", "direction", "project", "specialization", "non_field_errors", "nonFieldErrors"];

  for (const key of preferredKeys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
    if (Array.isArray(value)) {
      const firstText = value.find((item) => typeof item === "string" && item.trim());
      if (typeof firstText === "string") return firstText;
    }
  }

  for (const value of Object.values(record)) {
    if (typeof value === "string" && value.trim()) return value;
    if (Array.isArray(value)) {
      const firstText = value.find((item) => typeof item === "string" && item.trim());
      if (typeof firstText === "string") return firstText;
    }
  }

  return undefined;
}

function isApplyDeadlineExpired(event?: Event | null): boolean {
  if (!event?.applyDeadline) return false;
  const deadline = new Date(event.applyDeadline);
  if (Number.isNaN(deadline.getTime())) return false;
  return deadline.getTime() < Date.now();
}

function filterEventsByQuery(items: Event[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return items;

  return items.filter(
    (event) =>
      (event.title || "").toLowerCase().includes(normalizedQuery) ||
      (event.organizer || "").toLowerCase().includes(normalizedQuery) ||
      (event.status || "").toLowerCase().includes(normalizedQuery)
  );
}

export default function EventsPage() {
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);
  const { showToast } = useToast();
  const { addNotification } = useNotifications();
  const isStudent = user?.role === "student";

  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardContext, setWizardContext] = useState<WizardLaunchContext | null>(null);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [search, setSearch] = useState("");
  const [allEvents, setAllEvents] = useState<Event[]>([]);
  const [requests, setRequests] = useState<RequestType[]>([]);
  const [applyOpen, setApplyOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [testingPromptOpen, setTestingPromptOpen] = useState(false);
  const [testingPromptStep, setTestingPromptStep] = useState<"ask" | "info">("ask");
  const [pendingRequest, setPendingRequest] = useState<RequestType | null>(null);

  const [infoOpen, setInfoOpen] = useState(false);
  const [infoItem, setInfoItem] = useState<{ title?: string; description?: string } | null>(null);

  const loadEvents = useCallback(async () => {
    try {
      const [events, loadedRequests] = await Promise.all([
        getEvents(),
        user ? apiGetRequests({ ownerId: user.id, role: user.role }).catch(() => []) : Promise.resolve([]),
      ]);
      setAllEvents(events || []);
      setRequests(Array.isArray(loadedRequests) ? loadedRequests : []);
    } catch {
      setAllEvents([]);
      setRequests([]);
    }
  }, [user]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    const handleArchived = (event: globalThis.Event) => {
      const eventId = Number((event as CustomEvent<{ eventId?: number }>).detail?.eventId);
      if (!eventId) return;

      setAllEvents((prev) => prev.filter((item) => Number(item.id) !== eventId));
      setRequests((prev) => prev.filter((item) => Number(item.eventId) !== eventId));
      setSelectedEvent((prev) => (Number(prev?.id) === eventId ? null : prev));
    };

    window.addEventListener("events:archived", handleArchived);
    return () => window.removeEventListener("events:archived", handleArchived);
  }, []);

  const refreshRequests = useCallback(async () => {
    if (!user) {
      setRequests([]);
      return;
    }
    const loadedRequests = await apiGetRequests({ ownerId: user.id, role: user.role }).catch(() => []);
    setRequests(Array.isArray(loadedRequests) ? loadedRequests : []);
  }, [user]);

  const events = useMemo(() => filterEventsByQuery(allEvents, search), [allEvents, search]);

  const { animatedIds: searchAnimatedIds, handleSearchSubmit } = useSearchSubmitFeedback({
    getMatches: (query) => filterEventsByQuery(allEvents, query),
    getId: (event) => event.id,
    notFoundMessage: "Такого мероприятия не существует!",
    showToast,
  });

  const hasRequestForEvent = useCallback(
    (eventId: number) => requests.some((request) => Number(request.ownerId) === Number(user?.id) && Number(request.eventId) === Number(eventId)),
    [requests, user?.id]
  );

  const closeTestingPrompt = () => {
    setTestingPromptOpen(false);
    setTestingPromptStep("ask");
    setPendingRequest(null);
  };

  const openLink = (url: string) => {
    const trimmed = url.trim();
    closeTestingPrompt();
    if (!trimmed) return;

    try {
      const nextUrl = new URL(trimmed, window.location.origin);
      if (nextUrl.origin === window.location.origin) {
        navigate(`${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`);
        return;
      }
    } catch {
      return;
    }

    window.location.assign(trimmed);
  };

  const startTestingScenario = async () => {
    if (!pendingRequest?.id) return;

    try {
      const link = client.USE_MOCK
        ? buildMockRequestTransitionUrl(Number(pendingRequest.id), REQUEST_STATUS.CHAT_LINK_SENT, "testing")
        : (await createTestingSSOLink(Number(pendingRequest.id))).url;

      await updateRequestStatus(Number(pendingRequest.id), REQUEST_STATUS.TESTING);

      addNotification({
        userId: user?.id,
        title: "Приглашение на тестирование",
        message: client.USE_MOCK
          ? "Откройте ссылку и подтвердите переход к следующему этапу."
          : "Для продолжения откройте ссылку и пройдите тест.",
        link,
      });

      await refreshRequests();
      openLink(link);
    } catch {
      showToast("error", "Не удалось запустить сценарий тестирования");
    }
  };

  const startDirectScenario = async () => {
    if (!pendingRequest?.id) return;

    const link = client.USE_MOCK
      ? buildMockRequestTransitionUrl(Number(pendingRequest.id), REQUEST_STATUS.STARTED, "start")
      : buildTestingUrl(pendingRequest);

    addNotification({
      userId: user?.id,
      title: "Ссылка для перехода к ПШ",
      message: "Ссылка для прохождения находится в центре уведомлений.",
      link,
    });

    setTestingPromptStep("info");
    await refreshRequests();
  };

  return (
    <div className="page page--events">
      <TableHeader
        title="Мероприятия"
        search={search}
        onSearch={setSearch}
        onSearchSubmit={handleSearchSubmit}
        onCreate={() => {
          setMode("create");
          setWizardContext({ type: "event" });
          setWizardOpen(true);
        }}
      />

      <Table
        columns={[
          { key: "title", title: "Название" },
          { key: "startDate", title: "Дата начала" },
          { key: "endDate", title: "Дата окончания" },
          { key: "organizer", title: "Организатор" },
          { key: "status", title: "Статус" },
          ...(isStudent ? [{ key: "apply", title: "Заявка", width: "190px" }] : []),
        ]}
        data={events}
        animatedIds={searchAnimatedIds}
        badgeKeys={["startDate", "endDate", "status"]}
        onRowClick={(row) => navigate(`/events/${row.id}/directions`)}
        onEdit={(row) => {
          setMode("edit");
          setWizardContext({ type: "event", eventId: row.id });
          setWizardOpen(true);
        }}
        onInfoClick={(row) => {
          setInfoItem({ title: row.title || "-", description: row.description || "Нет описания" });
          setInfoOpen(true);
        }}
        renderCell={(row, colKey) => {
          if (colKey !== "apply") return undefined;

          const event = row as Event;
          const eventId = Number(event.id);
          const alreadyApplied = hasRequestForEvent(eventId);
          const isEnrollmentClosed = String(event.status || "").trim().toLowerCase() === "набор завершен";
          const isApplyClosed = isApplyDeadlineExpired(event);

	          if (isEnrollmentClosed) {
	            return null;
	          }

          return (
            <AppButton
	              type="button"
	              variant={alreadyApplied || isApplyClosed ? "dashed" : undefined}
	              className={`event-apply-pill${alreadyApplied || isApplyClosed ? " event-apply-pill--submitted is-disabled" : ""}`}
	              disabled={alreadyApplied || isApplyClosed}
              onClick={(clickEvent) => {
                clickEvent.stopPropagation();
                if (alreadyApplied || isApplyClosed) return;
                setSelectedEvent(event);
                setApplyOpen(true);
              }}
            >
              {alreadyApplied ? "Заявка отправлена" : isApplyClosed ? "Прием заявок завершен" : "Подать заявку"}
            </AppButton>
          );
        }}
      />

      {wizardOpen && wizardContext && (
        <EventWizardModal
          mode={mode}
          context={wizardContext}
          onClose={() => {
            setWizardOpen(false);
            void loadEvents();
          }}
        />
      )}

      <ApplyModal
        isOpen={applyOpen}
        onClose={() => setApplyOpen(false)}
        eventId={selectedEvent?.id}
        eventTitle={selectedEvent?.title}
        specializations={selectedEvent?.specializations || []}
        applicationFormFields={selectedEvent?.applicationFormFields || []}
        onSubmit={async (request) => {
          if (!user?.id || !selectedEvent?.id) return false;
          if (isApplyDeadlineExpired(selectedEvent)) {
            showToast("error", "Прием заявок на это мероприятие уже завершен.");
            return false;
          }

          if (hasRequestForEvent(Number(selectedEvent.id))) {
            showToast("error", "Вы уже отправляли заявку на это мероприятие");
            return false;
          }

          try {
            const created = await saveRequest({
              ...request,
              ownerId: user.id,
              eventId: selectedEvent.id,
              eventTitle: selectedEvent.title,
            });

            setPendingRequest(created);
            setTestingPromptStep("ask");
            setTestingPromptOpen(true);
            showToast("success", "Заявка отправлена");
            await refreshRequests();
            return true;
          } catch (error) {
            showToast("error", extractErrorMessage(error) || "Ошибка при отправке заявки");
            return false;
          }
        }}
      />

      <InfoModal isOpen={infoOpen} onClose={() => setInfoOpen(false)} title={infoItem?.title} description={infoItem?.description} />

      <Modal isOpen={testingPromptOpen} onClose={closeTestingPrompt} title="Переход по заявке">
        {testingPromptStep === "ask" ? (
          <div className="confirm-body">
            <div className="confirm-text">Перейти к прохождению теста?</div>
            <div className="confirm-actions">
              <AppButton className="confirm-btn-danger" onClick={startDirectScenario}>
                Нет
              </AppButton>
              <AppButton className="confirm-btn-primary" onClick={startTestingScenario}>
                Да
              </AppButton>
            </div>
          </div>
        ) : (
          <div className="confirm-body">
            <div className="confirm-text">Ссылка для прохождения находится в центре уведомлений</div>
            <div className="confirm-actions">
              <AppButton className="confirm-btn-primary" onClick={closeTestingPrompt}>
                Понятно
              </AppButton>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}


