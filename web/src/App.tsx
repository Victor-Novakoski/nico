import { useEffect, useState } from "react";
import { logout, me, onUnauthorized } from "./api";
import { Login } from "./pages/Login";
import { PaymentMethods } from "./pages/PaymentMethods";

type State =
  | { status: "loading" }
  | { status: "out" }
  | { status: "in"; username: string; personId: string | null };

type Page = "home" | "payment-methods";

export function App() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [page, setPage] = useState<Page>("home");

  useEffect(() => {
    onUnauthorized(() => setState({ status: "out" }));
    let active = true;
    me()
      .then((user) => {
        if (active)
          setState({
            status: "in",
            username: user.username,
            personId: user.person_id,
          });
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
    setPage("home");
  }

  if (state.status === "loading") return <p className="loading">Carregando…</p>;
  if (state.status === "out") {
    return (
      <Login
        onLoggedIn={(username) => {
          setState({ status: "in", username, personId: null });
          // O login não devolve a pessoa; busca para o dono padrão dos meios.
          me()
            .then((user) =>
              setState({
                status: "in",
                username: user.username,
                personId: user.person_id,
              }),
            )
            .catch(() => {});
        }}
      />
    );
  }
  return (
    <>
      <nav className="nav">
        <button
          type="button"
          className={page === "home" ? "" : "secondary"}
          aria-current={page === "home" ? "page" : undefined}
          onClick={() => setPage("home")}
        >
          Início
        </button>
        <button
          type="button"
          className={page === "payment-methods" ? "" : "secondary"}
          aria-current={page === "payment-methods" ? "page" : undefined}
          onClick={() => setPage("payment-methods")}
        >
          Meios de pagamento
        </button>
      </nav>
      {page === "payment-methods" ? (
        <PaymentMethods personId={state.personId} />
      ) : (
        <main className="home">
          <h1>Olá, {state.username}</h1>
          <p>Seus gastos do jeito que vierem.</p>
        </main>
      )}
      <div className="logout">
        <button type="button" className="secondary" onClick={handleLogout}>
          Sair
        </button>
      </div>
    </>
  );
}
