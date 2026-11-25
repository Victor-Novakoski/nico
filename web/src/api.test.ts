import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  UnauthorizedError,
  apiFetch,
  login,
  onUnauthorized,
} from "./api";

function reply(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
  });
}

function mockFetch(res: Response) {
  const fn = vi.fn().mockResolvedValue(res);
  vi.stubGlobal("fetch", fn);
  return fn;
}

async function thrown(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("esperava um erro");
}

afterEach(() => {
  vi.unstubAllGlobals();
  onUnauthorized(null);
});

describe("apiFetch", () => {
  it("envia o cookie (credentials include) e JSON quando há corpo", async () => {
    const fetchMock = mockFetch(reply(200, { ok: true }));
    await apiFetch("/api/x", { method: "POST", body: "{}" });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/x");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("Content-Type")).toBe(
      "application/json",
    );
  });

  it("401 chama o handler e lança UnauthorizedError", async () => {
    mockFetch(reply(401, { detail: "Não autenticado" }));
    const handler = vi.fn();
    onUnauthorized(handler);
    await expect(apiFetch("/api/me")).rejects.toBeInstanceOf(UnauthorizedError);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("erro com detail usa a mensagem da API", async () => {
    mockFetch(reply(429, { detail: "Muitas tentativas." }));
    const err = await thrown(apiFetch("/api/x"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(429);
    expect(err.message).toBe("Muitas tentativas.");
  });

  it("erro sem detail em texto usa a mensagem padrão", async () => {
    mockFetch(reply(422, { detail: [{ msg: "x" }] }));
    const err = await thrown(apiFetch("/api/x"));
    expect(err.message).toBe("Algo deu errado. Tente de novo.");
  });
});

describe("login", () => {
  it("401 no login não chama o handler e mostra a mensagem", async () => {
    const fetchMock = mockFetch(
      reply(401, { detail: "Usuário ou senha incorretos" }),
    );
    const handler = vi.fn();
    onUnauthorized(handler);
    const err = await thrown(login("ana", "errada"));
    expect(handler).not.toHaveBeenCalled();
    expect(err).toBeInstanceOf(ApiError);
    expect(err).not.toBeInstanceOf(UnauthorizedError);
    expect(err.message).toBe("Usuário ou senha incorretos");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      username: "ana",
      password: "errada",
    });
  });
});
