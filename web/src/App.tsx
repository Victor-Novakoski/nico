import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { logout, me, onUnauthorized } from "./api";
import { CashMonth } from "./pages/CashMonth";
import { Entry } from "./pages/Entry";
import { Invoice } from "./pages/Invoice";
import { Login } from "./pages/Login";
import { Pending } from "./pages/Pending";
import { PaymentMethods } from "./pages/PaymentMethods";
import { Settings } from "./pages/Settings";

type State =
  | { status: "loading" }
  | { status: "out" }
  | { status: "in"; username: string; personId: string | null };

type Tab = "entry" | "pending" | "month" | "more";
type MonthView = "invoice" | "cash";
type MoreView = "menu" | "payment-methods" | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "entry", label: "Lançar" },
  { id: "pending", label: "Conferir" },
  { id: "month", label: "Mês" },
  { id: "more", label: "Mais" },
];

export function App() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [tab, setTab] = useState<Tab>("entry");
  const [monthView, setMonthView] = useState<MonthView>("invoice");
  const [moreView, setMoreView] = useState<MoreView>("menu");

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
    setTab("entry");
    setMoreView("menu");
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
      {tab === "entry" && <Entry personId={state.personId} />}
      {tab === "pending" && <Pending />}
      {tab === "month" && (
        <>
          <div className="mx-auto flex max-w-[480px] gap-2 px-4 pt-4">
            <Button
              type="button"
              variant={monthView === "invoice" ? "default" : "outline"}
              className="flex-1"
              aria-pressed={monthView === "invoice"}
              onClick={() => setMonthView("invoice")}
            >
              Fatura
            </Button>
            <Button
              type="button"
              variant={monthView === "cash" ? "default" : "outline"}
              className="flex-1"
              aria-pressed={monthView === "cash"}
              onClick={() => setMonthView("cash")}
            >
              À vista
            </Button>
          </div>
          {monthView === "invoice" ? <Invoice /> : <CashMonth />}
        </>
      )}
      {tab === "more" && moreView === "payment-methods" && (
        <PaymentMethods personId={state.personId} />
      )}
      {tab === "more" && moreView === "settings" && <Settings />}
      {tab === "more" && moreView === "menu" && (
        <main className="mx-auto max-w-[480px] p-4 pb-24">
          <h1 className="mb-4 font-display text-3xl font-semibold">Mais</h1>
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-12 justify-start"
              onClick={() => setMoreView("payment-methods")}
            >
              Meios de pagamento
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-12 justify-start"
              onClick={() => setMoreView("settings")}
            >
              Configurações
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-12 justify-start"
              onClick={handleLogout}
            >
              Sair
            </Button>
          </div>
        </main>
      )}
      <nav
        aria-label="Navegação"
        className="fixed inset-x-0 bottom-0 z-10 border-t bg-background"
      >
        <div className="mx-auto flex max-w-[480px]">
          {TABS.map(({ id, label }) => {
            const active = tab === id;
            return (
              <button
                key={id}
                type="button"
                aria-current={active ? "page" : undefined}
                className={`flex min-h-12 flex-1 flex-col items-center justify-center gap-1 text-sm ${
                  active
                    ? "font-semibold text-foreground"
                    : "text-muted-foreground"
                }`}
                onClick={() => {
                  setTab(id);
                  if (id === "more") setMoreView("menu");
                }}
              >
                <span
                  aria-hidden="true"
                  className={`size-[5px] rounded-full ${active ? "bg-valor" : "bg-transparent"}`}
                />
                {label}
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
}
