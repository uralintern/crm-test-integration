import { useCallback, useContext, useEffect, useState } from "react";
import { Dropdown, Segmented } from "antd";
import type { MenuProps } from "antd";
import { DownOutlined } from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";
import { getEvents } from "../../events/api/events";
import { getRequests, removeRequest, updateRequestStatus } from "../api/requests";
import Modal from "../../../components/Modal/Modal";
import InfoModal from "../../../components/Modal/InfoModal";
import Table from "../../../components/Table/Table";
import {
  ORGANIZER_REQUEST_STATUSES,
  REQUEST_STATUS,
  canWithdrawRequestStatus,
  getRequestTransitionCopy,
} from "../../../constants/requestProgress";
import { AuthContext } from "../../../context/AuthContext";
import { useSearchSubmitFeedback } from "../../../hooks/useSearchSubmitFeedback";
import type { Event as EventType } from "../../../types/event";
import { normalizeApplicationFormFields } from "../../../constants/applicationForm";
import "../../../styles/page-colors.scss";
import AppButton from "../../../components/UI/Button";
import { AppSearch } from "../../../components/UI/Input";
import AppSelect from "../../../components/UI/Select";
import { useToast } from "../../../components/Toast/ToastProvider";
import "./requests.scss";
import {
  REQUESTS_TEXT as TEXT,
  CHART_VIEW_STORAGE_KEY,
  DISPLAYED_STATUSES_STORAGE_KEY,
  OTHER_STATUS_KEY,
  REQUESTS_VIEW_STORAGE_KEY,
  REQUEST_STATUS_COLORS,
} from "../config/requestsConfig";
import { buildAnalyticsStatuses, RequestsAnalytics } from "../components/RequestsAnalytics";
import { StatusSettingsModal } from "../components/StatusSettingsModal";
import type {
  AnalyticsStatusKey,
  EventFilter,
  PendingTransition,
  RequestRecord,
  RequestTableRow,
  RequestsChartView,
  RequestsView,
} from "../types";
import {
  eventTitleFromRecord,
  isOrganizerRole,
  isProjectantRole,
  isRequestsChartView,
  isRequestsView,
  readDisplayedStatuses,
} from "../utils/requestsUtils";

function getApplicationFieldLabels(request: RequestRecord, events: EventType[]) {
  const event = events.find((item) => Number(item.id) === Number(request.eventId));
  return new Map(normalizeApplicationFormFields(event?.applicationFormFields).map((field) => [field.id, field.label]));
}

function formatRequestInfo(request: RequestRecord, events: EventType[]) {
  const lines: string[] = [];
  const fieldLabels = getApplicationFieldLabels(request, events);
  const add = (label: string, value?: unknown) => {
    const text = typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim();
    if (text) lines.push(`${label}: ${text}`);
  };

  add("Проектант", request.studentName);
  add("Мероприятие", eventTitleFromRecord(request));
  add("Направление", request.directionTitle);
  add("Проект", request.projectTitle);
  add("Специализация", request.specialization);
  add(fieldLabels.get("university") ?? "Университет", request.university);
  add(fieldLabels.get("course") ?? "Курс", request.course);
  add(fieldLabels.get("telegram") ?? "Аккаунт в ВК", request.vk ?? request.telegram);
  add("Статус", request.status);
  add(fieldLabels.get("about") ?? "Сообщение", request.about);

  Object.entries(request.customFields || {}).forEach(([key, value]) => {
    if (key === "about") return;
    add(fieldLabels.get(key) ?? key, value);
  });

  add("Дата подачи", request.createdAt ? new Date(request.createdAt).toLocaleString("ru-RU") : "");
  return lines.length ? lines.join("\n") : "Информация по заявке отсутствует";
}
function renderStatusOption(status: string) {
  const color = REQUEST_STATUS_COLORS[status] || "#94a3b8";

  return (
    <span className="request-status-option" style={{ ["--status-color" as string]: color }}>
      <span>{status}</span>
    </span>
  );
}

function renderSelectedStatusLabel(status: string) {
  return (
    <span className="request-status-selected-label" style={{ color: "#fff" }}>
      {status}
    </span>
  );
}

function getStatusSelectStyle(status?: string) {
  const color = REQUEST_STATUS_COLORS[String(status || "")] || "#94a3b8";
  return { ["--request-status-color" as string]: color };
}

export default function RequestsPage() {
  const { user } = useContext(AuthContext);
  const { showToast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const isOrganizer = isOrganizerRole(user?.role);
  const isProjectant = isProjectantRole(user?.role);

  const [requests, setRequests] = useState<RequestRecord[]>([]);
  const [events, setEvents] = useState<EventType[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<EventFilter>("all");
  const [expandedStatusKeys, setExpandedStatusKeys] = useState<AnalyticsStatusKey[]>([]);
  const [search, setSearch] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [toRemoveId, setToRemoveId] = useState<number | null>(null);
  const [transitionOpen, setTransitionOpen] = useState(false);
  const [pendingTransition, setPendingTransition] = useState<PendingTransition | null>(null);
  const [view, setView] = useState<RequestsView>(() => {
    const savedView = window.localStorage.getItem(REQUESTS_VIEW_STORAGE_KEY);
    return isRequestsView(savedView) ? savedView : "list";
  });
  const [chartView, setChartView] = useState<RequestsChartView>(() => {
    const savedView = window.localStorage.getItem(CHART_VIEW_STORAGE_KEY);
    return isRequestsChartView(savedView) ? savedView : "circle";
  });
  const [statusSettingsOpen, setStatusSettingsOpen] = useState(false);
  const [displayedStatuses, setDisplayedStatuses] = useState<string[]>(readDisplayedStatuses);
  const [infoOpen, setInfoOpen] = useState(false);
  const [infoItem, setInfoItem] = useState<{ title?: string; description?: string } | null>(null);

  const load = useCallback(async () => {
    const loadedRequests = await getRequests({ ownerId: user?.id, role: user?.role }).catch(() => []);
    setRequests(Array.isArray(loadedRequests) ? (loadedRequests as RequestRecord[]) : []);
  }, [user?.id, user?.role]);

  const loadEvents = useCallback(async () => {
    const loadedEvents = await getEvents().catch(() => []);
    setEvents(Array.isArray(loadedEvents) ? loadedEvents : []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    window.localStorage.setItem(CHART_VIEW_STORAGE_KEY, chartView);
  }, [chartView]);

  useEffect(() => {
    window.localStorage.setItem(REQUESTS_VIEW_STORAGE_KEY, view);
  }, [view]);

  useEffect(() => {
    window.localStorage.setItem(DISPLAYED_STATUSES_STORAGE_KEY, JSON.stringify(displayedStatuses));
    setExpandedStatusKeys((current) =>
      current.filter((key) => key === OTHER_STATUS_KEY || displayedStatuses.includes(key))
    );
  }, [displayedStatuses]);

  useEffect(() => {
    if (!isProjectant) return;

    const params = new URLSearchParams(location.search);
    if (params.get("requestAction") !== "progress") return;

    const requestId = Number(params.get("requestId"));
    const targetStatus = String(params.get("targetStatus") || "").trim();
    const rawSource = params.get("source");
    const source = rawSource === "testing" || rawSource === "chat" ? rawSource : "start";

    if (!requestId || !targetStatus) {
      navigate("/requests", { replace: true });
      return;
    }

    const copy = getRequestTransitionCopy(source, targetStatus);
    setPendingTransition({
      requestId,
      targetStatus,
      source,
      title: copy.title,
      message: copy.message,
    });
    setTransitionOpen(true);
  }, [isProjectant, location.search, navigate]);

  const handleStatusChange = async (id: number, status: string) => {
    try {
      await updateRequestStatus(id, status);
    } finally {
      await load();
    }
  };

  const handleWithdraw = (id: number) => {
    setToRemoveId(id);
    setConfirmOpen(true);
  };

  const confirmWithdraw = async () => {
    if (toRemoveId == null) return;
    try {
      await removeRequest(toRemoveId);
      showToast("success", "Заявка отозвана");
    } catch {
      showToast("error", "Не удалось отозвать заявку");
    } finally {
      setConfirmOpen(false);
      setToRemoveId(null);
      await load();
    }
  };

  const closeTransitionModal = () => {
    setTransitionOpen(false);
    setPendingTransition(null);
    navigate("/requests", { replace: true });
  };

  const confirmTransition = async () => {
    if (!pendingTransition) {
      closeTransitionModal();
      return;
    }

    try {
      const latestRequests = await getRequests({ ownerId: user?.id, role: user?.role }).catch(() => requests);
      const currentRequest = latestRequests.find((request) => Number(request.id) === Number(pendingTransition.requestId));
      const currentStatus = currentRequest?.status;
      const requiredStatus =
        pendingTransition.source === "testing" && pendingTransition.targetStatus === REQUEST_STATUS.CHAT_LINK_SENT
          ? REQUEST_STATUS.TESTING
          : pendingTransition.source === "chat" && pendingTransition.targetStatus === REQUEST_STATUS.JOINED_CHAT
            ? REQUEST_STATUS.CHAT_LINK_SENT
            : pendingTransition.source === "start" && pendingTransition.targetStatus === REQUEST_STATUS.STARTED
              ? REQUEST_STATUS.JOINED_CHAT
              : undefined;

      if (requiredStatus && currentStatus !== requiredStatus) {
        showToast("error", `Переход недоступен: текущий статус заявки "${currentStatus || "-"}".`);
        await load();
        return;
      }

      await updateRequestStatus(pendingTransition.requestId, pendingTransition.targetStatus);
      await load();
    } finally {
      closeTransitionModal();
    }
  };

  const toggleStatusList = (statusKey: AnalyticsStatusKey) => {
    setExpandedStatusKeys((current) =>
      current.includes(statusKey) ? current.filter((key) => key !== statusKey) : [...current, statusKey]
    );
  };

  const toggleDisplayedStatus = (status: string, checked: boolean) => {
    setDisplayedStatuses((current) => {
      const selected = new Set(current);
      if (checked) selected.add(status);
      else selected.delete(status);

      return ORGANIZER_REQUEST_STATUSES.filter((item) => selected.has(item));
    });
  };

  const selectedEvent =
    selectedEventId === "all" ? undefined : events.find((event) => Number(event.id) === Number(selectedEventId));

  const eventDropdownItems: MenuProps["items"] = [
    { key: "all", label: TEXT.allEvents },
    ...events.map((event) => ({
      key: String(event.id),
      label: event.title || `${TEXT.event} #${event.id}`,
    })),
  ];

  const handleEventMenuClick: MenuProps["onClick"] = ({ key }) => {
    setSelectedEventId(key === "all" ? "all" : Number(key));
  };

  const normalizedSearch = search.trim().toLowerCase();
  const selectedEventTitle = String(selectedEvent?.title || "").trim().toLowerCase();

  const matchesSelectedEvent = (request: RequestRecord) => {
    const requestEventTitle = String(eventTitleFromRecord(request)).trim().toLowerCase();
    if (!isOrganizer) return true;
    return selectedEventId === "all" || Number(request.eventId) === Number(selectedEventId) || (!!selectedEventTitle && requestEventTitle === selectedEventTitle);
  };

  const matchesCurrentUser = (request: RequestRecord) => {
    if (!isProjectant) return true;
    if (!user?.id) return false;
    return Number(request.ownerId) === Number(user.id);
  };

  const matchesSearchQuery = (request: RequestRecord, query: string) => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return true;

    return (
      (request.studentName || "").toLowerCase().includes(normalizedQuery) ||
      String(eventTitleFromRecord(request)).toLowerCase().includes(normalizedQuery) ||
      (request.specialization || "").toLowerCase().includes(normalizedQuery) ||
      (request.status || "").toLowerCase().includes(normalizedQuery)
    );
  };

  const scopedRequests = requests.filter((request) => matchesSelectedEvent(request) && matchesCurrentUser(request));
  const filtered = scopedRequests.filter((request) => matchesSearchQuery(request, normalizedSearch));

  const { animatedIds: searchAnimatedIds, handleSearchSubmit } = useSearchSubmitFeedback({
    getMatches: (query) => scopedRequests.filter((request) => matchesSearchQuery(request, query)),
    getId: (request) => request.id,
    notFoundMessage: TEXT.requestNotFound,
    showToast,
  });

  const mapped: RequestTableRow[] = filtered.map((request) => ({
    id: request.id,
    studentName: request.studentName || "-",
    event: eventTitleFromRecord(request),
    specialization: request.specialization || "-",
    status: request.status || "-",
    raw: request,
  }));

  const statusCounts = ORGANIZER_REQUEST_STATUSES.reduce<Record<string, number>>((acc, status) => {
    acc[status] = 0;
    return acc;
  }, {});

  filtered.forEach((request) => {
    const status = String(request.status || "").trim();
    if (status in statusCounts) statusCounts[status] += 1;
  });

  const analyticsStatuses = buildAnalyticsStatuses(statusCounts, displayedStatuses, filtered);
  const totalRequests = filtered.length;
  const visibleView = isOrganizer ? view : "list";
  const pageTitle = isProjectant ? TEXT.myRequests : TEXT.requests;

  return (
    <div className="page page--events">
      <div className={`requests-toolbar${isOrganizer ? "" : " requests-toolbar--student"}`}>
        <h1 className="h1 requests-toolbar__title">{pageTitle}</h1>

        {isOrganizer && (
          <Segmented
            className="requests-view-toggle"
            size="large"
            shape="round"
            value={view}
            onChange={(value) => setView(value as RequestsView)}
              options={[
                { label: TEXT.list, value: "list" },
                { label: TEXT.diagram, value: "diagram" },
              ]}
            />
        )}

	        {isOrganizer && (
	          <div className="requests-toolbar__filters">
	            <Dropdown
	              menu={{ items: eventDropdownItems, onClick: handleEventMenuClick, selectedKeys: [String(selectedEventId)] }}
	              placement="bottom"
              trigger={["click"]}
            >
              <AppButton className="requests-event-dropdown">
                <span>{selectedEvent?.title || TEXT.allEvents}</span>
                <DownOutlined />
	              </AppButton>
	            </Dropdown>

	            <AppSearch
	              className="search-box"
	              placeholder={TEXT.search}
	              value={search}
	              onChange={(event) => setSearch(event.target.value)}
	              onSearch={handleSearchSubmit}
	            />
	          </div>
	        )}
	      </div>

      {visibleView === "list" ? (
        <Table
          columns={[
            { key: "studentName", title: TEXT.studentName, width: "310px" },
            { key: "event", title: TEXT.event, width: "370px" },
            { key: "specialization", title: TEXT.specialization, width: "380px" },
            { key: "status", title: TEXT.status },
          ]}
          data={mapped}
          animatedIds={searchAnimatedIds}
          gridColumns="1.2fr 2fr 1.4fr 1fr"
          onInfoClick={(row) => {
            setInfoItem({ title: row.studentName || "Заявка", description: formatRequestInfo(row.raw, events) });
            setInfoOpen(true);
          }}
          renderCell={(row: RequestTableRow, colKey: string) => {
            if (colKey !== "status") return undefined;

            if (user?.role === "organizer") {
              return (
                <AppSelect
                  className="status-select"
                  style={getStatusSelectStyle(row.status)}
                  value={row.status || undefined}
                  placeholder={TEXT.status}
                  onChange={(value) => handleStatusChange(row.id, String(value))}
                  options={[
                    ...ORGANIZER_REQUEST_STATUSES.map((status) => ({
                      value: status,
                      label: renderSelectedStatusLabel(status),
                    })),
                  ]}
                  optionRender={(option) => renderStatusOption(String(option.value || ""))}
                />
              );
            }

            if (isProjectant) {
              const canWithdraw = canWithdrawRequestStatus(row.status);

              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
                  <div>{row.status || ""}</div>
                  {canWithdraw && (
                    <AppButton className="danger-outline request-withdraw-button" onClick={() => handleWithdraw(row.id)}>
                      {TEXT.withdrawRequest}
                    </AppButton>
                  )}
                </div>
              );
            }

            return <div>{row.status || "-"}</div>;
          }}
        />
      ) : (
        <RequestsAnalytics
          chartView={chartView}
          onChartViewChange={setChartView}
          onOpenStatusSettings={() => setStatusSettingsOpen(true)}
          analyticsStatuses={analyticsStatuses}
          totalRequests={totalRequests}
          expandedStatusKeys={expandedStatusKeys}
          onToggleStatusList={toggleStatusList}
        />
      )}

	      <Modal isOpen={confirmOpen} onClose={() => setConfirmOpen(false)} title={TEXT.confirmAction}>
        <div className="confirm-body">
          <div className="confirm-text">{TEXT.withdrawConfirm}</div>
          <div className="confirm-actions">
            <AppButton className="close-btn" onClick={() => setConfirmOpen(false)}>
              {TEXT.cancel}
            </AppButton>
            <AppButton className="danger-outline" onClick={confirmWithdraw}>
              {TEXT.withdraw}
            </AppButton>
          </div>
        </div>
	      </Modal>

      <InfoModal isOpen={infoOpen} onClose={() => setInfoOpen(false)} title={infoItem?.title} description={infoItem?.description} />

      <StatusSettingsModal
        isOpen={statusSettingsOpen}
        displayedStatuses={displayedStatuses}
        statusCounts={statusCounts}
        onClose={() => setStatusSettingsOpen(false)}
        onToggleStatus={toggleDisplayedStatus}
        onSelectAll={() => setDisplayedStatuses([...ORGANIZER_REQUEST_STATUSES])}
      />
	
	      <Modal isOpen={transitionOpen} onClose={closeTransitionModal} title={pendingTransition?.title || TEXT.confirmation}>
        <div className="confirm-body">
          <div className="confirm-text">{pendingTransition?.message || TEXT.confirmActionText}</div>
          <div className="confirm-actions">
            <AppButton className="close-btn" onClick={closeTransitionModal}>
              {TEXT.cancel}
            </AppButton>
            <AppButton className="btn-send" onClick={confirmTransition}>
              {TEXT.confirm}
            </AppButton>
          </div>
        </div>
      </Modal>
    </div>
  );
}




