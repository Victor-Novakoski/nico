const GENERIC_ERROR = "Algo deu errado. Tente de novo.";

export type User = { username: string; person_id: string };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message = "Sessão expirada. Entre de novo.") {
    super(401, message);
    this.name = "UnauthorizedError";
  }
}

let unauthorizedHandler: (() => void) | null = null;

export function onUnauthorized(cb: (() => void) | null): void {
  unauthorizedHandler = cb;
}

type ApiOptions = { handleUnauthorized?: boolean };

async function errorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // corpo vazio ou não é JSON
  }
  return GENERIC_ERROR;
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
  { handleUnauthorized = true }: ApiOptions = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    init.body !== undefined &&
    init.body !== null &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (res.status === 401) {
    const message = await errorDetail(res);
    if (handleUnauthorized) {
      unauthorizedHandler?.();
      throw new UnauthorizedError();
    }
    throw new ApiError(401, message);
  }
  if (!res.ok) throw new ApiError(res.status, await errorDetail(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function login(
  username: string,
  password: string,
): Promise<{ username: string }> {
  return apiFetch(
    "/api/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
    { handleUnauthorized: false },
  );
}

export function me(): Promise<User> {
  return apiFetch<User>("/api/me");
}

export function logout(): Promise<void> {
  return apiFetch<void>("/api/logout", { method: "POST" });
}
