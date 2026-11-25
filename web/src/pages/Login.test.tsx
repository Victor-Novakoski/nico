import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Login } from "./Login";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => vi.unstubAllGlobals());

function fill() {
  fireEvent.change(screen.getByLabelText("Usuário"), {
    target: { value: "ana" },
  });
  fireEvent.change(screen.getByLabelText("Senha"), {
    target: { value: "segredo-de-teste" },
  });
}

describe("Login", () => {
  it("envia o que foi digitado e avisa quando entra", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { username: "ana" }));
    vi.stubGlobal("fetch", fetchMock);
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(onLoggedIn).toHaveBeenCalledWith("ana"));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      username: "ana",
      password: "segredo-de-teste",
    });
  });

  it("mostra a mensagem quando a senha está errada", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(401, { detail: "Usuário ou senha incorretos" }),
        ),
    );
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Usuário ou senha incorretos",
    );
    expect(onLoggedIn).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeEnabled();
  });

  it("desabilita o botão enquanto envia", async () => {
    let resolve!: (r: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(new Promise<Response>((r) => (resolve = r))),
    );
    render(<Login onLoggedIn={vi.fn()} />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(screen.getByRole("button", { name: "Entrando…" })).toBeDisabled();
    resolve(jsonResponse(200, { username: "ana" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  });

  it("mostra mensagem em português quando não há rede", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    render(<Login onLoggedIn={vi.fn()} />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sem conexão com o servidor. Tente de novo.",
    );
  });
});
