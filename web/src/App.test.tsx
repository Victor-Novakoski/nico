import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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

  it("volta ao login depois de sair", async () => {
    const fetchMock = vi.fn((path: string) =>
      Promise.resolve(
        path === "/api/logout"
          ? jsonResponse(204)
          : jsonResponse(200, { username: "ana", person_id: "p1" }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Sair" }));
    expect(
      await screen.findByRole("button", { name: "Entrar" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("abre a tela de meios de pagamento pelo menu", async () => {
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
    fireEvent.click(
      await screen.findByRole("button", { name: "Meios de pagamento" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Meios de pagamento" }),
    ).toBeInTheDocument();
  });
});
