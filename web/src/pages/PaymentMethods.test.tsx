import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PaymentMethods } from "./PaymentMethods";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status });
}

const PEOPLE = [
  { id: "p1", name: "Ana" },
  { id: "p2", name: "Beto" },
];

const ROXINHO = {
  id: "m1",
  name: "Roxinho",
  owner_id: "p2",
  kind: "credito",
  closing_day: 5,
  due_day: 12,
  aliases: ["roxo"],
};

type Handler = (init: RequestInit) => Response;

function mockApi(extra: Record<string, Handler> = {}) {
  const fn = vi.fn((path: string, init: RequestInit = {}) => {
    const key = `${init.method ?? "GET"} ${path}`;
    if (extra[key]) return Promise.resolve(extra[key](init));
    if (key === "GET /api/payment-methods")
      return Promise.resolve(jsonResponse(200, [ROXINHO]));
    if (key === "GET /api/people")
      return Promise.resolve(jsonResponse(200, PEOPLE));
    return Promise.resolve(jsonResponse(404, { detail: "Não encontrado" }));
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function postBody(fn: ReturnType<typeof mockApi>, path: string) {
  const call = fn.mock.calls.find(
    ([p, init]) => p === path && init?.method === "POST",
  );
  return JSON.parse(call![1]!.body as string);
}

afterEach(() => vi.unstubAllGlobals());

describe("PaymentMethods", () => {
  it("mostra a lista vinda da API", async () => {
    mockApi();
    render(<PaymentMethods personId="p1" />);
    expect(await screen.findByText("Roxinho")).toBeInTheDocument();
    expect(
      screen.getByText(/Crédito · fecha dia 5, vence dia 12 · de Beto/),
    ).toBeInTheDocument();
    expect(screen.getByText("Apelidos: roxo")).toBeInTheDocument();
  });

  it("cria um crédito com os dias e ele aparece na lista", async () => {
    const created = {
      id: "m2",
      name: "Azulão",
      owner_id: "p1",
      kind: "credito",
      closing_day: 10,
      due_day: 17,
      aliases: [],
    };
    const fn = mockApi({
      "POST /api/payment-methods": () => jsonResponse(201, created),
    });
    render(<PaymentMethods personId="p1" />);
    await screen.findByText("Roxinho");
    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Azulão" },
    });
    fireEvent.change(screen.getByLabelText(/Dia de fechamento/), {
      target: { value: "10" },
    });
    fireEvent.change(screen.getByLabelText(/Dia de vencimento/), {
      target: { value: "17" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cadastrar" }));
    expect(await screen.findByText("Azulão")).toBeInTheDocument();
    expect(postBody(fn, "/api/payment-methods")).toEqual({
      name: "Azulão",
      owner_id: "p1",
      kind: "credito",
      closing_day: 10,
      due_day: 17,
    });
  });

  it("Pix esconde os dias e não os envia", async () => {
    const fn = mockApi({
      "POST /api/payment-methods": () =>
        jsonResponse(201, {
          id: "m3",
          name: "Pix da casa",
          owner_id: "p1",
          kind: "pix",
          closing_day: null,
          due_day: null,
          aliases: [],
        }),
    });
    render(<PaymentMethods personId="p1" />);
    await screen.findByText("Roxinho");
    expect(screen.getByLabelText(/Dia de fechamento/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Tipo"), {
      target: { value: "pix" },
    });
    expect(screen.queryByLabelText(/Dia de fechamento/)).toBeNull();
    expect(screen.queryByLabelText(/Dia de vencimento/)).toBeNull();
    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Pix da casa" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cadastrar" }));
    expect(await screen.findByText("Pix da casa")).toBeInTheDocument();
    expect(postBody(fn, "/api/payment-methods")).toEqual({
      name: "Pix da casa",
      owner_id: "p1",
      kind: "pix",
    });
  });

  it("mostra a mensagem quando a API recusa o cadastro", async () => {
    mockApi({
      "POST /api/payment-methods": () =>
        jsonResponse(422, { detail: "Dono não encontrado" }),
    });
    render(<PaymentMethods personId="p1" />);
    await screen.findByText("Roxinho");
    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Azulão" },
    });
    fireEvent.change(screen.getByLabelText(/Dia de fechamento/), {
      target: { value: "10" },
    });
    fireEvent.change(screen.getByLabelText(/Dia de vencimento/), {
      target: { value: "17" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cadastrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Dono não encontrado",
    );
  });

  it("adiciona apelido pela URL do meio e mostra na lista", async () => {
    const fn = mockApi({
      "POST /api/payment-methods/m1/aliases": () =>
        jsonResponse(201, { ...ROXINHO, aliases: ["roxo", "nu"] }),
    });
    render(<PaymentMethods personId="p1" />);
    await screen.findByText("Roxinho");
    fireEvent.change(screen.getByLabelText("Novo apelido de Roxinho"), {
      target: { value: "nu" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar apelido" }));
    expect(await screen.findByText("Apelidos: roxo, nu")).toBeInTheDocument();
    expect(postBody(fn, "/api/payment-methods/m1/aliases")).toEqual({
      alias: "nu",
    });
  });

  it("mostra a mensagem quando o apelido já é de outro meio", async () => {
    mockApi({
      "POST /api/payment-methods/m1/aliases": () =>
        jsonResponse(409, {
          detail: "Apelido já usado em outro meio de pagamento",
        }),
    });
    render(<PaymentMethods personId="p1" />);
    await screen.findByText("Roxinho");
    fireEvent.change(screen.getByLabelText("Novo apelido de Roxinho"), {
      target: { value: "nu" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar apelido" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Apelido já usado em outro meio de pagamento",
      ),
    );
  });
});
