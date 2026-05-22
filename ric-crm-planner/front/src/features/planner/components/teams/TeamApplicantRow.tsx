import type { ProjectApplicantsGroup } from "../../planner.types";

type Applicant = ProjectApplicantsGroup["applicants"][number];

type TeamApplicantInfoProps = {
  applicant: Applicant;
};

type TeamApplicantHeaderProps = {
  compact?: boolean;
};

export function TeamApplicantInfo({ applicant }: TeamApplicantInfoProps) {
  return (
    <div className={`planner-applicant-columns ${applicant.desiredDirections.length === 0 ? "planner-applicant-columns--compact" : ""}`}>
      <span className="planner-applicant-name">{applicant.name}</span>
      <span className="planner-applicant-specialization">{applicant.specialization || "Без специализации"}</span>
      {applicant.desiredDirections.length > 0 && (
        <span className="planner-applicant-directions">
          {applicant.desiredDirections.map((direction) => (
            <span key={`${applicant.ownerId}:${direction.id ?? direction.title}`}>{direction.title}</span>
          ))}
        </span>
      )}
    </div>
  );
}

export function TeamApplicantHeader({ compact = false }: TeamApplicantHeaderProps) {
  return (
    <div className="planner-applicant-row planner-applicant-row--header" aria-hidden="true">
      <div className={`planner-applicant-columns planner-applicant-columns--header ${compact ? "planner-applicant-columns--compact" : ""}`}>
        <span>ФИ</span>
        <span>Специализация</span>
        {!compact && <span>Желаемое направление</span>}
      </div>
      <span className="planner-applicant-switch-placeholder" />
    </div>
  );
}
