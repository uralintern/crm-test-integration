import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getDirectionById } from "../api/directions";
import { getEventById } from "../api/events";
import { getPlannerState } from "../../planner/api/planner";
import { getProjectsByDirection } from "../api/projects";
import EventWizardModal, { type WizardLaunchContext } from "../components/EventWizard/EventWizardModal";
import TableHeader from "../../../components/Layout/TableHeader";
import InfoModal from "../../../components/Modal/InfoModal";
import Table from "../../../components/Table/Table";
import { useToast } from "../../../components/Toast/ToastProvider";
import PageLoader from "../../../components/Loading/PageLoader";
import BackButton from "../../../components/UI/BackButton";
import { useSearchSubmitFeedback } from "../../../hooks/useSearchSubmitFeedback";
import { getAllUsers } from "../../../storage/storage";
import { AuthContext } from "../../../context/AuthContext";
import { canManageEvent } from "../../../utils/access";
import type { Direction } from "../../../types/direction";
import type { Event } from "../../../types/event";
import type { Project } from "../../../types/project";
import type { User } from "../../../types/user";
import "../../../styles/page-colors.scss";

function fullName(user: User) {
  return `${user.surname || ""} ${user.name || ""}`.trim() || user.email || `ID ${user.id}`;
}

function buildCuratorLabel(curatorIds: number[], userNameById: Map<number, string>) {
  const uniqueIds = Array.from(new Set(curatorIds.filter((id) => Number.isFinite(id) && id > 0)));
  if (uniqueIds.length === 0) return "Не назначен";
  return uniqueIds.map((id) => userNameById.get(id) || `ID ${id}`).join(", ");
}

function filterProjectsByQuery(items: Project[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return items;

  return items.filter(
    (project) =>
      (project.title || "").toLowerCase().includes(normalizedQuery) ||
      (project.curator || "").toLowerCase().includes(normalizedQuery)
  );
}

export default function ProjectsPage() {
  const { eventId, directionId } = useParams();
  const navigate = useNavigate();
  const eventIdNum = Number(eventId);
  const directionIdNum = Number(directionId);
  const { showToast } = useToast();
  const { user } = useContext(AuthContext);

  const [event, setEvent] = useState<Event | null>(null);
  const [direction, setDirection] = useState<Direction | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);

  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardContext, setWizardContext] = useState<WizardLaunchContext | null>(null);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [search, setSearch] = useState("");

  const [infoOpen, setInfoOpen] = useState(false);
  const [infoItem, setInfoItem] = useState<{ title?: string; description?: string } | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [loadedEvent, loadedDirection, loadedProjects, plannerState, users] = await Promise.all([
        getEventById(eventIdNum).catch(() => null),
        getDirectionById(directionIdNum).catch(() => null),
        getProjectsByDirection(directionIdNum).catch(() => []),
        getPlannerState().catch(() => null),
        getAllUsers().catch(() => []),
      ]);

      const userNameById = new Map<number, string>((users || []).map((user) => [Number(user.id), fullName(user)]));
      const teams = plannerState?.teams || [];
      const mappedProjects = (loadedProjects || []).map((project) => {
        const curatorIds = teams
          .filter((team) => Number(team.projectId) === Number(project.id))
          .map((team) => Number(team.curatorId))
          .filter((id) => Number.isFinite(id) && id > 0);

        return {
          ...project,
          curator: curatorIds.length > 0 || !project.curator ? buildCuratorLabel(curatorIds, userNameById) : project.curator,
        };
      });

      setEvent(loadedEvent || null);
      setDirection(loadedDirection || null);
      setProjects(mappedProjects);
    } catch {
      setEvent(null);
      setDirection(null);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, [directionIdNum, eventIdNum]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const filteredProjects = useMemo(() => filterProjectsByQuery(projects, search), [projects, search]);
  const canManageCurrentEvent = canManageEvent(user, event || { id: eventIdNum });

  const { animatedIds: searchAnimatedIds, handleSearchSubmit } = useSearchSubmitFeedback({
    getMatches: (query) => filterProjectsByQuery(projects, query),
    getId: (project) => project.id,
    notFoundMessage: "Такого проекта не существует!",
    showToast,
  });

  return (
    <div className="page page--projects">
      <TableHeader
        title={
          <>
            <BackButton onClick={() => navigate(`/events/${eventId}/directions`)} />
            {`${event?.title || "Мероприятие"} / ${direction?.title || "Направление"} - Проекты`}
          </>
        }
        search={search}
        onSearch={setSearch}
        onSearchSubmit={handleSearchSubmit}
        canCreate={canManageCurrentEvent}
        onCreate={() => {
          setMode("create");
          setWizardContext({ type: "project", eventId: eventIdNum, directionId: directionIdNum });
          setWizardOpen(true);
        }}
      />

      <Table
        columns={[
          { key: "title", title: "Название" },
          { key: "curator", title: "Куратор" },
        ]}
        data={filteredProjects}
        animatedIds={searchAnimatedIds}
        canEditRow={() => canManageCurrentEvent}
        onEdit={(row) => {
          setMode("edit");
          setWizardContext({
            type: "project",
            eventId: eventIdNum,
            directionId: directionIdNum,
            projectId: row.id,
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
            void loadAll();
          }}
        />
      )}

      <InfoModal isOpen={infoOpen} onClose={() => setInfoOpen(false)} title={infoItem?.title} description={infoItem?.description} />

      {loading && <PageLoader className="page-loader--compact" />}
    </div>
  );
}



