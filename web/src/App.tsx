import { useEffect, useState } from "react";
import { logout, me, onUnauthorized } from "./api";
import { Login } from "./pages/Login";

type State =
  | { status: "loading" }
  | { status: "out" }
  | { status: "in"; username: string };

export function App() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    onUnauthorized(() => setState({ status: "out" }));
    let active = true;
    me()
      .then((user) => {
        if (active) setState({ status: "in", username: user.username });
      })
      .catch(() => {
        if (active) setState({ status: "out" });
      });
    return () => {
      active = false;
      onUnauthorized(null);
    };
  }, []);

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // sem sessão ou sem rede: volta ao login mesmo assim
    }
    setState({ status: "out" });
  }

  if (state.status === "loading") return <p className="loading">Carregando…</p>;
  if (state.status === "out") {
    return (
      <Login onLoggedIn={(username) => setState({ status: "in", username })} />
    );
  }
  return (
    <main className="home">
      <h1>Olá, {state.username}</h1>
      <p>Seus gastos do jeito que vierem.</p>
      <button type="button" className="secondary" onClick={handleLogout}>
        Sair
      </button>
    </main>
  );
}
