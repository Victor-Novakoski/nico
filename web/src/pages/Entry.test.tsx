import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Entry } from "./Entry";
import { parseAmountCents } from "../components/DraftCard";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status });
}

const PEOPLE = [
  { id: "p1", name: "Ana" },
  { id: "p2", name: "Beto" },
];

const METHODS = [
  {
    id: "m1",
    name: "Nubank",
    owner_id: "p1",
    kind: "credito",
    closing_day: 5,
    due_day: 12,
    aliases: [],
  },
];

const DRAFT = {
  description: "mercado",
  amount_cents: 12000,
  method_id: "m1",
  method_type: "credito",
  person_id: "p1",
  purchase_date: "2026-11-26",
  installments: 3,
  missing: [],
  sources: { amount_cents: "frase", method_id: "frase", person_id: "padrao" },
};

function mockApi(parse: unknown) {
  const fn = vi.fn((path: string, init: RequestInit = {}) => {
    const key = `${init.method ?? "GET"} ${path}`;
    if (key === "GET /api/payment-methods")
      return Promise.resolve(jsonResponse(200, METHODS));
    if (key === "GET /api/people")
      return Promise.resolve(jsonResponse(200, PEOPLE));
    if (key === "POST /api/drafts/parse")
      return Promise.resolve(jsonResponse(200, parse));
    if (key === "POST /api/purchases")
      return Promise.resolve(jsonResponse(201, { id: "x" }));
    return Promise.resolve(jsonResponse(404, { detail: "Não encontrado" }));
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

async function typeAndParse(text: string) {
  render(<Entry personId="p1" />);
  await screen.findByLabelText("Conte o gasto do jeito que vier");
  fireEvent.change(screen.getByLabelText("Conte o gasto do jeito que vier"), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: "Montar lançamentos" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("Entry", () => {
  it("mostra a frase colorida com os trechos de cada rascunho", async () => {
    const phrase = "120 mercado nubank 3x e 15 de pão";
    mockApi({
      understood: true,
      drafts: [
        { ...DRAFT, spans: [{ field: "amount_cents", start: 0, end: 3 }] },
        {
          ...DRAFT,
          description: "pão",
          amount_cents: 1500,
          spans: [{ field: "amount_cents", start: 24, end: 26 }],
        },
      ],
    });
    await typeAndParse(phrase);
    await screen.findAllByLabelText("Descrição");
    const valores = [
      ...document.querySelectorAll('[data-field="amount_cents"]'),
    ].map((el) => el.textContent);
    expect(valores).toEqual(["120", "15"]);
  });

  it("sem frase entendida (formulário manual) não mostra a frase colorida", async () => {
    mockApi({ understood: false, drafts: [] });
    await typeAndParse("comprei uma coisa ontem");
    await screen.findAllByLabelText("Descrição");
    expect(document.querySelector("[data-field]")).toBeNull();
  });

  it("frase entendida vira um cartão editável", async () => {
    mockApi({ understood: true, drafts: [DRAFT] });
    await typeAndParse("120 mercado nubank 3x");
    expect(await screen.findByLabelText("Descrição")).toHaveValue("mercado");
    expect(screen.getByLabelText("Valor (R$)")).toHaveValue("120,00");
    expect(screen.getByLabelText("Parcelas")).toHaveValue(3);
    expect(screen.getByLabelText("De quem é")).toHaveValue("p1");
    expect(screen.getByText("Assumido pelo app, confira.")).toBeInTheDocument();
  });

  it("sem rascunhos abre o formulário com o texto na descrição", async () => {
    mockApi({ understood: false, drafts: [] });
    await typeAndParse("comprei uma coisa ontem");
    expect(await screen.findByLabelText("Descrição")).toHaveValue(
      "comprei uma coisa ontem",
    );
    expect(screen.getByLabelText("Valor (R$)")).toHaveValue("");
    expect(screen.getByLabelText("De quem é")).toHaveValue("p1");
  });

  it("salva com id aleatório e o status escolhido", async () => {
    const uuid = "11111111-1111-4111-8111-111111111111";
    vi.spyOn(crypto, "randomUUID").mockReturnValue(uuid);
    const fn = mockApi({ understood: true, drafts: [DRAFT] });
    await typeAndParse("120 mercado nubank 3x");
    fireEvent.click(await screen.findByRole("button", { name: "Conferido" }));
    await waitFor(() =>
      expect(screen.getByText(/Salvo como conferido/)).toBeInTheDocument(),
    );
    const call = fn.mock.calls.find(
      ([p, init]) => p === "/api/purchases" && init?.method === "POST",
    );
    expect(JSON.parse(call![1]!.body as string)).toEqual({
      id: uuid,
      payment_method_id: "m1",
      description: "mercado",
      total_cents: 12000,
      purchase_date: "2026-11-26",
      installments: 3,
      status: "conferido",
      shares: [{ person_id: "p1", weight: 1 }],
    });
  });
});

describe("parseAmountCents", () => {
  it("aceita vírgula, ponto decimal e milhar", () => {
    expect(parseAmountCents("12,50")).toBe(1250);
    expect(parseAmountCents("12.50")).toBe(1250);
    expect(parseAmountCents("12.5")).toBe(1250);
    expect(parseAmountCents("1.234,56")).toBe(123456);
    expect(parseAmountCents("1.234")).toBe(123400);
    expect(parseAmountCents("120")).toBe(12000);
    expect(parseAmountCents("abc")).toBeNull();
  });
});
