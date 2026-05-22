import { useContext, useEffect, useMemo, useState } from "react";
import client from "../../api/client";
import { useToast } from "../../components/Toast/ToastProvider";
import { AuthContext } from "../../context/AuthContext";
import "../../styles/profile.scss";
import AppButton from "../../components/UI/Button";
import AppInput, { AppTextArea } from "../../components/UI/Input";
import AppSelect from "../../components/UI/Select";
import { SPECIALIZATION_OPTIONS } from "../../constants/specializations";

const DEFAULT_NAME = "Имя";
const DEFAULT_SURNAME = "Фамилия";
const SPECIALIZATION_SEPARATOR = ", ";

type ProfileResponse = {
  name?: string;
  surname?: string;
  university?: string;
  course?: string | number;
  specialty?: string;
  job?: string;
  workplace?: string;
  about?: string;
  telegram?: string;
  vk?: string;
  email?: string;
};

type ProfileUpdatePayload = Record<string, string | undefined>;

const AVATAR_COLORS = [
  "#f44336",
  "#e91e63",
  "#9c27b0",
  "#673ab7",
  "#3f51b5",
  "#2196f3",
  "#03a9f4",
  "#00bcd4",
  "#009688",
  "#4caf50",
  "#8bc34a",
  "#cddc39",
  "#ffeb3b",
  "#ffc107",
  "#ff9800",
  "#ff5722",
  "#795548",
  "#607d8b",
];

function splitSpecialties(value?: string) {
  return String(value || "")
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeCourse(value: string) {
  const digits = value.replace(/\D/g, "");
  if (!digits) return "";

  const number = Math.min(6, Math.max(1, Number(digits)));
  return String(number);
}

export default function ProfilePage() {
  const { user, updateProfile } = useContext(AuthContext);
  const [editing, setEditing] = useState(false);
  const { showToast } = useToast();

  const [profile, setProfile] = useState({
    name: DEFAULT_NAME,
    surname: DEFAULT_SURNAME,
    university: "",
    course: "",
    specialties: [] as string[],
    workplace: "",
    about: "",
    telegram: "",
    vk: "",
    email: "example@mail.ru",
  });
  const [selectedSpecializationId, setSelectedSpecializationId] = useState("");

  useEffect(() => {
    let mounted = true;

    const fillFromProfile = (data: ProfileResponse, fallbackUser = user) => {
      const userRecord = (fallbackUser ?? {}) as Record<string, unknown>;
      const specialtyValue = String(data.specialty ?? userRecord.specialty ?? "");

      setProfile({
        name: data.name || fallbackUser?.name || DEFAULT_NAME,
        surname: data.surname || fallbackUser?.surname || DEFAULT_SURNAME,
        university: String(data.university ?? userRecord.university ?? ""),
        course: data.course != null ? normalizeCourse(String(data.course)) : normalizeCourse(String(userRecord.course ?? "")),
        specialties: splitSpecialties(specialtyValue),
        workplace: String(data.workplace ?? data.job ?? userRecord.workplace ?? userRecord.job ?? ""),
        about: String(data.about ?? userRecord.about ?? ""),
        telegram: String(data.telegram ?? userRecord.telegram ?? ""),
        vk: String(data.vk ?? userRecord.vk ?? ""),
        email: data.email || fallbackUser?.email || "",
      });
      setSelectedSpecializationId("");
    };

    (async () => {
      if (!user) {
        setProfile((prev) => ({ ...prev, email: "example@mail.ru" }));
        return;
      }

      if (client.USE_MOCK) {
        fillFromProfile({}, user);
        return;
      }

      try {
        const data = await client.get<ProfileResponse>("/api/users/profile/");
        if (!mounted) return;
        fillFromProfile(data, user);
      } catch {
        if (!mounted) return;
        fillFromProfile({}, user);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [user]);

  const update = (key: keyof typeof profile, value: string | string[]) => setProfile((prev) => ({ ...prev, [key]: value }));

  const addSpecialization = () => {
    const selected = SPECIALIZATION_OPTIONS.find((item) => String(item.id) === String(selectedSpecializationId));
    if (!selected) return;

    setProfile((prev) => {
      if (prev.specialties.some((item) => item === selected.title)) return prev;
      return { ...prev, specialties: [...prev.specialties, selected.title] };
    });
    setSelectedSpecializationId("");
  };

  const removeSpecialization = (title: string) => {
    setProfile((prev) => ({ ...prev, specialties: prev.specialties.filter((item) => item !== title) }));
  };

  const onSave = async () => {
    if (!user) return;

    try {
      const payload: ProfileUpdatePayload = {
        name: profile.name,
        surname: profile.surname,
        telegram: profile.telegram || undefined,
        email: profile.email || undefined,
        course: profile.course || undefined,
        university: profile.university || undefined,
        vk: profile.vk || undefined,
        specialty: profile.specialties.join(SPECIALIZATION_SEPARATOR) || undefined,
        about: profile.about || undefined,
        workplace: profile.workplace || undefined,
        job: profile.workplace || undefined,
      };

      Object.keys(payload).forEach((key) => {
        const value = payload[key];
        if (typeof value === "undefined" || value === "") delete payload[key];
      });

      await updateProfile(payload);
      setEditing(false);
      showToast("success", "Профиль сохранён");
    } catch {
      showToast("error", "Ошибка при сохранении профиля");
    }
  };

  const initials = useMemo(() => {
    const surname = profile.surname.trim();
    const name = profile.name.trim();
    return `${surname[0] || ""}${name[0] || ""}`.toUpperCase() || "-";
  }, [profile.name, profile.surname]);

  const avatarBg = useMemo(() => {
    const source = String(user?.id ?? profile.email ?? profile.name ?? "default");
    let hash = 0;
    for (let i = 0; i < source.length; i += 1) hash = (hash * 31 + source.charCodeAt(i)) | 0;
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
  }, [profile, user]);

  return (
    <div className="page profile-page">
      <h1 className="page-title h1">Личный кабинет</h1>

      <div className="profile-container">
        <div className="profile-block">
          <h4 className="h4">Личная информация</h4>

          <div className="avatar-wrap">
            <div className="avatar" style={{ background: avatarBg }}>
              {initials}
            </div>
          </div>

          <div className="inputs">
            <AppInput className="text-regular" disabled={!editing} value={profile.name} onChange={(event) => update("name", event.target.value)} />
            <AppInput className="text-regular" disabled={!editing} value={profile.surname} onChange={(event) => update("surname", event.target.value)} />
            <AppInput
              className="text-regular"
              disabled={!editing}
              value={profile.university}
              onChange={(event) => update("university", event.target.value)}
              placeholder="Учебное заведение"
            />
            <AppInput
              className="text-regular"
              disabled={!editing}
              type="number"
              min={1}
              max={6}
              inputMode="numeric"
              value={profile.course}
              onChange={(event) => update("course", normalizeCourse(event.target.value))}
              placeholder="Курс"
            />

            <div className="profile-specializations">
              <div className="profile-specializations__add-row">
                <AppSelect
                  value={selectedSpecializationId}
                  disabled={!editing}
                  placeholder="Выберите специализацию"
                  onChange={(value) => setSelectedSpecializationId(String(value))}
                  options={[
                    { value: "", label: "Выберите специализацию" },
                    ...SPECIALIZATION_OPTIONS.map((specialization) => ({
                      value: String(specialization.id),
                      label: specialization.title,
                    })),
                  ]}
                />
                <AppButton
                  className="primary profile-specializations__add-button"
                  type="button"
                  onClick={addSpecialization}
                  disabled={!editing || !selectedSpecializationId}
                >
                  Добавить
                </AppButton>
              </div>
              <div className="profile-specializations__selected">
                {profile.specialties.length === 0 ? (
                  <span className="profile-specializations__empty">Специализации не выбраны</span>
                ) : (
                  profile.specialties.map((specialty) => (
                    <div key={specialty} className="profile-specialization-tag">
                      <span>{specialty}</span>
                      {editing && (
                        <AppButton
                          className="profile-specialization-tag__remove"
                          type="button"
                          onClick={() => removeSpecialization(specialty)}
                          aria-label="Удалить специализацию"
                        >
                          x
                        </AppButton>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            <AppTextArea className="text-regular" disabled={!editing} value={profile.about} onChange={(event) => update("about", event.target.value)} placeholder="О себе" />
          </div>
        </div>

        <div className="profile-block">
          <h4 className="h4">Контакты</h4>

          <div className="inputs">
            <AppInput className="text-regular" disabled={!editing} value={profile.telegram} onChange={(event) => update("telegram", event.target.value)} placeholder="Telegram" />
            <AppInput className="text-regular" disabled={!editing} value={profile.vk} onChange={(event) => update("vk", event.target.value)} placeholder="ВКонтакте" />
            <AppInput className="text-regular" disabled value={profile.email} />
          </div>
        </div>
      </div>

      <AppButton
        className="edit-btn h3"
        onClick={() => {
          if (editing) void onSave();
          else setEditing(true);
        }}
      >
        {editing ? "Сохранить изменения" : "Редактировать"}
      </AppButton>
    </div>
  );
}
