interface AppImportMetaEnv {
  VITE_API_BASE?: string;
  VITE_USE_MOCK?: string;
}

type UnknownRecord = Record<string, unknown>;
type RequestBody = unknown;
const LS_CURRENT_USER = "currentUser";

const ENV = (import.meta as ImportMeta & { env?: AppImportMetaEnv }).env ?? {};
const API_BASE = ENV.VITE_API_BASE || "";
const USE_MOCK = ENV.VITE_USE_MOCK === "true";

function getCookie(name: string) {
  const match = document.cookie.split("; ").find((s) => s.trim().startsWith(name + "="));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

function toCamel(s: string) {
  return s.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase());
}

function transformSpecial(obj: unknown): unknown {
  if (!obj || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(transformSpecial);

  const source = obj as UnknownRecord;
  const res: UnknownRecord = {};
  for (const k of Object.keys(source)) {
    const nk = toCamel(k);
    res[nk] = transformSpecial(source[k]);
  }

  if (
    typeof res.name !== "undefined" &&
    ("startDate" in res || "stage" in res || "endDate" in res || "eventId" in res || "directionId" in res)
  ) {
    res.title = res.name;
    delete res.name;
  }
  if (typeof res.name !== "undefined" && !("startDate" in res) && !("questionCount" in res)) {
    res.title = res.name;
    delete res.name;
  }
  if (typeof res.endAppDate !== "undefined" && !("applyDeadline" in res)) {
    res.applyDeadline = res.endAppDate;
    delete res.endAppDate;
  }
  if (typeof res.event === "number" || typeof res.event === "string") {
    res.eventId = Number(res.event);
    delete res.event;
  }
  if (typeof res.direction === "number" || typeof res.direction === "string") {
    res.directionId = Number(res.direction);
    delete res.direction;
  }
  if (typeof res.project === "number" || typeof res.project === "string") {
    res.projectId = Number(res.project);
  }
  if (typeof res.leader === "number" || typeof res.leader === "string") {
    res.organizer = Number(res.leader);
    delete res.leader;
  }
  if (typeof res.curator === "number" || typeof res.curator === "string") {
    res.curator = Number(res.curator);
  }
  if (typeof res.message !== "undefined" && !("about" in res)) {
    res.about = res.message;
    delete res.message;
  }
  if (typeof res.dateSub !== "undefined" && !("createdAt" in res)) {
    res.createdAt = res.dateSub;
    delete res.dateSub;
  }
  if (typeof res.user === "number" || typeof res.user === "string") {
    res.ownerId = Number(res.user);
  }
  if (typeof res.status === "object" && res.status !== null && !Array.isArray(res.status)) {
    const statusObj = res.status as UnknownRecord;
    res.status = statusObj.name ?? res.status;
  }
  return res;
}

async function parseResponse(res: Response): Promise<unknown> {
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
  return transformSpecial(data);
}

let refreshingPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  if (!localStorage.getItem(LS_CURRENT_USER)) return false;
  if (refreshingPromise) return refreshingPromise;
  refreshingPromise = (async () => {
    try {
      const r = await fetch(API_BASE + "/api/users/refresh/", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      refreshingPromise = null;
      return r.ok;
    } catch {
      refreshingPromise = null;
      return false;
    }
  })();
  return refreshingPromise;
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: RequestBody };

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  if (USE_MOCK) throw new Error("client.request: called in mock mode (switch to backend in AuthContext).");

  const url = API_BASE + path;
  const headers = new Headers(options.headers ?? {});
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const init: RequestOptions = {
    credentials: "include",
    headers,
    ...options,
  };

  const method = (init.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = getCookie("csrftoken");
    if (csrf) {
      const csrfHeaders = new Headers(init.headers ?? {});
      csrfHeaders.set("X-CSRFToken", csrf);
      init.headers = csrfHeaders;
    }
  }

  if (typeof init.body !== "undefined") {
    const body = init.body;
    const isBodyInit =
      typeof body === "string" ||
      body instanceof Blob ||
      body instanceof FormData ||
      body instanceof URLSearchParams ||
      body instanceof ArrayBuffer ||
      ArrayBuffer.isView(body);

    if (!isBodyInit) {
      init.body = JSON.stringify(body);
    }
  }

  let res = await fetch(url, init as RequestInit);

  if (res.status === 401 && localStorage.getItem(LS_CURRENT_USER)) {
    const ok = await doRefresh();
    if (ok) {
      if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        const csrf = getCookie("csrftoken");
        if (csrf) {
          const csrfHeaders = new Headers(init.headers ?? {});
          csrfHeaders.set("X-CSRFToken", csrf);
          init.headers = csrfHeaders;
        }
      }
      res = await fetch(url, init as RequestInit);
    }
  }

  const data = await parseResponse(res);
  if (!res.ok) {
    const err = data || { message: res.statusText || "Request failed" };
    throw err;
  }
  return data as T;
}

async function get<T = unknown>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

async function post<T = unknown>(path: string, body?: RequestBody): Promise<T> {
  return request<T>(path, { method: "POST", body });
}

async function put<T = unknown>(path: string, body?: RequestBody): Promise<T> {
  return request<T>(path, { method: "PUT", body });
}

async function patch<T = unknown>(path: string, body?: RequestBody): Promise<T> {
  return request<T>(path, { method: "PATCH", body });
}

async function del<T = unknown>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

async function login(email: string, password: string) {
  if (USE_MOCK) throw new Error("client.login: mock mode");
  await post("/api/users/login/", { email, password });
  const info = await get("/api/users/user-info/");
  return info;
}

async function logout() {
  if (USE_MOCK) throw new Error("client.logout: mock mode");
  await post("/api/users/logout/");
  return true;
}

export default {
  API_BASE,
  USE_MOCK,
  request,
  get,
  post,
  put,
  patch,
  del,
  login,
  logout,
  doRefresh,
};



