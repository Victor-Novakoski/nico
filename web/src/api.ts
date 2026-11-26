const GENERIC_ERROR = "Algo deu errado. Tente de novo.";
const INVALID_FIELDS = "Confira os campos e tente de novo.";

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
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // Só as mensagens dos nossos validadores ("Value error, ...") estão em
      // português; as padrão do Pydantic vêm em inglês e viram a genérica.
      const msgs = detail
        .map((d) => (typeof d?.msg === "string" ? d.msg : ""))
        .filter((m) => m.startsWith("Value error, "))
        .map((m) => m.replace(/^Value error, /, ""));
      return msgs.length > 0 ? msgs.join(" ") : INVALID_FIELDS;
    }
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

export type Kind = "credito" | "debito" | "pix" | "dinheiro";

export type PaymentMethod = {
  id: string;
  name: string;
  owner_id: string;
  kind: Kind;
  closing_day: number | null;
  due_day: number | null;
  aliases: string[];
};

export type Person = { id: string; name: string };

export type NewPaymentMethod = {
  name: string;
  owner_id: string;
  kind: Kind;
  closing_day?: number;
  due_day?: number;
};

export function listPaymentMethods(): Promise<PaymentMethod[]> {
  return apiFetch<PaymentMethod[]>("/api/payment-methods");
}

export function createPaymentMethod(
  data: NewPaymentMethod,
): Promise<PaymentMethod> {
  return apiFetch<PaymentMethod>("/api/payment-methods", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function addAlias(id: string, alias: string): Promise<PaymentMethod> {
  return apiFetch<PaymentMethod>(
    `/api/payment-methods/${encodeURIComponent(id)}/aliases`,
    { method: "POST", body: JSON.stringify({ alias }) },
  );
}

export function listPeople(): Promise<Person[]> {
  return apiFetch<Person[]>("/api/people");
}

export type DraftSources = Record<string, "frase" | "padrao">;

export type DraftSpan = { field: string; start: number; end: number };

export type Draft = {
  description: string;
  amount_cents: number;
  method_id: string | null;
  method_type: Kind | null;
  person_id: string;
  purchase_date: string;
  installments: number;
  missing: string[];
  sources: DraftSources;
  spans?: DraftSpan[];
};

export type ParseResult = {
  understood: boolean;
  drafts: Draft[];
  fallback?: string;
};

export function parseDrafts(text: string): Promise<ParseResult> {
  return apiFetch<ParseResult>("/api/drafts/parse", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export type PurchaseStatus = "pendente" | "conferido";

export type NewPurchase = {
  id: string;
  payment_method_id: string;
  description: string;
  total_cents: number;
  purchase_date: string;
  installments: number;
  status: PurchaseStatus;
  shares?: { person_id: string; weight: number }[];
};

export function createPurchase(data: NewPurchase): Promise<{ id: string }> {
  return apiFetch<{ id: string }>("/api/purchases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
