interface InternshipApiImportMetaEnv {
    VITE_INTERNSHIP_API_BASE?: string;
}

const API_BASE =
    ((import.meta as ImportMeta & { env?: InternshipApiImportMetaEnv }).env?.VITE_INTERNSHIP_API_BASE || "").trim() ||
    "/parser";

export interface InternshipListItem {
    id: string;
    title: string;
    direction: string;
    company: string;
    city: string | null;
    work_format: string | null;
    link: string;
    salary_from: number | null;
    description: string | null;
}

export interface PaginationMeta {
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface InternshipsListResponse {
    data: InternshipListItem[];
    pagination: PaginationMeta;
}

export type InternshipDetail = InternshipListItem;

// Коды формата работы
export const WORK_FORMAT_OPTIONS = [
    { code: "office", label: "Офис" },
    { code: "hybrid", label: "Гибрид" },
    { code: "remote", label: "Удалённая работа" },
] as const;

export type WorkFormatCode = (typeof WORK_FORMAT_OPTIONS)[number]["code"];

export interface GetInternshipsParams {
    page?: number;
    city?: string[];
    format?: WorkFormatCode[];
    //employment принимается бэкендом, но пока не применяется к фильтрации, на будущее
    employment?: string[];
}

function buildQuery(params: GetInternshipsParams): string {
    const search = new URLSearchParams();
    if (params.page) search.set("page", String(params.page));
    (params.city || []).forEach((c) => search.append("city", c));
    (params.format || []).forEach((f) => search.append("format", f));
    (params.employment || []).forEach((e) => search.append("employment", e));
    const qs = search.toString();
    return qs ? `?${qs}` : "";
}

async function handleResponse<T>(res: Response): Promise<T> {
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body?.detail || detail;
        } catch {

        }
        throw new Error(detail || `Request failed with status ${res.status}`);
    }
    return res.json() as Promise<T>;
}

export async function getInternships(params: GetInternshipsParams = {}): Promise<InternshipsListResponse> {
    const res = await fetch(`${API_BASE}/api/internship${buildQuery(params)}`, {
        method: "GET",
        headers: { Accept: "application/json" },
    });
    return handleResponse<InternshipsListResponse>(res);
}

export async function getInternshipById(id: string): Promise<InternshipDetail> {
    const res = await fetch(`${API_BASE}/api/internship/${id}`, {
        method: "GET",
        headers: { Accept: "application/json" },
    });
    return handleResponse<InternshipDetail>(res);
}