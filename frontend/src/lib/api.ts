const BASE = (import.meta as any).env?.VITE_API_URL ?? "";
const KEY = "parpte.token";

export const token = {
  get: () => localStorageSafe.get(KEY),
  set: (t: string | null) => (t ? localStorageSafe.set(KEY, t) : localStorageSafe.remove(KEY)),
};

const localStorageSafe = {
  get(k: string) {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set(k: string, v: string) {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* storage unavailable */
    }
  },
  remove(k: string) {
    try {
      localStorage.removeItem(k);
    } catch {
      /* storage unavailable */
    }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = token.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the ParPTE server. Check that the backend is running.");
  }
  if (res.status === 401 && t) {
    token.set(null);
    window.dispatchEvent(new Event("parpte:logout"));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : j.detail?.[0]?.msg ?? msg;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) => request<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(p: string, body: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
  /** Multipart upload of a response (and optional recording) for scoring. */
  submit: <T>(p: string, response: unknown, audio?: Blob | null) => {
    const fd = new FormData();
    fd.append("response", JSON.stringify(response ?? {}));
    if (audio) fd.append("audio", audio, "answer.webm");
    return request<T>(p, { method: "POST", body: fd });
  },
};
