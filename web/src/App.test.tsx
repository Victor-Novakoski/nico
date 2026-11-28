import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { App } from "./App";

function jsonResponse(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("mostra o login quando não há sessão", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(401, { detail: "x" })),
    );
    render(<App />);
    expect(screen.getByText("Carregando…")).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Entrar" }),
    ).toBeInTheDocument();
  });

  it("mostra a tela inicial quando há sessão", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) =>
        Promise.resolve(
          path === "/api/me"
            ? jsonResponse(200, { username: "ana", person_id: "p1" })
            : jsonResponse(200, []),
        ),
      ),
    );
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Lançar gastos" }),
    ).toBeInTheDocument();
  });

  function stubSession() {
    const fetchMock = vi.fn((path: string) =>
      Promise.resolve(
        path === "/api/logout"
          ? jsonResponse(204)
          : path === "/api/me"
            ? jsonResponse(200, { username: "ana", person_id: "p1" })
            : jsonResponse(200, []),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  function tab(name: string) {
    return within(
      screen.getByRole("navigation", { name: "Navegação" }),
    ).getByRole("button", { name });
  }

  it("marca a aba ativa na barra de baixo", async () => {
    stubSession();
    render(<App />);
    await screen.findByRole("heading", { name: "Lançar gastos" });
    expect(tab("Lançar")).toHaveAttribute("aria-current", "page");
    expect(tab("Conferir")).not.toHaveAttribute("aria-current");
    fireEvent.click(tab("Conferir"));
    expect(tab("Conferir")).toHaveAttribute("aria-current", "page");
    expect(tab("Lançar")).not.toHaveAttribute("aria-current");
  });

  it("vai a Conferir", async () => {
    stubSession();
    render(<App />);
    await screen.findByRole("heading", { name: "Lançar gastos" });
    fireEvent.click(tab("Conferir"));
    expect(
      screen.getByRole("heading", { name: "Pra conferir" }),
    ).toBeInTheDocument();
  });

  it("em Mês alterna entre Fatura e À vista", async () => {
    stubSession();
    render(<App />);
    await screen.findByRole("heading", { name: "Lançar gastos" });
    fireEvent.click(tab("Mês"));
    expect(screen.getByRole("heading", { name: "Fatura" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "À vista" }));
    expect(
      screen.getByRole("heading", { name: "À vista" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Fatura" }));
    expect(screen.getByRole("heading", { name: "Fatura" })).toBeInTheDocument();
  });

  it("abre Configurações por Mais", async () => {
    stubSession();
    render(<App />);
    await screen.findByRole("heading", { name: "Lançar gastos" });
    fireEvent.click(tab("Mais"));
    fireEvent.click(screen.getByRole("button", { name: "Configurações" }));
    expect(
      screen.getByRole("heading", { name: "Configurações" }),
    ).toBeInTheDocument();
  });

  it("volta ao login depois de sair", async () => {
    const fetchMock = stubSession();
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Mais" }));
    fireEvent.click(screen.getByRole("button", { name: "Sair" }));
    expect(
      await screen.findByRole("button", { name: "Entrar" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("abre a tela de meios de pagamento por Mais", async () => {
    stubSession();
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Mais" }));
    fireEvent.click(screen.getByRole("button", { name: "Meios de pagamento" }));
    expect(
      await screen.findByRole("heading", { name: "Meios de pagamento" }),
    ).toBeInTheDocument();
  });
});
