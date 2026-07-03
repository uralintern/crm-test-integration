import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { Modal as AntModal } from "antd";
import {
  buildParticipantsFromRequests,
  getPlannerState,
  getPlannerTeamDeskSocketUrl,
  hasPlannerAccessStatus,
  mergeTeamDeskIntoPlannerState,
  parsePlannerTeamDeskSocketMessage,
  savePlannerState,
  syncParticipants,
} from "../api/planner";
import { getRequests, updateRequestStatus } from "../../requests/api/requests";
import { REQUEST_STATUS } from "../../../constants/requestProgress";
import { updateProjectCurator } from "../../events/api/projects";
import { useToast } from "../../../components/Toast/ToastProvider";
import PageLoader from "../../../components/Loading/PageLoader";
import { AuthContext } from "../../../context/AuthContext";
import AutomationPanel from "../../automation/components/AutomationPanel";
import { DEFAULT_KANBAN_COLUMNS, nextPlannerId, removeTeamCascade } from "../storage/planner";
import { getAllUsers } from "../../../storage/storage";
import type { PlannerState, PlannerSubtask, PlannerTeam } from "../../../types/planner";
import type { Request } from "../../../types/request";
import type { User } from "../../../types/user";
import PlannerTabs from "../components/PlannerTabs";
import TeamsTab from "../components/tabs/TeamsTab";
import BacklogTab from "../components/tabs/BacklogTab";
import KanbanTab from "../components/tabs/KanbanTab";
import GanttTab from "../components/tabs/GanttTab";
import ConfirmCloseEnrollmentModal from "../components/modals/ConfirmCloseEnrollmentModal";
import ConfirmDeleteTeamModal from "../components/modals/ConfirmDeleteTeamModal";
import TeamInfoModal from "../components/modals/TeamInfoModal";
import TeamEditModal from "../components/modals/TeamEditModal";
import TaskCardModal from "../components/modals/TaskCardModal";
import type { ParentEditDraft, PlannerTab, ProjectApplicantsGroup, SubtaskEditDraft, TaskCardState } from "../planner.types";
import {
  getPlannerTitleMapsFromCatalog,
  loadMissingPlannerTitles,
  loadPlannerCrmCatalog,
  type PlannerCatalogEvent,
} from "../planner.catalog";
import { buildApplicantsTree, buildProjectApplicantGroups } from "../planner.applicants";
import { fullName, isFallbackParticipantName, PLANNED_KANBAN_STATUS, roleFlags } from "../planner.utils";
import { getManagedEventIds, isGlobalOrganizer } from "../../../utils/access";
import "../planner.scss";
import dayjs, { Dayjs } from "dayjs";

const UNASSIGNED_ASSIGNEE_FILTER = "__unassigned";

export default function PlannerPage() {
  const { user } = useContext(AuthContext);
  const { showToast } = useToast();
  const role = roleFlags(user?.role);
  const managedEventIdSet = useMemo(() => getManagedEventIds(user), [user]);
  const hasScopedOrganizerAccess = managedEventIdSet.size > 0;
  const hasGlobalOrganizerAccess = isGlobalOrganizer(user) || role.isOrganizer && !hasScopedOrganizerAccess;
  const isOrganizer = hasGlobalOrganizerAccess || hasScopedOrganizerAccess;
  const isCurator = role.isCurator;
  const isStudent = role.isStudent && !isOrganizer;
  const userId = Number(user?.id || 0);
  const skipNextPlannerSaveRef = useRef(false);
  const pruneMissingTeamDesksOnNextSaveRef = useRef(false);
  const syncedProjectCuratorKeyRef = useRef<Set<string>>(new Set());
  const plannerSocketRef = useRef<WebSocket | null>(null);

  const [tab, setTab] = useState<PlannerTab>(() => {
    const raw = localStorage.getItem("planner_tab_v1");
    if (raw === "teams" || raw === "backlog" || raw === "kanban" || raw === "gantt") return raw;
    return "teams";
  });
  const [loading, setLoading] = useState(false);
  const [isPlannerLoaded, setIsPlannerLoaded] = useState(false);
  const [teamFilter, setTeamFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [state, setState] = useState<PlannerState>({
    enrollmentClosed: false,
    closedEventIds: [],
    hiddenEventIds: [],
    participants: [],
    teams: [],
    parentTasks: [],
    subtasks: [],
    columns: [],
  });
  const [users, setUsers] = useState<User[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);

  const [selectedApplicantsByGroup, setSelectedApplicantsByGroup] = useState<Record<string, number[]>>({});
  const [teamNameByGroup, setTeamNameByGroup] = useState<Record<string, string>>({});
  const [teamCuratorByGroup, setTeamCuratorByGroup] = useState<Record<string, string>>({});
  const [teamDirectionByGroup, setTeamDirectionByGroup] = useState<Record<string, string>>({});
  const [teamProjectByGroup, setTeamProjectByGroup] = useState<Record<string, string>>({});
  const [activeTeamBuilderGroupKey, setActiveTeamBuilderGroupKey] = useState("");
  const [crmCatalog, setCrmCatalog] = useState<PlannerCatalogEvent[]>([]);
  const [eventTitleById, setEventTitleById] = useState<Record<number, string>>({});
  const [directionTitleById, setDirectionTitleById] = useState<Record<number, string>>({});
  const [projectTitleById, setProjectTitleById] = useState<Record<number, string>>({});

  const [parentTitle, setParentTitle] = useState("");
  const [parentAssigneeId, setParentAssigneeId] = useState("");
  const [parentStart, setParentStart] = useState<Dayjs | undefined>();
  const [parentEnd, setParentEnd] = useState<Dayjs | undefined>();
  const [selectedParentId, setSelectedParentId] = useState<number | null>(null);

  const [subTitle, setSubTitle] = useState("");
  const [subAssigneeId, setSubAssigneeId] = useState("0");
  const [subStart, setSubStart] = useState<Dayjs | undefined>();
  const [subEnd, setSubEnd] = useState<Dayjs | undefined>();
  const [subInSprint, setSubInSprint] = useState(false);
  const [newColumn, setNewColumn] = useState("");
  const [closeEnrollmentTarget, setCloseEnrollmentTarget] = useState<{ eventId: number; eventTitle: string } | null>(null);
  const [deleteTeamTargetId, setDeleteTeamTargetId] = useState<number | null>(null);
  const [teamInfoOpen, setTeamInfoOpen] = useState(false);
  const [teamInfoId, setTeamInfoId] = useState<number | null>(null);
  const [teamEditOpen, setTeamEditOpen] = useState(false);
  const [teamEditId, setTeamEditId] = useState<number | null>(null);
  const [teamEditMembers, setTeamEditMembers] = useState<number[]>([]);
  const [taskCardOpen, setTaskCardOpen] = useState(false);
  const [taskCard, setTaskCard] = useState<TaskCardState>(null);
  const [automationOpen, setAutomationOpen] = useState(false);

  const [editingParentId, setEditingParentId] = useState<number | null>(null);
  const [editingParentDraft, setEditingParentDraft] = useState<ParentEditDraft | null>(null);
  const [editingSubtaskId, setEditingSubtaskId] = useState<number | null>(null);
  const [editingSubtaskDraft, setEditingSubtaskDraft] = useState<SubtaskEditDraft | null>(null);

  const notifyError = (message: string) => {
    showToast("error", message);
  };

  const notifySuccess = (message: string) => {
    showToast("success", message);
  };

  const currentTimestamp = () => new Date().toISOString();

  const resolveProjectIdFromRequestIds = (requestIds: number[]) => {
    const projectIds = Array.from(
      new Set(
        requests
          .filter((request) => requestIds.includes(Number(request.id)))
          .map((request) => Number(request.projectId))
          .filter((projectId) => Number.isFinite(projectId) && projectId > 0)
      )
    );

    return projectIds.length === 1 ? projectIds[0] : undefined;
  };

  const resolveTeamProjectId = (team?: PlannerTeam) => {
    const directProjectId = Number(team?.projectId);
    if (Number.isFinite(directProjectId) && directProjectId > 0) return directProjectId;

    return resolveProjectIdFromRequestIds(team?.sourceRequestIds || []);
  };

  const syncProjectCurator = (projectId?: number, curatorId?: number, options?: { silent?: boolean }) => {
    const normalizedProjectId = Number(projectId);
    const normalizedCuratorId = Number(curatorId);
    if (!Number.isFinite(normalizedProjectId) || normalizedProjectId <= 0) return;
    if (!Number.isFinite(normalizedCuratorId) || normalizedCuratorId <= 0) return;

    void updateProjectCurator(normalizedProjectId, normalizedCuratorId).catch(() => {
      if (!options?.silent) notifyError("Не удалось обновить куратора проекта");
    });
  };

  const clearProjectCurator = (projectId?: number, options?: { silent?: boolean }) => {
    const normalizedProjectId = Number(projectId);
    if (!Number.isFinite(normalizedProjectId) || normalizedProjectId <= 0) return;

    void updateProjectCurator(normalizedProjectId, null).catch(() => {
      if (!options?.silent) notifyError("Не удалось убрать куратора проекта");
    });
  };


  useEffect(() => {
    if (!isPlannerLoaded) return;

    const curatorIdsByProject = new Map<number, Set<number>>();
    state.teams.forEach((team) => {
      const projectId = resolveTeamProjectId(team);
      const curatorId = Number(team.curatorId);
      if (!projectId || !Number.isFinite(curatorId) || curatorId <= 0) return;

      if (!curatorIdsByProject.has(projectId)) curatorIdsByProject.set(projectId, new Set());
      curatorIdsByProject.get(projectId)?.add(curatorId);
    });

    curatorIdsByProject.forEach((curatorIds, projectId) => {
      if (curatorIds.size !== 1) return;

      const [curatorId] = Array.from(curatorIds);
      const syncKey = `${projectId}:${curatorId}`;
      if (syncedProjectCuratorKeyRef.current.has(syncKey)) return;

      syncedProjectCuratorKeyRef.current.add(syncKey);
      syncProjectCurator(projectId, curatorId, { silent: true });
    });
  }, [isPlannerLoaded, state.teams, requests]);

  useEffect(() => {
    localStorage.setItem("planner_tab_v1", tab);
  }, [tab]);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setIsPlannerLoaded(false);
    Promise.all([
      getPlannerState(),
      getAllUsers(),
      getRequests({ role: user?.role, ownerId: isOrganizer ? undefined : user?.id }),
    ])
      .then(([planner, us, rs]) => {
        if (!mounted) return;
        const usersData = Array.isArray(us) ? us : [];
        const requestsData = Array.isArray(rs) ? rs : [];
        const synced =
          isOrganizer && planner.closedEventIds.length > 0
            ? syncParticipants(planner, buildParticipantsFromRequests(usersData, requestsData, planner.closedEventIds))
            : planner;
        skipNextPlannerSaveRef.current = true;
        setState(synced);
        setUsers(Array.isArray(us) ? us : []);
        setRequests(Array.isArray(rs) ? rs : []);
        setIsPlannerLoaded(true);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [isOrganizer, user?.id, user?.role]);

  useEffect(() => {
    let mounted = true;

    const loadCrmCatalog = async () => {
      try {
        const catalog = await loadPlannerCrmCatalog();
        if (!mounted) return;

        const titleMaps = getPlannerTitleMapsFromCatalog(catalog);
        setCrmCatalog(catalog);
        setEventTitleById((prev) => ({ ...prev, ...titleMaps.eventTitleById }));
        setDirectionTitleById((prev) => ({ ...prev, ...titleMaps.directionTitleById }));
        setProjectTitleById((prev) => ({ ...prev, ...titleMaps.projectTitleById }));
      } catch {
        if (mounted) setCrmCatalog([]);
      }
    };

    void loadCrmCatalog();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    const fillTitles = async () => {
      const titleMaps = await loadMissingPlannerTitles(requests);
      if (!mounted) return;

      if (Object.keys(titleMaps.eventTitleById).length > 0) {
        setEventTitleById((prev) => ({ ...prev, ...titleMaps.eventTitleById }));
      }
      if (Object.keys(titleMaps.directionTitleById).length > 0) {
        setDirectionTitleById((prev) => ({ ...prev, ...titleMaps.directionTitleById }));
      }
      if (Object.keys(titleMaps.projectTitleById).length > 0) {
        setProjectTitleById((prev) => ({ ...prev, ...titleMaps.projectTitleById }));
      }
    };

    void fillTitles();
    return () => {
      mounted = false;
    };
  }, [requests]);

  const userNameById = useMemo(() => new Map(users.map((u) => [Number(u.id), fullName(u) || u.email])), [users]);
  const curatorUsers = useMemo(
    () =>
      users.filter((candidate) => {
        const candidateRole = roleFlags(candidate.role);
        return candidateRole.isOrganizer || candidateRole.isCurator || Boolean(candidate.isGlobalOrganizer || candidate.isSuperuser || candidate.isStaff);
      }),
    [users]
  );
  const requestStudentNameById = useMemo(() => {
    const map = new Map<number, string>();
    requests.forEach((request) => {
      const ownerId = Number(request.ownerId);
      const name = String(request.studentName || "").trim();
      if (!Number.isFinite(ownerId) || !name) return;
      map.set(ownerId, name);
    });
    return map;
  }, [requests]);
  const participantNameById = useMemo(
    () => new Map(state.participants.map((p) => [Number(p.id), String(p.fullName || "").trim()])),
    [state.participants]
  );
  const specializationByOwnerId = useMemo(() => {
    const map = new Map<number, string>();
    state.teams.forEach((team) => {
      Object.entries(team.memberRoles || {}).forEach(([ownerId, role]) => {
        const id = Number(ownerId);
        const value = String(role || "").trim();
        if (Number.isFinite(id) && value) map.set(id, value);
      });
    });
    requests.forEach((r) => {
      const ownerId = Number(r.ownerId);
      if (!Number.isFinite(ownerId)) return;
      const spec = String(r.specialization || "").trim();
      if (spec) map.set(ownerId, spec);
    });
    return map;
  }, [requests, state.teams]);
  const hiddenEventIdSet = useMemo(
    () => new Set(state.hiddenEventIds.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)),
    [state.hiddenEventIds]
  );
  const confirmedMemberTeamIds = useMemo(
    () => state.teams.filter((t) => t.confirmed && t.memberIds.includes(userId)).map((t) => t.id),
    [state.teams, userId]
  );
  const curatorTeamIds = useMemo(() => state.teams.filter((t) => Number(t.curatorId) === userId).map((t) => t.id), [state.teams, userId]);
  const studentIsSyncedParticipant = useMemo(
    () => isStudent && state.closedEventIds.length > 0 && state.participants.some((participant) => Number(participant.id) === userId),
    [isStudent, state.closedEventIds.length, state.participants, userId]
  );
  const studentHasPlannerAccess = !isStudent || confirmedMemberTeamIds.length > 0 || studentIsSyncedParticipant;
  const studentWaitingForConfirmedTeam = isStudent && studentHasPlannerAccess && confirmedMemberTeamIds.length === 0;
  const teamById = useMemo(() => new Map(state.teams.map((team) => [Number(team.id), team])), [state.teams]);
  const isManagedTeam = (teamId: number) => {
    if (hasGlobalOrganizerAccess) return true;
    const team = teamById.get(Number(teamId));
    return Boolean(team && managedEventIdSet.has(Number(team.eventId)));
  };
  const canViewTeam = (teamId: number) => isManagedTeam(teamId) || isCurator || (isStudent && confirmedMemberTeamIds.includes(teamId));
  const canEditTeam = (teamId: number) => isManagedTeam(teamId) || (isCurator && curatorTeamIds.includes(teamId)) || (isStudent && confirmedMemberTeamIds.includes(teamId));
  const canMoveSubtask = (subtask: PlannerSubtask) => canEditTeam(subtask.teamId) || Number(subtask.assigneeId) === userId;

  const visibleTeams = state.teams.filter((t) => canViewTeam(t.id) && !hiddenEventIdSet.has(Number(t.eventId)));
  const activeTeamId = teamFilter ? Number(teamFilter) : null;
  const activeTeam = activeTeamId != null ? visibleTeams.find((team) => Number(team.id) === Number(activeTeamId)) ?? null : null;
  useEffect(() => {
    if (!isPlannerLoaded) return;
    if (skipNextPlannerSaveRef.current) {
      skipNextPlannerSaveRef.current = false;
      return;
    }
    const saveOptions = pruneMissingTeamDesksOnNextSaveRef.current ? { pruneMissingTeamDesks: true } : undefined;
    pruneMissingTeamDesksOnNextSaveRef.current = false;
    void savePlannerState(state, activeTeamId, saveOptions);
  }, [activeTeamId, isPlannerLoaded, state]);
  const plannerAutomationEventId = Number(activeTeam?.eventId ?? visibleTeams[0]?.eventId ?? 0) || null;
  const openPlannerAutomation = () => {
    if (!plannerAutomationEventId) {
      notifyError("Сначала выберите команду, связанную с мероприятием.");
      return;
    }
    setAutomationOpen(true);
  };

  useEffect(() => {
    if (visibleTeams.length === 0) {
      if (teamFilter) setTeamFilter("");
      return;
    }
    const hasSelectedTeam = visibleTeams.some((team) => String(team.id) === teamFilter);
    if (!hasSelectedTeam) {
      setTeamFilter(String(visibleTeams[0].id));
    }
  }, [teamFilter, visibleTeams]);
  const teamParents = state.parentTasks.filter(
    (p) => canViewTeam(p.teamId) && activeTeamId != null && Number(activeTeamId) === Number(p.teamId)
  );
  const teamSubtasks = state.subtasks.filter(
    (s) => canViewTeam(s.teamId) && activeTeamId != null && Number(activeTeamId) === Number(s.teamId)
  );
  const normalizedAssigneeFilter = assigneeFilter.trim();
  const matchesAssigneeFilter = (assigneeId?: number) => {
    if (!normalizedAssigneeFilter) return true;
    const normalizedAssigneeId = Number(assigneeId);
    if (normalizedAssigneeFilter === UNASSIGNED_ASSIGNEE_FILTER) {
      return assigneeId == null || !Number.isFinite(normalizedAssigneeId) || normalizedAssigneeId <= 0;
    }
    return normalizedAssigneeId === Number(normalizedAssigneeFilter);
  };
  const filteredSubtasks = teamSubtasks.filter((subtask) => matchesAssigneeFilter(subtask.assigneeId));
  const filteredParents = teamParents.filter((parent) => {
    if (!normalizedAssigneeFilter) return true;
    if (matchesAssigneeFilter(parent.assigneeId)) return true;
    return teamSubtasks.some(
      (subtask) => Number(subtask.parentTaskId) === Number(parent.id) && matchesAssigneeFilter(subtask.assigneeId)
    );
  });
  const selectedParent = filteredParents.find((p) => Number(p.id) === Number(selectedParentId));
  const displayNameForUserId = (id: number) => {
    const userName = userNameById.get(id);
    if (userName) return userName;

    const requestName = requestStudentNameById.get(id);
    if (requestName) return requestName;

    const participantName = participantNameById.get(id);
    if (participantName && !isFallbackParticipantName(participantName)) return participantName;

    return `Участник #${id}`;
  };
  const displayAssigneeLabel = (id: number) => {
    const base = displayNameForUserId(id);
    const spec = specializationByOwnerId.get(id);
    return spec ? `${base} - ${spec}` : base;
  };
  const getTeamMemberIds = (teamId: number) =>
    state.teams.find((t) => Number(t.id) === Number(teamId))?.memberIds || [];
  const activeTeamMembers = activeTeamId != null ? getTeamMemberIds(activeTeamId) : [];
  const assigneeFilterOptions = [
    { value: "", label: "Все исполнители" },
    { value: UNASSIGNED_ASSIGNEE_FILTER, label: "Без ответственного" },
    ...activeTeamMembers.map((id) => ({ value: String(id), label: displayAssigneeLabel(Number(id)) })),
  ];
  useEffect(() => {
    setAssigneeFilter("");
  }, [activeTeamId]);
  useEffect(() => {
    if (!isPlannerLoaded || activeTeamId == null || !Number.isFinite(activeTeamId) || activeTeamId <= 0) return;

    const socket = new WebSocket(getPlannerTeamDeskSocketUrl(activeTeamId));
    plannerSocketRef.current = socket;

    socket.onmessage = (event) => {
      const message = parsePlannerTeamDeskSocketMessage(String(event.data));
      if (!message || Number(message.teamId) !== Number(activeTeamId)) return;

      skipNextPlannerSaveRef.current = true;
      setState((prev) => mergeTeamDeskIntoPlannerState(prev, message.desk));
    };

    socket.onerror = () => {
      socket.close();
    };

    return () => {
      if (plannerSocketRef.current === socket) plannerSocketRef.current = null;
      socket.close();
    };
  }, [activeTeamId, isPlannerLoaded]);
  const selectedTeamMembers = selectedParent
    ? state.teams.find((t) => Number(t.id) === Number(selectedParent.teamId))?.memberIds || []
    : [];
  const plannedColumn = state.columns.find((column) => column === PLANNED_KANBAN_STATUS) || state.columns[0] || PLANNED_KANBAN_STATUS;
  const sourceLabelForTeam = (team: PlannerTeam) => {
    const eventLabel = team.eventId ? eventTitleById[team.eventId] || `Мероприятие #${team.eventId}` : "";
    const directionLabel = team.directionId ? directionTitleById[team.directionId] || `Направление #${team.directionId}` : "";
    const projectLabel = team.projectId ? projectTitleById[team.projectId] || `Проект #${team.projectId}` : "";
    return [eventLabel, directionLabel, projectLabel].filter(Boolean).join(" / ");
  };
  const openTeamInfo = (teamId: number) => {
    setTeamInfoId(teamId);
    setTeamInfoOpen(true);
  };
  const closeTeamInfo = () => {
    setTeamInfoOpen(false);
    setTeamInfoId(null);
  };
  const openTeamEdit = (teamId: number) => {
    const team = state.teams.find((t) => Number(t.id) === Number(teamId));
    if (!team) return;
    setTeamEditId(teamId);
    setTeamEditMembers([...team.memberIds]);
    setTeamEditOpen(true);
  };
  const closeTeamEdit = () => {
    setTeamEditOpen(false);
    setTeamEditId(null);
    setTeamEditMembers([]);
  };
  const toggleTeamEditMember = (id: number) => {
    const team = state.teams.find((t) => Number(t.id) === Number(teamEditId));
    if (team?.confirmed) {
      notifyError("Состав подтверждённой команды нельзя менять. Сначала снимите подтверждение.");
      return;
    }
    setTeamEditMembers((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const saveTeamEdit = () => {
    if (teamEditId == null) return;
    const team = state.teams.find((t) => Number(t.id) === Number(teamEditId));
    if (team?.confirmed) {
      notifyError("Состав подтверждённой команды нельзя менять. Сначала снимите подтверждение.");
      return;
    }
    const unique = Array.from(new Set(teamEditMembers));
    if (unique.length === 0) {
      notifyError("Выберите хотя бы одного участника");
      return;
    }
    setState((prev) => ({
      ...prev,
      teams: prev.teams.map((t) => {
        if (Number(t.id) !== Number(teamEditId)) return t;
        const memberRoles = unique.reduce<Record<string, string>>((acc, memberId) => {
          const existingRole = t.memberRoles?.[String(memberId)];
          const knownRole = specializationByOwnerId.get(memberId);
          if (existingRole || knownRole) acc[String(memberId)] = existingRole || knownRole || "";
          return acc;
        }, {});
        return { ...t, memberIds: unique, memberRoles };
      }),
    }));
    notifySuccess("Состав команды обновлён");
    closeTeamEdit();
  };
  const openTaskCard = (type: "parent" | "subtask", id: number) => {
    setTaskCard({ type, id });
    setTaskCardOpen(true);
  };
  const closeTaskCard = () => {
    setTaskCardOpen(false);
    setTaskCard(null);
  };
  const openCloseEnrollment = (eventId: number, eventTitle: string) => {
    setCloseEnrollmentTarget({ eventId, eventTitle });
  };
  const openDeleteTeamConfirm = (teamId: number) => {
    const team = state.teams.find((item) => Number(item.id) === Number(teamId));
    if (!team) return;
    if (team.confirmed) {
      notifyError("Сначала расформируйте команду, затем удалите её.");
      return;
    }

    setDeleteTeamTargetId(teamId);
  };
  const closeDeleteTeamConfirm = () => {
    setDeleteTeamTargetId(null);
  };
  const confirmDeleteTeam = () => {
    if (deleteTeamTargetId == null) return;
    pruneMissingTeamDesksOnNextSaveRef.current = true;
    setState((prev) => removeTeamCascade(prev, deleteTeamTargetId));
    setDeleteTeamTargetId(null);
    notifySuccess("Команда удалена");
  };

  const snapshotParticipants = (closedEventIds = state.closedEventIds, sourceRequests = requests) =>
    buildParticipantsFromRequests(users, sourceRequests, closedEventIds);

  const projectApplicantGroups = useMemo(
    () =>
      buildProjectApplicantGroups({
        crmCatalog,
        requests,
        closedEventIds: state.closedEventIds,
        userNameById,
        eventTitleById,
        directionTitleById,
      }),
    [crmCatalog, directionTitleById, eventTitleById, requests, state.closedEventIds, userNameById]
  );

  const applicantsTree = useMemo(
    () => buildApplicantsTree(projectApplicantGroups, state.closedEventIds, hiddenEventIdSet),
    [hiddenEventIdSet, projectApplicantGroups, state.closedEventIds]
  );
  const toggleApplicantForGroup = (groupKey: string, ownerId: number) => {
    setActiveTeamBuilderGroupKey(groupKey);
    setSelectedApplicantsByGroup((prev) => {
      const current = prev[groupKey] || [];
      const hasOwner = current.includes(ownerId);
      const next = hasOwner ? current.filter((id) => id !== ownerId) : [...current, ownerId];
      return { ...prev, [groupKey]: next };
    });
  };

  const createTeamFromGroup = (group: ProjectApplicantsGroup, teamNameOverride?: string) => {
    const selectedOwnerIds = Array.from(new Set(selectedApplicantsByGroup[group.key] || []));
    const availableIds = new Set(group.applicants.map((a) => a.ownerId));
    const assignedIds = group.eventId
      ? new Set(
        state.teams
          .filter((team) => Number(team.eventId) === Number(group.eventId))
          .flatMap((team) => team.memberIds.map((memberId) => Number(memberId)))
      )
      : new Set<number>();
    const memberIds = selectedOwnerIds.filter((id) => availableIds.has(id) && !assignedIds.has(Number(id)));
    if (memberIds.length === 0) {
      notifyError("Выберите хотя бы одного участника");
      return;
    }

    const rawName = (teamNameOverride ?? teamNameByGroup[group.key] ?? "").trim();
    if (!rawName) {
      notifyError("Введите название команды");
      return;
    }
    const teamName = rawName;

    const curatorRaw = teamCuratorByGroup[group.key];
    const curatorIdNum = curatorRaw ? Number(curatorRaw) : undefined;
    const curatorId = typeof curatorIdNum === "number" && !Number.isNaN(curatorIdNum) ? curatorIdNum : undefined;
    const directionIdNum = Number(teamDirectionByGroup[group.key]);
    const projectIdNum = Number(teamProjectByGroup[group.key]);
    const directionId = Number.isFinite(directionIdNum) && directionIdNum > 0 ? directionIdNum : undefined;

    const requestIds = group.applicants.filter((a) => memberIds.includes(a.ownerId)).flatMap((a) => a.requestIds);
    const projectId = Number.isFinite(projectIdNum) && projectIdNum > 0
      ? projectIdNum
      : resolveProjectIdFromRequestIds(requestIds);
    const memberRoles = group.applicants
      .filter((applicant) => memberIds.includes(applicant.ownerId) && applicant.specialization)
      .reduce<Record<string, string>>((acc, applicant) => {
        acc[String(applicant.ownerId)] = String(applicant.specialization);
        return acc;
      }, {});
    const created: PlannerTeam = {
      id: nextPlannerId(state.teams),
      name: teamName,
      curatorId,
      memberIds,
      memberRoles,
      confirmed: false,
      eventId: group.eventId,
      directionId,
      projectId,
      sourceRequestIds: requestIds,
      createdBy: userId || undefined,
      updatedAt: currentTimestamp(),
    };

    setState((prev) => {
      const participantsById = new Map(prev.participants.map((p) => [Number(p.id), p]));
      memberIds.forEach((id) => {
        const fullName =
          group.applicants.find((a) => a.ownerId === id)?.name ||
          userNameById.get(id) ||
          requestStudentNameById.get(id) ||
          `Участник #${id}`;
        participantsById.set(id, { id, fullName });
      });
      return {
        ...prev,
        participants: Array.from(participantsById.values()),
        teams: [...prev.teams, created],
      };
    });

    syncProjectCurator(projectId, curatorId);

    setSelectedApplicantsByGroup((prev) => ({ ...prev, [group.key]: [] }));
    setTeamNameByGroup((prev) => ({ ...prev, [group.key]: "" }));
    setTeamCuratorByGroup((prev) => ({ ...prev, [group.key]: "" }));
    setTeamDirectionByGroup((prev) => ({ ...prev, [group.key]: "" }));
    setTeamProjectByGroup((prev) => ({ ...prev, [group.key]: "" }));
    notifySuccess("Команда сформирована");
  };

  const addParentTask = () => {
    const teamId = Number(activeTeamId);
    if (!teamId || !canEditTeam(teamId)) {
      notifyError("Нет прав или команда не выбрана");
      return;
    }
    if (!parentTitle.trim()) {
      notifyError("Проверьте поля большой задачи");
      return;
    }

    if (parentStart && parentEnd) {
      if (parentStart > parentEnd) {
        notifyError("Проверьте сроки большой задачи");
        return;
      }
    }

    setState((prev) => ({
      ...prev,
      parentTasks: [
        ...prev.parentTasks,
        {
          id: nextPlannerId(prev.parentTasks),
          teamId,
          title: parentTitle.trim(),
          assigneeId: parentAssigneeId ? Number(parentAssigneeId) : undefined,
          startDate: parentStart,
          endDate: parentEnd,
          createdBy: userId || undefined,
          updatedAt: currentTimestamp(),
        },
      ],
    }));
    setParentTitle("");
    setParentAssigneeId("");
    setParentStart(undefined);
    setParentEnd(undefined);
    notifySuccess("Большая задача добавлена");
  };

  const addSubtask = () => {
    if (!selectedParent) {
      notifyError("Выберите большую задачу");
      return;
    }
    if (!canEditTeam(selectedParent.teamId)) {
      notifyError("Нет прав на подзадачи этой команды");
      return;
    }
    if (!subTitle.trim() || !subAssigneeId) {
      notifyError("Проверьте поля подзадачи");
      return;
    }

    const created: PlannerSubtask = {
      id: nextPlannerId(state.subtasks),
      teamId: selectedParent.teamId,
      parentTaskId: selectedParent.id,
      title: subTitle.trim(),
      role: "",
      assigneeId: Number(subAssigneeId),
      startDate: subStart,
      endDate: subEnd,
      status: plannedColumn,
      inSprint: true,
      createdBy: userId || undefined,
      updatedAt: currentTimestamp(),
    };
    setState((prev) => ({ ...prev, subtasks: [...prev.subtasks, created] }));
    setSubTitle("");
    setSubAssigneeId("0");
    setSubStart(undefined);
    setSubEnd(undefined);
    setSubInSprint(true);
    notifySuccess("Подзадача добавлена");
  };

  const startEditParent = (parentId: number) => {
    const parent = state.parentTasks.find((p) => Number(p.id) === Number(parentId));
    if (!parent || !canEditTeam(parent.teamId)) return;
    setEditingParentId(parent.id);
    setEditingParentDraft({
      title: parent.title,
      assigneeId: parent.assigneeId,
      startDate: parent.startDate ? dayjs(parent.startDate) : undefined,
      endDate: parent.endDate ? dayjs(parent.endDate) : undefined,
    });
  };

  const cancelEditParent = () => {
    setEditingParentId(null);
    setEditingParentDraft(null);
  };

  const saveEditedParent = () => {
    if (!editingParentId || !editingParentDraft) return;
    const nextTitle = editingParentDraft.title.trim();
    if (!nextTitle) {
      notifyError("Проверьте поля большой задачи");
      return;
    }

    setState((prev) => ({
      ...prev,
      parentTasks: prev.parentTasks.map((p) =>
        Number(p.id) === Number(editingParentId)
          ? {
            ...p,
            title: nextTitle,
            assigneeId: editingParentDraft.assigneeId,
            startDate: editingParentDraft.startDate ? dayjs(editingParentDraft.startDate) : undefined,
            endDate: editingParentDraft.endDate ? dayjs(editingParentDraft.endDate) : undefined,
            updatedAt: currentTimestamp(),
          }
          : p
      ),
    }));
    cancelEditParent();
    notifySuccess("Большая задача обновлена");
  };

  const startEditSubtask = (subtaskId: number) => {
    const subtask = state.subtasks.find((s) => Number(s.id) === Number(subtaskId));
    if (!subtask || !canEditTeam(subtask.teamId)) return;
    setEditingSubtaskId(subtask.id);
    setEditingSubtaskDraft({
      title: subtask.title,
      assigneeId: subtask.assigneeId,
      startDate: subtask.startDate ? dayjs(subtask.startDate) : undefined,
      endDate: subtask.endDate ? dayjs(subtask.endDate) : undefined,
      status: subtask.status,
      inSprint: subtask.inSprint,
    });
  };

  const cancelEditSubtask = () => {
    setEditingSubtaskId(null);
    setEditingSubtaskDraft(null);
  };

  const saveEditedSubtask = () => {
    if (!editingSubtaskId || !editingSubtaskDraft) return;
    const nextTitle = editingSubtaskDraft.title.trim();

    if (!nextTitle) {
      notifyError("Проверьте поля подзадачи");
      return;
    }
    const current = state.subtasks.find((s) => Number(s.id) === Number(editingSubtaskId));
    const parent = state.parentTasks.find((p) => Number(p.id) === Number(current?.parentTaskId));
    if (!current || !parent) return;

    const safeStatus =
      editingSubtaskDraft.inSprint && !current.inSprint
        ? plannedColumn
        : state.columns.includes(editingSubtaskDraft.status)
          ? editingSubtaskDraft.status
          : state.columns.includes(current.status)
            ? current.status
            : plannedColumn;
    setState((prev) => ({
      ...prev,
      subtasks: prev.subtasks.map((s) =>
        Number(s.id) === Number(editingSubtaskId)
          ? {
            ...s,
            title: nextTitle,
            assigneeId: editingSubtaskDraft.assigneeId,
            startDate: editingSubtaskDraft.startDate,
            endDate: editingSubtaskDraft.endDate,
            status: safeStatus,
            inSprint: Boolean(editingSubtaskDraft.inSprint),
            updatedAt: currentTimestamp(),
          }
          : s
      ),
    }));
    cancelEditSubtask();
    notifySuccess("Подзадача обновлена");
  };

  const removeKanbanColumn = (title: string) => {
    if (DEFAULT_KANBAN_COLUMNS.includes(title)) {
      notifyError("Базовые колонки удалять нельзя");
      return;
    }
    if (state.columns.length <= 1) {
      notifyError("Должна остаться хотя бы одна колонка");
      return;
    }

    const nextColumns = state.columns.filter((c) => c !== title);
    const fallbackStatus = nextColumns[0] || DEFAULT_KANBAN_COLUMNS[0];

    setState((prev) => ({
      ...prev,
      columns: nextColumns,
      subtasks: prev.subtasks.map((s) => (s.status === title ? { ...s, status: fallbackStatus } : s)),
    }));

    notifySuccess("Колонка удалена");
  };

  const confirmCloseEnrollment = async () => {
    if (!closeEnrollmentTarget) return;
    const eventId = closeEnrollmentTarget.eventId;
    const eventTitle = closeEnrollmentTarget.eventTitle;
    const nextClosedEventIds = Array.from(new Set([...state.closedEventIds, eventId]));
    const statusEquals = (status: string | undefined, target: string) =>
      String(status || "").trim().toLowerCase() === target.toLowerCase();
    const inviteTargets = requests.filter(
      (request) => Number(request.eventId) === Number(eventId) && statusEquals(request.status, REQUEST_STATUS.JOINED_CHAT)
    );
    let nextRequests = requests;

    if (inviteTargets.length > 0) {
      const results = await Promise.allSettled(
        inviteTargets.map((request) => updateRequestStatus(request.id, REQUEST_STATUS.ENROLLMENT_CLOSED))
      );
      const updatedById = new Map<number, Request>();

      results.forEach((result) => {
        if (result.status === "fulfilled" && result.value) {
          updatedById.set(Number(result.value.id), result.value);
        }
      });

      nextRequests = requests.map((request) => updatedById.get(Number(request.id)) ?? request);
      setRequests(nextRequests);

      const failedCount = results.filter((result) => result.status === "rejected").length;
      if (failedCount > 0) {
        notifyError(`Не удалось отправить приглашения для ${failedCount} заявок. Повторите завершение набора.`);
        return;
      }
    }

    setState((prev) => ({
      ...prev,
      enrollmentClosed: true,
      closedEventIds: nextClosedEventIds,
      participants: snapshotParticipants(nextClosedEventIds, nextRequests),
    }));
    setCloseEnrollmentTarget(null);
    notifySuccess(
      inviteTargets.length > 0
        ? `Набор по мероприятию «${eventTitle}» завершён, приглашения отправлены`
        : `Набор по мероприятию «${eventTitle}» завершён`
    );
  };

  const toggleEventVisibility = (eventId: number, enabled: boolean) => {
    if (!Number.isFinite(eventId) || eventId <= 0) return;
    setState((prev) => {
      const hiddenSet = new Set(prev.hiddenEventIds.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0));
      if (enabled) {
        hiddenSet.delete(eventId);
      } else {
        hiddenSet.add(eventId);
      }
      return { ...prev, hiddenEventIds: Array.from(hiddenSet).sort((a, b) => a - b) };
    });
  };

  const moveKanbanSubtask = (subtaskId: number, column: string, position: number) => {
    setState((prev) => {
      const moved = prev.subtasks.find((subtask) => Number(subtask.id) === Number(subtaskId));
      if (!moved || !canMoveSubtask(moved)) return prev;

      const movedNext: PlannerSubtask = { ...moved, status: column, inSprint: true, updatedAt: currentTimestamp() };
      const targetSubtasks = prev.subtasks.filter(
        (subtask) =>
          Number(subtask.id) !== Number(subtaskId) &&
          Number(subtask.teamId) === Number(moved.teamId) &&
          subtask.inSprint &&
          subtask.status === column
      );
      const safePosition = Math.max(0, Math.min(position, targetSubtasks.length));

      let targetIndex = 0;
      let inserted = false;
      const subtasks: PlannerSubtask[] = [];

      prev.subtasks.forEach((subtask) => {
        if (Number(subtask.id) === Number(subtaskId)) return;

        const isTargetColumn =
          Number(subtask.teamId) === Number(moved.teamId) && subtask.inSprint && subtask.status === column;
        if (isTargetColumn && !inserted && targetIndex === safePosition) {
          subtasks.push(movedNext);
          inserted = true;
        }

        subtasks.push(subtask);
        if (isTargetColumn) targetIndex += 1;
      });

      if (!inserted) subtasks.push(movedNext);

      return { ...prev, subtasks };
    });
  };

  const moveKanbanColumn = (sourceTitle: string, targetTitle: string) => {
    setState((prev) => {
      const fromIndex = prev.columns.indexOf(sourceTitle);
      const toIndex = prev.columns.indexOf(targetTitle);
      if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return prev;

      const columns = [...prev.columns];
      const [moved] = columns.splice(fromIndex, 1);
      columns.splice(toIndex, 0, moved);

      return { ...prev, columns };
    });
  };

  const taskCardParent = taskCard?.type === "parent"
    ? state.parentTasks.find((p) => Number(p.id) === Number(taskCard.id)) ?? null
    : null;
  const taskCardSubtask = taskCard?.type === "subtask"
    ? state.subtasks.find((s) => Number(s.id) === Number(taskCard.id)) ?? null
    : null;
  const taskCardTeamId = taskCardSubtask?.teamId ?? taskCardParent?.teamId;
  const taskCardTeam = taskCardTeamId ? state.teams.find((t) => Number(t.id) === Number(taskCardTeamId)) ?? null : null;
  const taskCardParentForSubtask = taskCardSubtask
    ? state.parentTasks.find((p) => Number(p.id) === Number(taskCardSubtask.parentTaskId)) ?? null
    : null;
  const taskCardSubtasksCount = taskCardParent
    ? state.subtasks.filter((s) => Number(s.parentTaskId) === Number(taskCardParent.id)).length
    : 0;
  const teamInfoTeam = teamInfoId != null ? state.teams.find((t) => Number(t.id) === Number(teamInfoId)) ?? null : null;
  const deleteTeamTarget = deleteTeamTargetId != null ? state.teams.find((t) => Number(t.id) === Number(deleteTeamTargetId)) ?? null : null;
  const teamEditTeam = teamEditId != null ? state.teams.find((t) => Number(t.id) === Number(teamEditId)) ?? null : null;
  const teamEditCandidateIds = (() => {
    const ids = new Set<number>();
    if (teamEditTeam?.eventId) {
      requests.forEach((request) => {
        const ownerId = Number(request.ownerId);
        if (!Number.isFinite(ownerId)) return;
        if (Number(request.eventId) === Number(teamEditTeam.eventId)) {
          if (state.closedEventIds.includes(Number(teamEditTeam.eventId)) && !hasPlannerAccessStatus(request.status)) {
            return;
          }
          ids.add(ownerId);
        }
      });
    } else if (teamEditTeam?.sourceRequestIds?.length) {
      const sourceIds = new Set(teamEditTeam.sourceRequestIds.map((id) => Number(id)));
      requests.forEach((request) => {
        const ownerId = Number(request.ownerId);
        if (!Number.isFinite(ownerId)) return;
        if (sourceIds.has(Number(request.id))) {
          if (teamEditTeam.eventId && state.closedEventIds.includes(Number(teamEditTeam.eventId)) && !hasPlannerAccessStatus(request.status)) {
            return;
          }
          ids.add(ownerId);
        }
      });
    }
    (teamEditTeam?.memberIds || []).forEach((id) => ids.add(Number(id)));
    return Array.from(ids)
      .filter((id) => Number.isFinite(id))
      .sort((a, b) => displayNameForUserId(a).localeCompare(displayNameForUserId(b), "ru"));
  })();

  if (!user) return <div className="page planner-page"><div className="planner-empty">Войдите для доступа к планировщику.</div></div>;
  if (loading) return <div className="page planner-page"><PageLoader /></div>;
  if (!studentHasPlannerAccess) {
    return (
      <div className="page planner-page">
        <div className="planner-empty">Доступ откроется после завершения набора по мероприятию.</div>
      </div>
    );
  }

  return (
    <div className="page planner-page">
      <PlannerTabs tab={tab} onChange={setTab} onOpenAutomation={isOrganizer ? openPlannerAutomation : undefined} />

      {studentWaitingForConfirmedTeam && (
        <div className="planner-card planner-access-note">
          <h3 className="h3">Доступ к планировщику открыт</h3>
          <p>
            Набор завершён, вы добавлены в список участников. Рабочие вкладки станут доступны после того, как организатор
            сформирует и подтвердит вашу команду.
          </p>
        </div>
      )}

      {!studentWaitingForConfirmedTeam && tab === "teams" && (
        <TeamsTab
          isOrganizer={isOrganizer}
          state={state}
          applicantsTree={applicantsTree}
          selectedApplicantsByGroup={selectedApplicantsByGroup}
          teamNameByGroup={teamNameByGroup}
          teamCuratorByGroup={teamCuratorByGroup}
          teamDirectionByGroup={teamDirectionByGroup}
          teamProjectByGroup={teamProjectByGroup}
          activeTeamBuilderGroupKey={activeTeamBuilderGroupKey}
          curatorUsers={curatorUsers}
          visibleTeams={visibleTeams}
          userNameById={userNameById}
          onOpenConfirmCloseEnrollment={openCloseEnrollment}
          onToggleEventVisibility={toggleEventVisibility}
          onSyncParticipants={() => setState((prev) => ({ ...prev, participants: snapshotParticipants(prev.closedEventIds) }))}
          onToggleApplicantForGroup={toggleApplicantForGroup}
          onSelectBuilderGroup={setActiveTeamBuilderGroupKey}
          onTeamNameChange={(groupKey, value) => setTeamNameByGroup((prev) => ({ ...prev, [groupKey]: value }))}
          onTeamCuratorChange={(groupKey, value) => setTeamCuratorByGroup((prev) => ({ ...prev, [groupKey]: value }))}
          onTeamDirectionChange={(groupKey, value) => {
            setTeamDirectionByGroup((prev) => ({ ...prev, [groupKey]: value }));
            setTeamProjectByGroup((prev) => ({ ...prev, [groupKey]: "" }));
          }}
          onTeamProjectChange={(groupKey, value) => setTeamProjectByGroup((prev) => ({ ...prev, [groupKey]: value }))}
          onCreateTeamFromGroup={createTeamFromGroup}
          onRenameTeam={(teamId, value) =>
            setState((prev) => ({
              ...prev,
              teams: prev.teams.map((team) => (team.id === teamId && !team.confirmed ? { ...team, name: value } : team)),
            }))
          }
          onToggleTeamConfirmed={(teamId) =>
            setState((prev) => ({
              ...prev,
              teams: prev.teams.map((team) => (team.id === teamId ? { ...team, confirmed: !team.confirmed } : team)),
            }))
          }
          onOpenTeamInfo={openTeamInfo}
          onOpenTeamEdit={openTeamEdit}
          onAssignTeamCurator={(teamId, curatorId) => {
            const targetTeam = state.teams.find((team) => Number(team.id) === Number(teamId));
            const nextState = {
              ...state,
              teams: state.teams.map((team) =>
                Number(team.id) === Number(teamId) ? { ...team, curatorId, updatedAt: currentTimestamp() } : team
              ),
            };

            setState(nextState);
            void savePlannerState(nextState, teamId);

            syncProjectCurator(resolveTeamProjectId(targetTeam), curatorId);

            notifySuccess("Куратор назначен");
          }}
          onClearTeamCurator={(teamId) => {
            const targetTeam = state.teams.find((team) => Number(team.id) === Number(teamId));
            const projectId = resolveTeamProjectId(targetTeam);
            const nextState = {
              ...state,
              teams: state.teams.map((team) =>
                Number(team.id) === Number(teamId) ? { ...team, curatorId: undefined, updatedAt: currentTimestamp() } : team
              ),
            };

            setState(nextState);
            void savePlannerState(nextState, teamId);

            const remainingCuratorIds = Array.from(
              new Set(
                nextState.teams
                  .filter((team) => Number(resolveTeamProjectId(team)) === Number(projectId))
                  .map((team) => Number(team.curatorId))
                  .filter((curatorId) => Number.isFinite(curatorId) && curatorId > 0)
              )
            );

            if (remainingCuratorIds.length === 1) {
              syncProjectCurator(projectId, remainingCuratorIds[0]);
            } else {
              clearProjectCurator(projectId);
            }

            notifySuccess("Куратор убран");
          }}
          onDeleteTeam={openDeleteTeamConfirm}
          sourceLabelForTeam={sourceLabelForTeam}
        />
      )}

      {!studentWaitingForConfirmedTeam && tab === "backlog" && (
        <BacklogTab
          activeTeamName={activeTeam?.name || ""}
          parentTitle={parentTitle}
          parentAssigneeId={parentAssigneeId}
          parentStart={parentStart}
          parentEnd={parentEnd}
          onParentTitleChange={setParentTitle}
          onParentAssigneeChange={setParentAssigneeId}
          onParentStartChange={setParentStart}
          onParentEndChange={setParentEnd}
          onAddParentTask={addParentTask}
          activeTeamMembers={activeTeamMembers}
          filteredParents={filteredParents}
          selectedParentId={selectedParentId}
          onSelectParent={setSelectedParentId}
          editingParentId={editingParentId}
          editingParentDraft={editingParentDraft}
          setEditingParentDraft={setEditingParentDraft}
          onOpenTaskCard={openTaskCard}
          onStartEditParent={startEditParent}
          onSaveEditedParent={saveEditedParent}
          onCancelEditParent={cancelEditParent}
          onDeleteParent={(parentId) =>
            setState((prev) => ({
              ...prev,
              parentTasks: prev.parentTasks.filter((parentTask) => parentTask.id !== parentId),
              subtasks: prev.subtasks.filter((subtask) => subtask.parentTaskId !== parentId),
            }))
          }
          canEditTeam={canEditTeam}
          selectedParent={selectedParent}
          selectedTeamMembers={selectedTeamMembers}
          subAssigneeId={subAssigneeId}
          subTitle={subTitle}
          subStart={subStart}
          subEnd={subEnd}
          subInSprint={subInSprint}
          onSubAssigneeChange={setSubAssigneeId}
          onSubTitleChange={setSubTitle}
          onSubStartChange={setSubStart}
          onSubEndChange={setSubEnd}
          onSubInSprintChange={setSubInSprint}
          onAddSubtask={addSubtask}
          filteredSubtasks={filteredSubtasks}
          assigneeFilter={assigneeFilter}
          assigneeFilterOptions={assigneeFilterOptions}
          onAssigneeFilterChange={setAssigneeFilter}
          editingSubtaskId={editingSubtaskId}
          editingSubtaskDraft={editingSubtaskDraft}
          setEditingSubtaskDraft={setEditingSubtaskDraft}
          getTeamMemberIds={getTeamMemberIds}
          displayAssigneeLabel={displayAssigneeLabel}
          onStartEditSubtask={startEditSubtask}
          onSaveEditedSubtask={saveEditedSubtask}
          onCancelEditSubtask={cancelEditSubtask}
          onDeleteSubtask={(subtaskId) =>
            setState((prev) => ({ ...prev, subtasks: prev.subtasks.filter((subtask) => subtask.id !== subtaskId) }))
          }

          visibleTeams={visibleTeams}
          teamFilter={teamFilter}
          onTeamFilterChange={setTeamFilter}
        />
      )}

      {!studentWaitingForConfirmedTeam && tab === "kanban" && (
        <KanbanTab
          newColumn={newColumn}
          columns={state.columns}
          filteredSubtasks={filteredSubtasks}
          assigneeFilter={assigneeFilter}
          assigneeFilterOptions={assigneeFilterOptions}
          onAssigneeFilterChange={setAssigneeFilter}
          canEditTeam={canEditTeam}
          displayAssigneeLabel={displayAssigneeLabel}
          currentUserId={userId}
          onNewColumnChange={setNewColumn}
          onAddColumn={() => {
            const title = newColumn.trim();
            if (!title) return;
            if (state.columns.some((column) => column.toLowerCase() === title.toLowerCase())) return;
            setState((prev) => ({ ...prev, columns: [...prev.columns, title] }));
            setNewColumn("");
          }}
          onRemoveColumn={removeKanbanColumn}
          onOpenTaskCard={openTaskCard}
          onMoveSubtask={moveKanbanSubtask}
          onMoveColumn={moveKanbanColumn}
        />
      )}

      {!studentWaitingForConfirmedTeam && tab === "gantt" && (
        <GanttTab
          activeTeamName={activeTeam?.name || ""}
          parents={filteredParents}
          subtasks={filteredSubtasks}
          displayAssigneeLabel={displayAssigneeLabel}
          onOpenTaskCard={openTaskCard}
        />
      )}

      <ConfirmCloseEnrollmentModal
        isOpen={Boolean(closeEnrollmentTarget)}
        eventTitle={closeEnrollmentTarget?.eventTitle}
        onClose={() => setCloseEnrollmentTarget(null)}
        onConfirm={confirmCloseEnrollment}
      />
      <ConfirmDeleteTeamModal
        isOpen={Boolean(deleteTeamTarget)}
        team={deleteTeamTarget}
        onClose={closeDeleteTeamConfirm}
        onConfirm={confirmDeleteTeam}
      />
      <TeamInfoModal
        isOpen={teamInfoOpen}
        team={teamInfoTeam}
        specializationByOwnerId={specializationByOwnerId}
        displayNameForUserId={displayNameForUserId}
        onClose={closeTeamInfo}
      />
      <TeamEditModal
        isOpen={teamEditOpen}
        team={teamEditTeam}
        teamEditMembers={teamEditMembers}
        candidateIds={teamEditCandidateIds}
        displayAssigneeLabel={displayAssigneeLabel}
        onToggleMember={toggleTeamEditMember}
        onClose={closeTeamEdit}
        onSave={saveTeamEdit}
      />
      <TaskCardModal
        isOpen={taskCardOpen}
        taskCardParent={taskCardParent}
        taskCardSubtask={taskCardSubtask}
        taskCardTeam={taskCardTeam}
        taskCardParentForSubtask={taskCardParentForSubtask}
        taskCardSubtasksCount={taskCardSubtasksCount}
        displayAssigneeLabel={displayAssigneeLabel}
        sourceLabelForTeam={sourceLabelForTeam}
        onClose={closeTaskCard}
      />
      <AntModal
        open={automationOpen}
        onCancel={() => setAutomationOpen(false)}
        footer={null}
        width="min(1380px, calc(100vw - 32px))"
        centered
        destroyOnHidden
        className="planner-automation-modal"
        title="Настройка роботов и триггеров планировщика"
      >
        {plannerAutomationEventId && (
          <AutomationPanel scope="planner" lockedEventId={plannerAutomationEventId} className="automation-panel--modal" />
        )}
      </AntModal>
    </div>
  );
}




