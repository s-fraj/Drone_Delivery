const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const TOKEN_KEY = 'drovery_token';
const USER_KEY = 'drovery_user';

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } catch {
      /* storage unavailable */
    }
  },
};

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Fired when a request comes back 401 so the auth layer can drop the session
// and redirect, without api.ts depending on React or the router.
export const AUTH_EXPIRED_EVENT = 'drovery:auth-expired';

interface FastApiValidationItem {
  msg?: string;
}

/** FastAPI `detail` is a string, or a list of {loc,msg,type} for 422s. */
function extractMessage(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return (detail as FastApiValidationItem[])
        .map((d) => d.msg ?? JSON.stringify(d))
        .join('; ');
    }
  }
  return 'Request failed';
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(API_BASE + path, { ...init, headers });
  if (res.status === 401 && token) {
    tokenStore.clear();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => ({}));
    throw new ApiError(extractMessage(body), res.status);
  }
  return res;
}

async function json<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await request(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => json<T>(path, 'GET'),
  post: <T>(path: string, body?: unknown) => json<T>(path, 'POST', body),
  put: <T>(path: string, body?: unknown) => json<T>(path, 'PUT', body),
  delete: <T = void>(path: string) => json<T>(path, 'DELETE'),

  /** OAuth2 password flow expects a urlencoded form, not JSON. */
  async login(email: string, password: string): Promise<string> {
    const res = await request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    });
    const data = (await res.json()) as { access_token: string };
    return data.access_token;
  },

  /** Download an authenticated file (e.g. the admin CSV export). */
  async download(path: string, filename: string): Promise<void> {
    const res = await request(path);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};
