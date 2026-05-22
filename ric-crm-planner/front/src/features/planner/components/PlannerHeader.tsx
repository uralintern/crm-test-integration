import type { PlannerTeam } from "../../../types/planner";
import AppSelect from "../../../components/UI/Select";

type PlannerHeaderProps = {
  visibleTeams: PlannerTeam[];
  teamFilter: string;
  onTeamFilterChange: (value: string) => void;
};

export default function PlannerHeader({ visibleTeams, teamFilter, onTeamFilterChange }: PlannerHeaderProps) {
  return (
    <div className="planner-head">
      <h1 className="h1">Планировщик</h1>
      <label className="planner-label">
        Команда
        <AppSelect
          value={teamFilter || ""}
          onChange={(value) => onTeamFilterChange(String(value))}
          disabled={visibleTeams.length === 0}
          options={
            visibleTeams.length === 0
              ? [{ value: "", label: "Нет команд" }]
              : visibleTeams.map((team) => ({ value: String(team.id), label: team.name }))
          }
        />
      </label>
    </div>
  );
}
