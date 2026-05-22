import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Empty, Modal as AntModal } from "antd";
import { RollbackOutlined } from "@ant-design/icons";
import { getArchivedEvents, restoreEvent } from "../api/events";
import TableHeader from "../../../components/Layout/TableHeader";
import Table from "../../../components/Table/Table";
import AppButton from "../../../components/UI/Button";
import { useToast } from "../../../components/Toast/ToastProvider";
import { AuthContext } from "../../../context/AuthContext";
import { useSearchSubmitFeedback } from "../../../hooks/useSearchSubmitFeedback";
import type { Event } from "../../../types/event";
import "../../../styles/page-colors.scss";
import "./archive.scss";

function isProjectantRole(role?: string) {
  const normalized = String(role || "").toLowerCase();
  return normalized === "student" || normalized.includes("project");
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

export default function ArchivePage() {
  const { user } = useContext(AuthContext);
  const { showToast } = useToast();
  const [events, setEvents] = useState<Event[]>([]);
  const [search, setSearch] = useState("");
  const [restoreCandidate, setRestoreCandidate] = useState<Event | null>(null);
  const [restoring, setRestoring] = useState(false);
  const canManageArchive = Boolean(user && !isProjectantRole(user.role));

  const loadEvents = useCallback(async () => {
    if (!canManageArchive) {
      setEvents([]);
      return;
    }

    try {
      const archived = await getArchivedEvents();
      setEvents(archived);
    } catch {
      setEvents([]);
      showToast("error", "Не удалось загрузить архив мероприятий");
    }
  }, [canManageArchive, showToast]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  const filteredEvents = useMemo(() => filterEventsByQuery(events, search), [events, search]);

  const { animatedIds: searchAnimatedIds, handleSearchSubmit } = useSearchSubmitFeedback({
    getMatches: (query) => filterEventsByQuery(events, query),
    getId: (event) => event.id,
    notFoundMessage: "Такого мероприятия в архиве нет!",
    showToast,
  });

  const handleRestore = async () => {
    if (!restoreCandidate?.id) return;
    const eventId = Number(restoreCandidate.id);
    setRestoring(true);

    try {
      await restoreEvent(eventId);
      setRestoreCandidate(null);
      showToast("success", "Мероприятие возвращено из архива");
      await loadEvents();
      window.dispatchEvent(new CustomEvent("events:restored", { detail: { eventId } }));
    } catch {
      showToast("error", "Не удалось вернуть мероприятие из архива");
    } finally {
      setRestoring(false);
    }
  };

  if (!canManageArchive) {
    return (
      <section className="archive-page">
        <div className="archive-page__empty">
          <Empty description="Архив мероприятий доступен организаторам.">
            <h1>Архив мероприятий</h1>
          </Empty>
        </div>
      </section>
    );
  }

  return (
    <div className="page page--events">
      <TableHeader
        title="Архив мероприятий"
        search={search}
        onSearch={setSearch}
        onSearchSubmit={handleSearchSubmit}
      />

      <Table
        columns={[
          { key: "title", title: "Название" },
          { key: "startDate", title: "Дата начала" },
          { key: "endDate", title: "Дата окончания" },
          { key: "organizer", title: "Организатор" },
          { key: "status", title: "Статус" },
        ]}
        data={filteredEvents}
        animatedIds={searchAnimatedIds}
        badgeKeys={["startDate", "endDate", "status"]}
        onEdit={(row) => setRestoreCandidate(row)}
        editIcon={<RollbackOutlined />}
        editTooltip="Вернуть из архива"
      />

      <AntModal
        open={Boolean(restoreCandidate)}
        onCancel={() => setRestoreCandidate(null)}
        title="Вернуть мероприятие из архива?"
        footer={[
          <AppButton key="cancel" className="close-btn" onClick={() => setRestoreCandidate(null)} disabled={restoring}>
            Отмена
          </AppButton>,
          <AppButton key="restore" className="primary-btn" onClick={handleRestore} disabled={restoring}>
            {restoring ? "Возвращаем..." : "Вернуть"}
          </AppButton>,
        ]}
        centered
      >
        <p>
          Мероприятие снова появится в списке мероприятий, а связанные заявки, направления, проекты и команды снова
          станут доступны в рабочих разделах.
        </p>
      </AntModal>
    </div>
  );
}
