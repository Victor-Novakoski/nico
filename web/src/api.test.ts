import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  UnauthorizedError,
  addAlias,
  apiFetch,
  createPaymentMethod,
  listPaymentMethods,
  listPeople,
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

  it("detail em lista junta as mensagens dos nossos validadores", async () => {
    mockFetch(
      reply(422, {
        detail: [
          { msg: "Value error, Dia inválido" },
          { msg: "Value error, Nome vazio" },
        ],
      }),
    );
    const err = await thrown(apiFetch("/api/x"));
    expect(err.message).toBe("Dia inválido Nome vazio");
  });

  it("mensagem padrão do Pydantic (em inglês) vira a de conferir os campos", async () => {
    mockFetch(
      reply(422, {
        detail: [{ msg: "Input should be greater than or equal to 1" }, {}],
      }),
    );
    const err = await thrown(apiFetch("/api/x"));
    expect(err.message).toBe("Confira os campos e tente de novo.");
  });

  it("corpo sem detail usa a mensagem padrão", async () => {
    mockFetch(reply(500, {}));
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

describe("meios de pagamento", () => {
  it("lista meios e pessoas pelas rotas certas", async () => {
    const fetchMock = mockFetch(reply(200, []));
    await listPaymentMethods();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/payment-methods");
    fetchMock.mockResolvedValue(reply(200, []));
    await listPeople();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/people");
  });

  it("cria meio com POST e corpo JSON", async () => {
    const fetchMock = mockFetch(reply(201, { id: "m1" }));
    await createPaymentMethod({ name: "Roxinho", owner_id: "p1", kind: "pix" });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/payment-methods");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      name: "Roxinho",
      owner_id: "p1",
      kind: "pix",
    });
  });

  it("adiciona apelido em /aliases", async () => {
    const fetchMock = mockFetch(reply(201, { id: "m1" }));
    await addAlias("m1", "roxo");
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/payment-methods/m1/aliases");
    expect(JSON.parse(init.body)).toEqual({ alias: "roxo" });
  });
});
