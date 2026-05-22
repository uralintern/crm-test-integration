import { useState } from "react";
import type { SyntheticEvent } from "react";
import { InfoCircleOutlined } from "@ant-design/icons";
import type { PlannerState, PlannerTeam } from "../../../../types/planner";
import type { User } from "../../../../types/user";
import type { ApplicantsTreeNode, ProjectApplicantsGroup } from "../../planner.types";
import { fullName } from "../../planner.utils";
import AppButton from "../../../../components/UI/Button";
import AppInput from "../../../../components/UI/Input";
import AppSelect from "../../../../components/UI/Select";
import AppSwitch from "../../../../components/UI/Switch";
import { TeamApplicantHeader, TeamApplicantInfo } from "../teams/TeamApplicantRow";

type TeamsTabProps = {
  isOrganizer: boolean;
  state: PlannerState;
  applicantsTree: ApplicantsTreeNode[];
  selectedApplicantsByGroup: Record<string, number[]>;
  teamNameByGroup: Record<string, string>;
  teamCuratorByGroup: Record<string, string>;
  teamDirectionByGroup: Record<string, string>;
  teamProjectByGroup: Record<string, string>;
  activeTeamBuilderGroupKey: string;
  currentUser: User;
  visibleTeams: PlannerTeam[];
  userNameById: Map<number, string>;
  onOpenConfirmCloseEnrollment: (eventId: number, eventTitle: string) => void;
  onToggleEventVisibility: (eventId: number, enabled: boolean) => void;
  onSyncParticipants: () => void;
  onToggleApplicantForGroup: (groupKey: string, ownerId: number) => void;
  onSelectBuilderGroup: (groupKey: string) => void;
  onTeamNameChange: (groupKey: string, value: string) => void;
  onTeamCuratorChange: (groupKey: string, value: string) => void;
  onTeamDirectionChange: (groupKey: string, value: string) => void;
  onTeamProjectChange: (groupKey: string, value: string) => void;
  onCreateTeamFromGroup: (group: ProjectApplicantsGroup, teamNameOverride?: string) => void;
  onRenameTeam: (teamId: number, value: string) => void;
  onToggleTeamConfirmed: (teamId: number) => void;
  onOpenTeamInfo: (teamId: number) => void;
  onOpenTeamEdit: (teamId: number) => void;
  onAssignTeamCurator: (teamId: number, curatorId: number) => void;
  onDeleteTeam: (teamId: number) => void;
  sourceLabelForTeam: (team: PlannerTeam) => string;
};

function stopSummaryToggle(event: SyntheticEvent) {
  event.preventDefault();
  event.stopPropagation();
}

const TEAM_EVENT_OPEN_STATE_KEY = "planner_team_event_open_state_v1";

function readTeamEventOpenState(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(TEAM_EVENT_OPEN_STATE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeTeamEventOpenState(value: Record<string, boolean>) {
  localStorage.setItem(TEAM_EVENT_OPEN_STATE_KEY, JSON.stringify(value));
}

export default function TeamsTab({
  isOrganizer,
  state,
  applicantsTree,
  selectedApplicantsByGroup,
  teamNameByGroup,
  teamCuratorByGroup,
  teamDirectionByGroup,
  teamProjectByGroup,
  activeTeamBuilderGroupKey,
  currentUser,
  visibleTeams,
  userNameById,
  onOpenConfirmCloseEnrollment,
  onToggleEventVisibility,
  onSyncParticipants,
  onToggleApplicantForGroup,
  onSelectBuilderGroup,
  onTeamNameChange,
  onTeamCuratorChange,
  onTeamDirectionChange,
  onTeamProjectChange,
  onCreateTeamFromGroup,
  onRenameTeam,
  onToggleTeamConfirmed,
  onOpenTeamInfo,
  onOpenTeamEdit,
  onAssignTeamCurator,
  onDeleteTeam,
  sourceLabelForTeam,
}: TeamsTabProps) {
  const [eventOpenByKey, setEventOpenByKey] = useState<Record<string, boolean>>(() => readTeamEventOpenState());
  const [curatorEditTeamId, setCuratorEditTeamId] = useState<number | null>(null);
  const [curatorDraftByTeam, setCuratorDraftByTeam] = useState<Record<number, string>>({});
  const hasClosedEvents = state.closedEventIds.length > 0;
  const groups = applicantsTree.map((node) => node.group);
  const assignedOwnerIdsByEventId = new Map<number, Set<number>>();
  visibleTeams.forEach((team) => {
    const eventId = Number(team.eventId);
    if (!Number.isFinite(eventId) || eventId <= 0) return;
    const assignedIds = assignedOwnerIdsByEventId.get(eventId) || new Set<number>();
    team.memberIds.forEach((memberId) => assignedIds.add(Number(memberId)));
    assignedOwnerIdsByEventId.set(eventId, assignedIds);
  });
  const fallbackActiveGroup =
    groups.find((group) => (selectedApplicantsByGroup[group.key] || []).length > 0) || groups[0] || null;
  const activeGroup = groups.find((group) => group.key === activeTeamBuilderGroupKey) || fallbackActiveGroup;
  const activeSelectedIds = activeGroup ? selectedApplicantsByGroup[activeGroup.key] || [] : [];
  const activeSelectedApplicants = activeGroup
    ? activeGroup.applicants.filter((applicant) => activeSelectedIds.includes(applicant.ownerId))
    : [];
  const selectedDirectionId = activeGroup ? teamDirectionByGroup[activeGroup.key] || "" : "";
  const selectedProjectId = activeGroup ? teamProjectByGroup[activeGroup.key] || "" : "";
  const selectedDirection = activeGroup?.directionOptions.find((direction) => String(direction.id) === selectedDirectionId);
  const availableProjects = selectedDirection?.projects || [];

  const setEventOpen = (key: string, open: boolean) => {
    setEventOpenByKey((prev) => {
      const next = { ...prev, [key]: open };
      writeTeamEventOpenState(next);
      return next;
    });
  };

  const getCuratorName = (id: number) => {
    if (Number(id) === Number(currentUser.id)) {
      return fullName(currentUser) || currentUser.email || `ID ${currentUser.id}`;
    }

    return userNameById.get(Number(id)) || `Участник #${id}`;
  };

  const getCuratorOptions = (team: PlannerTeam) => {
    const optionIds = new Set<number>();
    if (Number(currentUser.id)) optionIds.add(Number(currentUser.id));
    team.memberIds.forEach((memberId) => optionIds.add(Number(memberId)));

    return [
      { value: "", label: "Выберите куратора", disabled: true },
      ...Array.from(optionIds).map((id) => ({
        value: String(id),
        label: Number(id) === Number(currentUser.id) ? `Организатор: ${getCuratorName(id)}` : getCuratorName(id),
      })),
    ];
  };

  const submitTeamCurator = (teamId: number) => {
    const curatorId = Number(curatorDraftByTeam[teamId] || 0);
    if (!Number.isFinite(curatorId) || curatorId <= 0) return;

    onAssignTeamCurator(teamId, curatorId);
    setCuratorEditTeamId(null);
    setCuratorDraftByTeam((prev) => {
      const next = { ...prev };
      delete next[teamId];
      return next;
    });
  };

  const renderCreatedTeams = () => (
    <section className="teams-created-block">
      <div className="teams-panel-head teams-panel-head--compact">
        <div>
          <div className="teams-eyebrow">Готовый список</div>
          <h3 className="h3">Сформированные команды</h3>
          <p>{visibleTeams.length ? `${visibleTeams.length} команд` : "Пока нет созданных команд"}</p>
        </div>
      </div>

      <div className="teams-list">
        {visibleTeams.length === 0 && <div className="planner-empty-inline">Команды появятся здесь после формирования.</div>}

        {visibleTeams.map((team) => (
          <div key={team.id} className="team-item">
            <div className="team-top">
              {isOrganizer ? (
                <AppInput
                  value={team.name}
                  disabled={team.confirmed}
                  title={team.confirmed ? "Чтобы изменить название, сначала сними подтверждение команды" : undefined}
                  onChange={(event) => onRenameTeam(team.id, event.target.value)}
                />
              ) : (
                <div className="team-title">{team.name}</div>
              )}

              {isOrganizer ? (
                <div className={`team-badge ${team.confirmed ? "ok" : "draft"}`}>
                  {team.confirmed ? "Подтверждена" : "Черновик"}
                </div>
              ) : (
                <div className="team-badge-stack">
                  <div className={`team-badge ${team.confirmed ? "ok" : "draft"}`}>
                    {team.confirmed ? "Подтверждена" : "Черновик"}
                  </div>
                  <AppButton className="info-icon-btn" type="button" onClick={() => onOpenTeamInfo(team.id)} aria-label="Информация о команде">
                    <InfoCircleOutlined />
                  </AppButton>
                </div>
              )}
            </div>

            <div className="team-meta-grid">
              <div className="team-value">
                <span>Куратор</span>
                {team.curatorId ? userNameById.get(team.curatorId) || `ID ${team.curatorId}` : "-"}
              </div>
              <div className="team-value">
                <span>Участники</span>
                {team.memberIds.length}
              </div>
            </div>

            {sourceLabelForTeam(team) && (
              <div className="team-value team-value--source">
                <span>Источник</span>
                {sourceLabelForTeam(team)}
              </div>
            )}

            {isOrganizer && curatorEditTeamId === team.id && (
              <div className="team-curator-assign">
                <AppSelect
                  value={curatorDraftByTeam[team.id] || ""}
                  onChange={(value) => setCuratorDraftByTeam((prev) => ({ ...prev, [team.id]: String(value) }))}
                  options={getCuratorOptions(team)}
                />
                <AppButton
                  className="primary"
                  type="button"
                  disabled={!curatorDraftByTeam[team.id]}
                  onClick={() => submitTeamCurator(team.id)}
                >
                  Назначить
                </AppButton>
                <AppButton className="link-btn" type="button" onClick={() => setCuratorEditTeamId(null)}>
                  Отмена
                </AppButton>
              </div>
            )}

            {isOrganizer && (
              <div className="team-actions">
                <AppButton className="primary" type="button" onClick={() => onToggleTeamConfirmed(team.id)}>
                  {team.confirmed ? "Расформировать" : "Подтвердить"}
                </AppButton>
                <AppButton className="link-btn" type="button" onClick={() => onOpenTeamEdit(team.id)}>
                  Состав
                </AppButton>
                {!team.curatorId && curatorEditTeamId !== team.id && (
                  <AppButton
                    className="link-btn"
                    type="button"
                    onClick={() => {
                      setCuratorDraftByTeam((prev) => ({ ...prev, [team.id]: prev[team.id] || "" }));
                      setCuratorEditTeamId(team.id);
                    }}
                  >
                    Назначить куратора
                  </AppButton>
                )}
                <AppButton
                  className="danger-outline"
                  type="button"
                  disabled={team.confirmed}
                  title={team.confirmed ? "Сначала расформируйте команду" : undefined}
                  onClick={() => onDeleteTeam(team.id)}
                >
                  Удалить
                </AppButton>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );

  const renderSelectedPanel = () => {
    if (!activeGroup) {
      return (
        <section className="planner-card teams-panel teams-panel--selection">
          <div className="teams-panel-head teams-panel-head--compact">
            <div>
              <div className="teams-eyebrow">Сбор команды</div>
              <h3 className="h3">Выбранные участники</h3>
              <p>Выберите проектантов в мероприятии слева.</p>
            </div>
          </div>
          <div className="planner-empty-inline">Нет доступных мероприятий.</div>
        </section>
      );
    }

    const curatorOptions = [
      { value: "", label: "Куратор команды", disabled: true },
      ...(!activeSelectedApplicants.some((applicant) => Number(applicant.ownerId) === Number(currentUser.id))
        ? [
            {
              value: String(currentUser.id),
              label: `Организатор: ${fullName(currentUser) || currentUser.email || `ID ${currentUser.id}`}`,
            },
          ]
        : []),
      ...activeSelectedApplicants.map((applicant) => ({
        value: String(applicant.ownerId),
        label: applicant.name,
      })),
    ];

    return (
      <section className="planner-card teams-panel teams-panel--selection">
        <div className="teams-panel-head teams-panel-head--compact">
          <div>
            <div className="teams-eyebrow">Сбор команды</div>
            <h3 className="h3">Выбранные участники</h3>
            <p>{activeGroup.eventTitle}</p>
          </div>
          <div className="team-badge draft">{activeSelectedApplicants.length}</div>
        </div>

        <div className="planner-selected-list">
          {activeSelectedApplicants.length === 0 ? (
            <div className="planner-empty-inline">Выберите участников в мероприятии слева.</div>
          ) : (
            <>
              <TeamApplicantHeader compact />
              {activeSelectedApplicants.map((applicant) => (
                <label key={`${activeGroup.key}:selected:${applicant.ownerId}`} className="planner-check planner-applicant-row planner-applicant-row--selected">
                  <div className="planner-applicant-columns planner-applicant-columns--compact">
                    <span className="planner-applicant-name">{applicant.name}</span>
                    <span className="planner-applicant-specialization">{applicant.specialization || "Без специализации"}</span>
                  </div>
                  <AppSwitch checked onChange={() => onToggleApplicantForGroup(activeGroup.key, applicant.ownerId)} compact />
                </label>
              ))}
            </>
          )}
        </div>

        <div className="planner-team-builder-form">
          <AppInput
            value={teamNameByGroup[activeGroup.key] || ""}
            onChange={(event) => onTeamNameChange(activeGroup.key, event.target.value)}
            placeholder="Название команды"
          />

          <AppSelect
            value={selectedDirectionId}
            onChange={(value) => onTeamDirectionChange(activeGroup.key, String(value))}
            disabled={activeGroup.directionOptions.length === 0}
            options={[
              { value: "", label: activeGroup.directionOptions.length ? "Выберите направление" : "У мероприятия нет направлений", disabled: true },
              ...activeGroup.directionOptions.map((direction) => ({ value: String(direction.id), label: direction.title })),
            ]}
          />

          <AppSelect
            value={selectedProjectId}
            onChange={(value) => onTeamProjectChange(activeGroup.key, String(value))}
            disabled={!selectedDirectionId || availableProjects.length === 0}
            options={[
              { value: "", label: availableProjects.length ? "Выберите проект" : "У направления нет проектов", disabled: true },
              ...availableProjects.map((project) => ({ value: String(project.id), label: project.title })),
            ]}
          />

          <AppSelect
            value={teamCuratorByGroup[activeGroup.key] || ""}
            onChange={(value) => onTeamCuratorChange(activeGroup.key, String(value))}
            options={curatorOptions}
          />

          <AppButton className="primary" type="button" onClick={() => onCreateTeamFromGroup(activeGroup, teamNameByGroup[activeGroup.key] || "")}>
            Сформировать команду
          </AppButton>
        </div>
      </section>
    );
  };

  return (
    <div className={`teams-layout ${!isOrganizer ? "teams-layout--single" : ""}`}>
      {isOrganizer && (
        <section className="planner-card teams-panel teams-panel--builder">
          <div className="teams-panel-head">
            <div>
              <div className="teams-eyebrow">Работа с заявками</div>
              <h3 className="h3">Формирование команд</h3>
              <p>Выбери проектантов внутри мероприятия, затем справа задай параметры команды.</p>
            </div>

            {hasClosedEvents && (
              <AppButton className="primary" type="button" onClick={onSyncParticipants}>
                Синхронизировать участников
              </AppButton>
            )}
          </div>

          {hasClosedEvents && (
            <div className="planner-note teams-note">
              Для мероприятий с завершённым набором в планировщике остаются только участники со статусом «Приступил к ПШ».
            </div>
          )}

          <div className="planner-source-tree">
            {applicantsTree.length === 0 ? (
              <div className="planner-empty-inline">Нет заявок для формирования команд.</div>
            ) : (
              applicantsTree.map((eventNode) => {
                const group = eventNode.group;
                const eventId = typeof eventNode.eventId === "number" ? eventNode.eventId : null;
                const isVisibleInTeams = !eventNode.eventHidden;
                const selectedIds = selectedApplicantsByGroup[group.key] || [];
                const assignedIds = eventId ? assignedOwnerIdsByEventId.get(eventId) || new Set<number>() : new Set<number>();
                const availableApplicants = group.applicants.filter(
                  (applicant) => !selectedIds.includes(applicant.ownerId) && !assignedIds.has(Number(applicant.ownerId))
                );
                const allApplicantsAssigned =
                  group.applicants.length > 0 && group.applicants.every((applicant) => assignedIds.has(Number(applicant.ownerId)));
                const switchControl = (
                  <div className="planner-source-switch" onClick={stopSummaryToggle}>
                    <span>В списке команд</span>
                    <AppSwitch
                      checked={isVisibleInTeams}
                      disabled={!eventId}
                      onChange={(checked) => {
                        if (!eventId) return;
                        onToggleEventVisibility(eventId, checked);
                      }}
                      compact
                    />
                  </div>
                );

                if (!isVisibleInTeams) {
                  return (
                    <div key={eventNode.key} className="planner-source-node planner-source-node--event planner-source-node--disabled">
                      <div className="planner-source-summary planner-source-summary--static">
                        <div className="planner-source-summary-main">
                          <span>Мероприятие: {eventNode.title}</span>
                        </div>

                        <div className="planner-source-summary-actions">
                          <span className="planner-source-meta planner-source-meta--muted">Скрыто из списка команд</span>
                          {switchControl}
                        </div>
                      </div>
                    </div>
                  );
                }

                return (
                  <details
                    key={eventNode.key}
                    className="planner-source-node planner-source-node--event"
                    open={eventOpenByKey[eventNode.key] ?? true}
                    onToggle={(event) => setEventOpen(eventNode.key, event.currentTarget.open)}
                  >
                    <summary className="planner-source-summary" onClick={() => onSelectBuilderGroup(group.key)}>
                      <div className="planner-source-summary-main">
                        <span>Мероприятие: {eventNode.title}</span>
                        <span className="planner-source-meta">{group.applicants.length} участников</span>
                      </div>

                      <div className="planner-source-summary-actions">
                        {eventNode.eventClosed && <span className="planner-source-meta planner-source-meta--closed">Набор завершён</span>}

                        {isOrganizer && eventId && (
                          <>
                            {!eventNode.eventClosed && (
                              <AppButton
                                type="button"
                                className="planner-source-close-btn"
                                onClick={(event) => {
                                  stopSummaryToggle(event);
                                  onOpenConfirmCloseEnrollment(eventId, eventNode.title);
                                }}
                              >
                                Завершить набор
                              </AppButton>
                            )}
                          </>
                        )}

                        {switchControl}
                      </div>
                    </summary>

                    <div className="planner-source-content">
                      {availableApplicants.length === 0 ? (
                        <div className="planner-empty-inline">
                          {group.applicants.length === 0
                            ? "По этому мероприятию пока нет доступных участников."
                            : allApplicantsAssigned
                              ? "Все доступные участники уже распределены по командам."
                              : "Все доступные участники выбраны."}
                        </div>
                      ) : (
                        <div className="planner-members-list">
                          <TeamApplicantHeader />
                          {availableApplicants.map((applicant) => (
                            <label key={`${group.key}:${applicant.ownerId}`} className="planner-check planner-applicant-row">
                              <TeamApplicantInfo applicant={applicant} />
                              <AppSwitch
                                checked={false}
                                onChange={() => onToggleApplicantForGroup(group.key, applicant.ownerId)}
                                compact
                              />
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </details>
                );
              })
            )}
          </div>

          {renderCreatedTeams()}
        </section>
      )}

      {isOrganizer ? renderSelectedPanel() : <section className="planner-card teams-panel teams-panel--created">{renderCreatedTeams()}</section>}
    </div>
  );
}

