import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { logout, me, onUnauthorized } from "./api";
import { Entry } from "./pages/Entry";
import { Login } from "./pages/Login";
import { PaymentMethods } from "./pages/PaymentMethods";

type State =
  | { status: "loading" }
  | { status: "out" }
  | { status: "in"; username: string; personId: string | null };

type Page = "entry" | "payment-methods";

export function App() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [page, setPage] = useState<Page>("entry");

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
    setPage("entry");
  }

  if (state.status === "loading")
    return <p className="p-4 text-center text-muted-foreground">Carregando…</p>;
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
      <nav className="flex gap-2 px-4 pt-4">
        <Button
          type="button"
          variant={page === "entry" ? "default" : "outline"}
          className="flex-1"
          aria-current={page === "entry" ? "page" : undefined}
          onClick={() => setPage("entry")}
        >
          Lançar
        </Button>
        <Button
          type="button"
          variant={page === "payment-methods" ? "default" : "outline"}
          className="flex-1"
          aria-current={page === "payment-methods" ? "page" : undefined}
          onClick={() => setPage("payment-methods")}
        >
          Meios de pagamento
        </Button>
      </nav>
      {page === "payment-methods" ? (
        <PaymentMethods personId={state.personId} />
      ) : (
        <Entry personId={state.personId} />
      )}
      <div className="flex justify-center p-4">
        <Button type="button" variant="outline" onClick={handleLogout}>
          Sair
        </Button>
      </div>
    </>
  );
}
