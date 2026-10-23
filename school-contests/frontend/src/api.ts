// Клиент API: JSON-запросы с cookie и CSRF-заголовком.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getCookie(name: string): string {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

type Options = { method?: string; body?: unknown; form?: FormData };

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.body || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = getCookie("csrf_token");
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch("/api" + path, { method, headers, body, credentials: "same-origin" });
  if (!res.ok) {
    let message = "Ошибка запроса";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) {
        // Ошибки валидации FastAPI: берём первое сообщение
        message = String(data.detail[0]?.msg ?? message).replace(/^Value error, /, "");
      }
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

// ---------- Типы ----------

export interface User {
  id: number;
  email: string;
  role: "student" | "admin";
  last_name: string;
  first_name: string;
  middle_name: string | null;
  full_name: string;
  grade: number | null;
  class_letter: string | null;
  class_name: string;
  school: string | null;
  has_photo: boolean;
  email_verified: boolean;
  is_active: boolean;
}

export interface EventItem {
  id: number;
  title: string;
  description: string;
  rules: string;
  subject: string;
  level: string;
  level_label: string;
  participation_type: "individual" | "team";
  team_min_size: number | null;
  team_max_size: number | null;
  start_date: string;
  end_date: string;
  status: "draft" | "published" | "finished";
  phase: "upcoming" | "ongoing" | "finished";
  can_register: boolean;
  registered: boolean;
  my_status: string | null;
  participants: number | null;
  team?: TeamInfo | null;
}

export interface TeamInfo {
  id: number;
  name: string;
  join_code: string;
  is_captain: boolean;
  members: { id: number; name: string; class: string; captain: boolean }[];
}

export const STATUS_LABEL: Record<string, string> = {
  registered: "Записан",
  participated: "Участник",
  prizewinner: "Призёр",
  winner: "Победитель",
};

export const PHASE_LABEL: Record<string, string> = {
  upcoming: "Скоро",
  ongoing: "Идёт сейчас",
  finished: "Завершён",
};

export const EVENT_STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  published: "Опубликовано",
  finished: "Завершено",
};

export const LEVELS: [string, string][] = [
  ["school", "Школьный"],
  ["municipal", "Муниципальный"],
  ["regional", "Региональный"],
  ["federal", "Всероссийский"],
  ["international", "Международный"],
];

export function fmtDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

export function fmtRange(a: string, b: string): string {
  return a === b ? fmtDate(a) : `${fmtDate(a)} — ${fmtDate(b)}`;
}
