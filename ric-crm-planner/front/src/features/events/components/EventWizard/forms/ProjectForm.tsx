import { CheckOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getDirectionsByEvent } from "../../../api/directions";
import { getProjectsByDirection, saveProjectsForDirection } from "../../../api/projects";
import type { Project } from "../../../../../types/project";
import { useToast } from "../../../../../components/Toast/ToastProvider";
import PageLoader from "../../../../../components/Loading/PageLoader";
import { useWizard } from "../EventWizardModal";
import type { DirectionModel, ProjectModel } from "../types";
import AppButton from "../../../../../components/UI/Button";
import AppInput, { AppTextArea } from "../../../../../components/UI/Input";
import AppSelect from "../../../../../components/UI/Select";

type LocalProject = ProjectModel & { directionId?: string };

function buildProjectSnapshot(
  projects: LocalProject[],
  directionId: string,
  title: string,
  description: string,
  editingProjectId: number | null
) {
  return JSON.stringify({
    directionId,
    projects: projects.map((project) => ({
      title: project.title?.trim() ?? "",
      description: project.description?.trim() ?? "",
      directionId: String(project.directionId ?? ""),
    })),
    title: title.trim(),
    description: description.trim(),
    editingProjectId,
  });
}

export default function ProjectForm() {
  const { mode, eventId, savedDirections, directionId: ctxDirectionId, projectId: ctxProjectId, setHasUnsavedProjects } = useWizard();
  const { showToast } = useToast();

  const [directions, setDirections] = useState<DirectionModel[]>([]);
  const [directionId, setDirectionId] = useState<string>(ctxDirectionId ? String(ctxDirectionId) : "");
  const [projects, setProjects] = useState<LocalProject[]>([]);
  const [editingProjectId, setEditingProjectId] = useState<number | null>(mode === "edit" && ctxProjectId ? Number(ctxProjectId) : null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loadingDirections, setLoadingDirections] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "synced">("idle");
  const [savedSnapshot, setSavedSnapshot] = useState("");

  const markUnsaved = () => {
    setSaveState("idle");
    setHasUnsavedProjects?.(true);
  };

  const formSnapshot = useMemo(
    () => buildProjectSnapshot(projects, directionId, title, description, editingProjectId),
    [description, directionId, editingProjectId, projects, title]
  );

  useEffect(() => {
    if (saveState === "synced" && savedSnapshot && savedSnapshot !== formSnapshot) {
      setSaveState("idle");
    }
  }, [formSnapshot, saveState, savedSnapshot]);

  const resetDraft = () => {
    setEditingProjectId(null);
    setTitle("");
    setDescription("");
    setErrors({});
  };

  const fillForm = useCallback(
    (project?: LocalProject) => {
      if (!project) return;
      setEditingProjectId(Number(project.id));
      setDirectionId(String(project.directionId ?? ctxDirectionId ?? ""));
      setTitle(project.title ?? "");
      setDescription(project.description ?? "");
      setErrors({});
    },
    [ctxDirectionId]
  );

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (savedDirections && savedDirections.length > 0) {
        if (!mounted) return;
        setDirections(savedDirections);
        if (!directionId && savedDirections.length > 0) setDirectionId(String(ctxDirectionId ?? savedDirections[0].id));
        return;
      }

      if (!eventId) return;
      setLoadingDirections(true);
      try {
        const loadedDirections = await getDirectionsByEvent(eventId);
        if (!mounted) return;
        setDirections(loadedDirections || []);
        if (!directionId && loadedDirections && loadedDirections.length > 0) {
          setDirectionId(String(ctxDirectionId ?? loadedDirections[0].id));
        }
      } catch {
        if (mounted) setDirections([]);
      } finally {
        if (mounted) setLoadingDirections(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [ctxDirectionId, directionId, eventId, savedDirections]);

  useEffect(() => {
    let mounted = true;

    (async () => {
      if (!directionId) {
        setProjects([]);
        return;
      }

      const cachedDirection = (savedDirections || []).find((direction) => String(direction.id) === String(directionId));
      if (cachedDirection?.projects?.length) {
        if (!mounted) return;
        const mapped = cachedDirection.projects.map((project) => ({
          ...project,
          directionId: String(directionId),
        }));
        setProjects(mapped);
        if (mode === "edit" && ctxProjectId) {
          fillForm(mapped.find((project) => Number(project.id) === Number(ctxProjectId)));
        }
        return;
      }

      setLoadingProjects(true);
      try {
        const apiProjects = await getProjectsByDirection(Number(directionId));
        if (!mounted) return;
        const mapped = (apiProjects || []).map((project) => ({
          id: Number(project.id),
          title: project.title ?? "",
          description: project.description ?? "",
          directionId: String(directionId),
        }));
        setProjects(mapped);
        if (mode === "edit" && ctxProjectId) {
          fillForm(mapped.find((project) => Number(project.id) === Number(ctxProjectId)));
        }
      } catch {
        if (mounted) setProjects([]);
      } finally {
        if (mounted) setLoadingProjects(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [ctxProjectId, directionId, fillForm, mode, savedDirections]);

  useEffect(() => {
    if (ctxDirectionId) setDirectionId(String(ctxDirectionId));
  }, [ctxDirectionId]);

  const validateDraft = () => {
    const nextErrors: Record<string, string> = {};
    if (!directionId) nextErrors.directionId = "Выберите направление";
    if (!title.trim()) nextErrors.title = "Введите название проекта";
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const buildDraft = (): LocalProject => ({
    id: editingProjectId ?? Date.now(),
    title: title.trim(),
    description: description.trim(),
    directionId,
  });

  const saveDraftToList = () => {
    if (!validateDraft()) return false;
    const nextProject = buildDraft();

    if (editingProjectId != null) {
      setProjects((prev) => prev.map((project) => (Number(project.id) === Number(editingProjectId) ? { ...project, ...nextProject } : project)));
      markUnsaved();
      showToast("success", "Изменения проекта добавлены в черновик");
      return true;
    }

    setProjects((prev) => [...prev, nextProject]);
    resetDraft();
    markUnsaved();
    return true;
  };

  const removeProject = (id: number) => {
    setProjects((prev) => prev.filter((project) => Number(project.id) !== Number(id)));
    if (Number(editingProjectId) === Number(id)) resetDraft();
    markUnsaved();
  };

  const handleSave = async () => {
    if (!directionId) {
      showToast("error", "Выберите направление");
      return;
    }

    let preparedProjects = [...projects];
    if (title.trim()) {
      if (!validateDraft()) return;
      const draft = buildDraft();
      preparedProjects =
        editingProjectId != null
          ? preparedProjects.map((project) => (Number(project.id) === Number(editingProjectId) ? { ...project, ...draft } : project))
          : [...preparedProjects, draft];
    }

    for (const project of preparedProjects) {
      if (!project.title?.trim()) {
        showToast("error", "У одного из проектов нет названия");
        return;
      }
    }

    try {
      const payload: Project[] = preparedProjects.map((project) => ({
        id: Number(project.id),
        title: project.title ?? "",
        description: project.description ?? "",
        directionId: Number(directionId),
      }));
      const saved = await saveProjectsForDirection(Number(directionId), payload);
      const mapped = (saved || []).map((project) => ({
        id: Number(project.id),
        title: project.title ?? "",
        description: project.description ?? "",
        directionId: String(directionId),
      }));
      const activeProject =
        mode === "edit" && ctxProjectId
          ? mapped.find((project) => Number(project.id) === Number(ctxProjectId))
          : undefined;

      setProjects(mapped);
      if (activeProject) {
        fillForm(activeProject);
      } else {
        resetDraft();
      }
      setSavedSnapshot(
        buildProjectSnapshot(
          mapped,
          directionId,
          activeProject?.title ?? "",
          activeProject?.description ?? "",
          activeProject ? Number(activeProject.id) : null
        )
      );
      setSaveState("synced");
      setHasUnsavedProjects?.(false);
      showToast("success", "Проекты сохранены");
    } catch {
      showToast("error", "Ошибка при сохранении проектов");
    }
  };

  return (
    <div className="wizard-form">
      <h2 className="h2">{mode === "edit" ? "Редактирование проекта" : "Добавление проектов"}</h2>

      <div className={`field-wrap ${errors.directionId ? "error" : ""}`}>
        <label className="text-small">
          <span className="wizard-field-label">Выберите направление</span>
          <AppSelect
            tone="projects"
            value={directionId}
            disabled={mode === "edit" && Boolean(ctxDirectionId)}
            onChange={(value) => {
              setDirectionId(String(value));
              markUnsaved();
              setErrors((prev) => {
                const next = { ...prev };
                delete next.directionId;
                return next;
              });
            }}
            options={[
              { value: "", label: "Выберите направление" },
              ...(loadingDirections
                ? [{ value: "__loading", label: "Загрузка...", disabled: true }]
                : directions.map((direction) => ({
                    value: String(direction.id),
                    label: direction.title,
                  }))),
            ]}
          />
        </label>
        {errors.directionId && <div className="field-error">{errors.directionId}</div>}
      </div>

      <div className={`field-wrap ${errors.title ? "error" : ""}`}>
        <label className="text-small">
          <span className="wizard-field-label">Название проекта</span>
          <div className="wizard-inline-add-row wizard-inline-add-row--entity">
            <AppInput
              placeholder="Введите название проекта"
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                markUnsaved();
                setErrors((prev) => {
                  const next = { ...prev };
                  delete next.title;
                  return next;
                });
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  saveDraftToList();
                }
              }}
            />
            <AppButton className="primary wizard-inline-add-button wizard-inline-add-button--secondary" type="button" onClick={saveDraftToList}>
              {editingProjectId != null ? "Обновить" : "Добавить"}
            </AppButton>
          </div>
        </label>
        {errors.title && <div className="field-error">{errors.title}</div>}
      </div>

      <label className="text-small">
        <span className="wizard-field-label">Описание</span>
        <AppTextArea
          value={description}
          onChange={(event) => {
            setDescription(event.target.value);
            markUnsaved();
          }}
          placeholder="Краткое описание проекта"
        />
      </label>

      <div className="tags" style={{ marginTop: 12 }}>
        {loadingProjects ? (
          <PageLoader className="page-loader--compact" />
        ) : (
          projects.map((project) => (
            <div
              key={project.id}
              className="tag"
              style={Number(editingProjectId) === Number(project.id) ? { outline: "2px solid var(--wizard-accent)" } : undefined}
            >
              <AppButton
                className="tag-edit"
                type="button"
                onClick={() => fillForm(project)}
              >
                <strong className="tag-title">{project.title}</strong>
                {project.description && <span className="tag-description">{project.description}</span>}
              </AppButton>
              <AppButton className="tag-remove" type="button" onClick={() => removeProject(Number(project.id))} aria-label="Удалить проект">
                x
              </AppButton>
            </div>
          ))
        )}
      </div>

      <div className="wizard-actions">
        <AppButton className="primary" type="button" onClick={handleSave} disabled={saveState === "synced"}>
          {saveState === "synced" && <CheckOutlined />}
          {saveState === "synced"
            ? "Изменения сохранены"
            : mode === "edit" || projects.length > 0
              ? "Сохранить изменения"
              : "Сохранить настройки проекта"}
        </AppButton>
      </div>
    </div>
  );
}


