import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getDirectionsByEvent } from "../api/directions";
import { getEventById } from "../api/events";
import EventWizardModal, { type WizardLaunchContext } from "../components/EventWizard/EventWizardModal";
import TableHeader from "../../../components/Layout/TableHeader";
import InfoModal from "../../../components/Modal/InfoModal";
import Table from "../../../components/Table/Table";
import { useToast } from "../../../components/Toast/ToastProvider";
import BackButton from "../../../components/UI/BackButton";
import { useSearchSubmitFeedback } from "../../../hooks/useSearchSubmitFeedback";
import type { Direction } from "../../../types/direction";
import type { Event } from "../../../types/event";
import "../../../styles/page-colors.scss";

function filterDirectionsByQuery(items: Direction[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return items;

  return items.filter(
    (direction) =>
      (direction.title || "").toLowerCase().includes(normalizedQuery) ||
      (direction.organizer || "").toLowerCase().includes(normalizedQuery)
  );
}

export default function DirectionsPage() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const eventIdNum = Number(eventId);
  const { showToast } = useToast();

  const [search, setSearch] = useState("");
  const [event, setEvent] = useState<Event | null>(null);
  const [directions, setDirections] = useState<Direction[]>([]);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardContext, setWizardContext] = useState<WizardLaunchContext | null>(null);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [infoOpen, setInfoOpen] = useState(false);
  const [infoItem, setInfoItem] = useState<{ title?: string; description?: string } | null>(null);

  const loadDirections = useCallback(async () => {
    try {
      const [loadedEvent, loadedDirections] = await Promise.all([getEventById(eventIdNum), getDirectionsByEvent(eventIdNum)]);
      setEvent(loadedEvent || null);
      setDirections(loadedDirections || []);
    } catch {
      setEvent(null);
      setDirections([]);
    }
  }, [eventIdNum]);

  useEffect(() => {
    void loadDirections();
  }, [loadDirections]);

  const filteredDirections = filterDirectionsByQuery(directions, search);

  const { animatedIds: searchAnimatedIds, handleSearchSubmit } = useSearchSubmitFeedback({
    getMatches: (query) => filterDirectionsByQuery(directions, query),
    getId: (direction) => direction.id,
    notFoundMessage: "Такого направления не существует!",
    showToast,
  });

  return (
    <div className="page page--directions">
      <TableHeader
        title={
          <>
            <BackButton onClick={() => navigate("/events")} />
            {`${event?.title || "Мероприятие"} - Направления`}
          </>
        }
        search={search}
        onSearch={setSearch}
        onSearchSubmit={handleSearchSubmit}
        onCreate={() => {
          setMode("create");
          setWizardContext({ type: "direction", eventId: eventIdNum });
          setWizardOpen(true);
        }}
      />

      <Table
        columns={[
          { key: "title", title: "Название" },
          { key: "organizer", title: "Организатор" },
        ]}
        data={filteredDirections}
        animatedIds={searchAnimatedIds}
        onRowClick={(row) => navigate(`/events/${eventId}/directions/${row.id}/projects`)}
        onEdit={(row) => {
          setMode("edit");
          setWizardContext({
            type: "direction",
            eventId: eventIdNum,
            directionId: row.id,
          });
          setWizardOpen(true);
        }}
        onInfoClick={(row) => {
          setInfoItem({ title: row.title || "-", description: row.description || "Нет описания" });
          setInfoOpen(true);
        }}
      />

      {wizardOpen && wizardContext && (
        <EventWizardModal
          mode={mode}
          context={wizardContext}
          onClose={() => {
            setWizardOpen(false);
            void loadDirections();
          }}
        />
      )}

      <InfoModal isOpen={infoOpen} onClose={() => setInfoOpen(false)} title={infoItem?.title} description={infoItem?.description} />
    </div>
  );
}



