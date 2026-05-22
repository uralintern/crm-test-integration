import { createContext, useEffect, useRef, useState, type ReactNode } from "react";
import client from "../api/client";
import baseUsers from "../mock-data/users.json";
import { CURRENT_MOCK_SEED_VERSION, LS_MOCK_SEED_VERSION } from "../storage/mockSeed";

interface User {
  id: number;
  email: string;
  name: string;
  surname: string;
  role: string;
  vk?: string;
  vkConfirmed?: boolean;
  vkBotUrl?: string;
  isSuperuser?: boolean;
  isStaff?: boolean;
  password?: string;
}

type AuthActionResult = {
  ok: boolean;
  error?: string;
};

type BackendUserRecord = Record<string, unknown>;
type MockUser = User & { password?: string; confirm?: string };
type ProfileUpdate = Partial<User> &
  Record<string, unknown> & {
    first_name?: string;
    last_name?: string;
    patronymic?: string;
    telegram?: string;
    course?: string;
    university?: string;
    vk?: string;
    job?: string;
  };

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<boolean>;
  register: (u: Omit<User, "id"> & { confirm?: string }) => Promise<AuthActionResult>;
  logout: () => Promise<void>;
  updateProfile: (u: ProfileUpdate) => Promise<void>;
  refreshUser: () => Promise<User | null>;
}

export const AuthContext = createContext<AuthContextType>({} as AuthContextType);

const USE_MOCK = client.USE_MOCK;
const LS_USERS = "users";
const LS_CURRENT_USER = "currentUser";

function mapBackendUser(data: unknown): User | null {
  if (!data || typeof data !== "object") return null;
  const obj = data as BackendUserRecord;
  const profile = (obj.profile && typeof obj.profile === "object" ? obj.profile : {}) as BackendUserRecord;

  const idRaw = obj.id ?? obj.pk ?? null;
  const id =
    typeof idRaw === "number"
      ? idRaw
      : typeof idRaw === "string" && !Number.isNaN(Number(idRaw))
        ? Number(idRaw)
        : null;
  const email = String(obj.email ?? profile.email ?? "");
  const name = String(obj.firstName ?? obj.first_name ?? obj.name ?? profile.name ?? "");
  const surname = String(obj.lastName ?? obj.last_name ?? obj.surname ?? profile.surname ?? "");
  const vk = String(obj.vk ?? profile.vk ?? "");
  const vkConfirmed = Boolean(obj.vkConfirmed ?? obj.vk_confirmed ?? profile.vkConfirmed ?? profile.vk_confirmed);
  const vkBotUrl = String(obj.vkBotUrl ?? obj.vk_bot_url ?? profile.vkBotUrl ?? profile.vk_bot_url ?? "");
  const isSuperuser = Boolean(obj.isSuperuser ?? obj.is_superuser);
  const isStaff = Boolean(obj.isStaff ?? obj.is_staff);
  let role = "guest";
  if (typeof obj.role === "string") {
    role = obj.role;
  } else if (profile.crm_role) {
    const crm = String(profile.crm_role).toLowerCase();
    if (crm.includes("project") || crm.includes("projectant")) role = "student";
    else if (crm.includes("curator") || crm.includes("admin")) role = "organizer";
  } else if (obj.crm_role) {
    const crm = String(obj.crm_role).toLowerCase();
    if (crm.includes("project") || crm.includes("projectant")) role = "student";
    else if (crm.includes("curator") || crm.includes("admin")) role = "organizer";
  } else {
    role = obj.is_staff ? "organizer" : "student";
  }

  if (id == null) return null;

  return {
    id,
    email,
    name,
    surname,
    role,
    vk,
    vkConfirmed,
    vkBotUrl,
    isSuperuser,
    isStaff,
  };
}

function ensureMockAuthSeeded() {
  const storedVersion = localStorage.getItem(LS_MOCK_SEED_VERSION);
  if (storedVersion !== CURRENT_MOCK_SEED_VERSION) {
    localStorage.setItem(LS_USERS, "[]");
    localStorage.removeItem(LS_CURRENT_USER);
  }
}

function readStoredMockUsers() {
  return JSON.parse(localStorage.getItem(LS_USERS) || "[]") as MockUser[];
}

function translateBackendMessage(message: string): string {
  const normalized = message.trim();

  if (!normalized) return message;

  if (normalized === "Passwords do not match.") {
    return "Пароли не совпадают.";
  }

  if (normalized === "Invalid credentials.") {
    return "Неверный email или пароль.";
  }

  if (normalized === "This password is too common.") {
    return "Этот пароль слишком простой.";
  }

  if (normalized === "This password is entirely numeric.") {
    return "Пароль не должен состоять только из цифр.";
  }

  const tooShortMatch = normalized.match(
    /^This password is too short\. It must contain at least (\d+) characters\.$/i
  );
  if (tooShortMatch) {
    return `Пароль слишком короткий. Он должен содержать не менее ${tooShortMatch[1]} символов.`;
  }

  const tooSimilarMatch = normalized.match(/^The password is too similar to the (.+)\.$/i);
  if (tooSimilarMatch) {
    return `Пароль слишком похож на поле "${tooSimilarMatch[1]}".`;
  }

  return message;
}

function extractErrorMessage(error: unknown): string | undefined {
  if (!error) return undefined;
  if (typeof error === "string") return translateBackendMessage(error);

  if (Array.isArray(error)) {
    const firstText = error.find((item) => typeof item === "string" && item.trim());
    return typeof firstText === "string" ? translateBackendMessage(firstText) : undefined;
  }

  if (typeof error !== "object") return undefined;

  const record = error as Record<string, unknown>;
  const preferredKeys = [
    "detail",
    "message",
    "password",
    "passwordConfirmation",
    "password_confirmation",
    "email",
    "nonFieldErrors",
    "non_field_errors",
  ];

  for (const key of preferredKeys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return translateBackendMessage(value);
    if (Array.isArray(value)) {
      const firstText = value.find((item) => typeof item === "string" && item.trim());
      if (typeof firstText === "string") return translateBackendMessage(firstText);
    }
  }

  for (const value of Object.values(record)) {
    if (typeof value === "string" && value.trim()) return translateBackendMessage(value);
    if (Array.isArray(value)) {
      const firstText = value.find((item) => typeof item === "string" && item.trim());
      if (typeof firstText === "string") return translateBackendMessage(firstText);
    }
  }

  return undefined;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const didBootstrapBackendRef = useRef(false);
  const [user, setUser] = useState<User | null>(() => {
    if (USE_MOCK) {
      ensureMockAuthSeeded();
      const saved = localStorage.getItem(LS_CURRENT_USER);
      if (!saved) return null;
      try {
        const parsed = JSON.parse(saved) as MockUser;
        const allUsers = [...(baseUsers as MockUser[]), ...readStoredMockUsers()];
        return (
          allUsers.find(
            (item) =>
              Number(item.id) === Number(parsed.id) &&
              String(item.email).trim().toLowerCase() === String(parsed.email).trim().toLowerCase()
          ) || null
        );
      } catch {
        localStorage.removeItem(LS_CURRENT_USER);
        return null;
      }
    }

    const saved = localStorage.getItem(LS_CURRENT_USER);
    return saved ? JSON.parse(saved) : null;
  });

  useEffect(() => {
    if (USE_MOCK) return;
    if (didBootstrapBackendRef.current) return;
    didBootstrapBackendRef.current = true;
    if (!localStorage.getItem(LS_CURRENT_USER)) {
      setUser(null);
      return;
    }
    (async () => {
      try {
        const info = await client.get("/api/users/user-info/");
        const mapped = mapBackendUser(info);
        setUser(mapped);
        if (mapped) localStorage.setItem(LS_CURRENT_USER, JSON.stringify(mapped));
        else localStorage.removeItem(LS_CURRENT_USER);
      } catch {
        try {
          const ok = await client.doRefresh();
          if (ok) {
            const info = await client.get("/api/users/user-info/");
            const mapped = mapBackendUser(info);
            setUser(mapped);
            if (mapped) localStorage.setItem(LS_CURRENT_USER, JSON.stringify(mapped));
            else localStorage.removeItem(LS_CURRENT_USER);
          } else {
            setUser(null);
            localStorage.removeItem(LS_CURRENT_USER);
          }
        } catch {
          setUser(null);
          localStorage.removeItem(LS_CURRENT_USER);
        }
      }
    })();
  }, []);

  const getAllUsersMock = () => {
    ensureMockAuthSeeded();
    const stored = readStoredMockUsers();
    return [...(baseUsers as MockUser[]), ...stored];
  };

  const loginMock = async (email: string, password: string) => {
    const users = getAllUsersMock();
    const normalizedEmail = email.trim().toLowerCase();
    const found = users.find((u) => String(u.email).trim().toLowerCase() === normalizedEmail && u.password === password);
    if (!found) return false;
    setUser(found);
    localStorage.setItem(LS_CURRENT_USER, JSON.stringify(found));
    return true;
  };

  const registerMock = async (u: Omit<User, "id"> & { confirm?: string }): Promise<AuthActionResult> => {
    ensureMockAuthSeeded();
    const normalizedEmail = u.email.trim().toLowerCase();
    const newUser: MockUser = { ...u, email: normalizedEmail, id: Date.now() };
    const stored = readStoredMockUsers();
    stored.push(newUser);
    localStorage.setItem(LS_USERS, JSON.stringify(stored));
    localStorage.setItem(LS_CURRENT_USER, JSON.stringify(newUser));
    setUser(newUser);
    return { ok: true };
  };

  const updateProfileMock = async (u: ProfileUpdate) => {
    if (!user) return;
    ensureMockAuthSeeded();
    const updated: MockUser = { ...user, ...u };
    setUser(updated);
    localStorage.setItem(LS_CURRENT_USER, JSON.stringify(updated));
    const stored = readStoredMockUsers();
    const idx = stored.findIndex((s) => s.id === updated.id);
    if (idx >= 0) stored[idx] = updated;
    else stored.push(updated);
    localStorage.setItem(LS_USERS, JSON.stringify(stored));
  };

  const logoutMock = async () => {
    setUser(null);
    localStorage.removeItem(LS_CURRENT_USER);
  };

  const refreshUserMock = async () => user;

  const loginBackend = async (email: string, password: string) => {
    try {
      const info = await client.login(email.trim().toLowerCase(), password);
      const mapped = mapBackendUser(info);
      setUser(mapped);
      if (mapped) localStorage.setItem(LS_CURRENT_USER, JSON.stringify(mapped));
      else localStorage.removeItem(LS_CURRENT_USER);
      return true;
    } catch {
      return false;
    }
  };

  const refreshUserBackend = async () => {
    try {
      const info = await client.get("/api/users/user-info/");
      const mapped = mapBackendUser(info);
      setUser(mapped);
      if (mapped) localStorage.setItem(LS_CURRENT_USER, JSON.stringify(mapped));
      else localStorage.removeItem(LS_CURRENT_USER);
      return mapped;
    } catch {
      return user;
    }
  };

  const registerBackend = async (u: Omit<User, "id"> & { confirm?: string }): Promise<AuthActionResult> => {
    try {
      const payload = {
        email: u.email.trim().toLowerCase(),
        vk: String(u.vk || ""),
        first_name: u.name || "",
        last_name: u.surname || "",
        password: u.password || "",
        password_confirmation: u.confirm || u.password || "",
      };
      await client.post("/api/users/register/", payload);
      const loggedIn = await loginBackend(payload.email, payload.password);
      return loggedIn ? { ok: true } : { ok: false, error: "Регистрация прошла, но не удалось автоматически войти в аккаунт." };
    } catch (error) {
      return {
        ok: false,
        error: extractErrorMessage(error) || "Не удалось зарегистрироваться",
      };
    }
  };

  const updateProfileBackend = async (u: ProfileUpdate) => {
    try {
      const allowed: Array<keyof ProfileUpdate> = [
        "surname",
        "name",
        "patronymic",
        "telegram",
        "email",
        "course",
        "university",
        "vk",
        "job",
        "workplace",
        "specialty",
        "about",
      ];
      const payload: Record<string, unknown> = {};
      allowed.forEach((k) => {
        const value = u[k];
        if (typeof value !== "undefined") payload[String(k)] = value;
      });

      if (typeof u.first_name !== "undefined") payload["name"] = u.first_name;
      if (typeof u.last_name !== "undefined") payload["surname"] = u.last_name;

      await client.put("/api/users/profile/", payload);
      try {
        const info = await client.get("/api/users/user-info/");
        const mapped = mapBackendUser(info);
        setUser(mapped);
        if (mapped) localStorage.setItem(LS_CURRENT_USER, JSON.stringify(mapped));
        else localStorage.removeItem(LS_CURRENT_USER);
      } catch {
        const partial = { ...user, ...(payload.name ? { name: payload.name } : {}), ...(payload.surname ? { surname: payload.surname } : {}) };
        setUser(partial as User);
        if (partial) localStorage.setItem(LS_CURRENT_USER, JSON.stringify(partial));
      }
    } catch {
    }
  };

  const logoutBackend = async () => {
    try {
      await client.logout();
    } catch {
    } finally {
      setUser(null);
      localStorage.removeItem(LS_CURRENT_USER);
    }
  };

  const value: AuthContextType = USE_MOCK
    ? {
        user,
        login: loginMock,
        register: registerMock,
        logout: logoutMock,
        updateProfile: updateProfileMock,
        refreshUser: refreshUserMock,
      }
    : {
        user,
        login: loginBackend,
        register: registerBackend,
        logout: logoutBackend,
        updateProfile: updateProfileBackend,
        refreshUser: refreshUserBackend,
      };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}



