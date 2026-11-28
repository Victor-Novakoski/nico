import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  ApiError,
  addAlias,
  createPaymentMethod,
  listPaymentMethods,
  listPeople,
  type Kind,
  type NewPaymentMethod,
  type PaymentMethod,
  type Person,
} from "../api";

type Props = { personId: string | null };

const KIND_LABELS: Record<Kind, string> = {
  credito: "Crédito",
  debito: "Débito",
  pix: "Pix",
  dinheiro: "Dinheiro",
};

function errorMessage(err: unknown): string {
  return err instanceof ApiError
    ? err.message
    : "Sem conexão com o servidor. Tente de novo.";
}

function replaceMethod(list: PaymentMethod[], updated: PaymentMethod) {
  return list.map((m) => (m.id === updated.id ? updated : m));
}

export function PaymentMethods({ personId }: Props) {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [kind, setKind] = useState<Kind>("credito");
  const [closingDay, setClosingDay] = useState("");
  const [dueDay, setDueDay] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [aliasDrafts, setAliasDrafts] = useState<Record<string, string>>({});
  const [aliasError, setAliasError] = useState<{
    id: string;
    message: string;
  } | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([listPaymentMethods(), listPeople()])
      .then(([ms, ps]) => {
        if (!active) return;
        setMethods(ms);
        setPeople(ps);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(errorMessage(err));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const personName = (id: string) =>
    people.find((p) => p.id === id)?.name ?? "—";

  // Dono escolhido; sem escolha, a pessoa logada (ou a primeira da lista).
  const selectedOwner =
    ownerId ??
    (people.some((p) => p.id === personId) ? personId : people[0]?.id) ??
    "";

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const body: NewPaymentMethod = {
      name,
      owner_id: selectedOwner,
      kind,
    };
    if (kind === "credito") {
      body.closing_day = Number(closingDay);
      body.due_day = Number(dueDay);
    }
    try {
      const created = await createPaymentMethod(body);
      setMethods((list) => [...list, created]);
      setName("");
      setClosingDay("");
      setDueDay("");
    } catch (err) {
      setError(errorMessage(err));
    }
    setSubmitting(false);
  }

  async function handleAlias(e: FormEvent, method: PaymentMethod) {
    e.preventDefault();
    const alias = (aliasDrafts[method.id] ?? "").trim();
    if (!alias) return;
    setAliasError(null);
    try {
      const updated = await addAlias(method.id, alias);
      setMethods((list) => replaceMethod(list, updated));
      setAliasDrafts((d) => ({ ...d, [method.id]: "" }));
    } catch (err) {
      setAliasError({ id: method.id, message: errorMessage(err) });
    }
  }

  return (
    <section className="mx-auto max-w-[480px] p-4">
      <h1 className="mb-4 font-display text-3xl font-semibold">
        Meios de pagamento
      </h1>
      {loading ? (
        <p>Carregando…</p>
      ) : methods.length === 0 ? (
        <p>Nenhum meio de pagamento cadastrado ainda.</p>
      ) : (
        <ul className="mb-6 flex list-none flex-col gap-3 p-0">
          {methods.map((m) => (
            <li
              key={m.id}
              className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 text-card-foreground"
            >
              <strong className="font-display text-lg">{m.name}</strong>
              <p className="my-1 text-muted-foreground">
                {KIND_LABELS[m.kind]}
                {m.kind === "credito" &&
                  ` · fecha dia ${m.closing_day}, vence dia ${m.due_day}`}
                {` · de ${personName(m.owner_id)}`}
              </p>
              {m.aliases.length > 0 && (
                <p className="my-1 text-muted-foreground">
                  Apelidos: {m.aliases.join(", ")}
                </p>
              )}
              <form
                className="mt-2 flex flex-col gap-2"
                onSubmit={(e) => handleAlias(e, m)}
              >
                <label htmlFor={`alias-${m.id}`}>
                  Novo apelido de {m.name}
                </label>
                <Input
                  id={`alias-${m.id}`}
                  value={aliasDrafts[m.id] ?? ""}
                  onChange={(e) =>
                    setAliasDrafts((d) => ({ ...d, [m.id]: e.target.value }))
                  }
                />
                {aliasError?.id === m.id && (
                  <p role="alert" className="m-0 text-destructive">
                    {aliasError.message}
                  </p>
                )}
                <Button type="submit" variant="outline">
                  Adicionar apelido
                </Button>
              </form>
            </li>
          ))}
        </ul>
      )}

      <h2 className="mb-2 font-display text-xl font-semibold">
        Novo meio de pagamento
      </h2>
      <form onSubmit={handleCreate} className="flex flex-col gap-2">
        <label htmlFor="pm-name" className="font-semibold">
          Nome
        </label>
        <Input
          id="pm-name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label htmlFor="pm-owner" className="font-semibold">
          Dono
        </label>
        <Select
          id="pm-owner"
          value={selectedOwner}
          onChange={(e) => setOwnerId(e.target.value)}
        >
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
        <label htmlFor="pm-kind" className="font-semibold">
          Tipo
        </label>
        <Select
          id="pm-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value as Kind)}
        >
          {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
            <option key={k} value={k}>
              {KIND_LABELS[k]}
            </option>
          ))}
        </Select>
        {kind === "credito" && (
          <>
            <label htmlFor="pm-closing" className="font-semibold">
              Dia de fechamento (1 a 31)
            </label>
            <Input
              id="pm-closing"
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
              required
              value={closingDay}
              onChange={(e) => setClosingDay(e.target.value)}
            />
            <label htmlFor="pm-due" className="font-semibold">
              Dia de vencimento (1 a 31)
            </label>
            <Input
              id="pm-due"
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
              required
              value={dueDay}
              onChange={(e) => setDueDay(e.target.value)}
            />
          </>
        )}
        {error && (
          <p role="alert" className="m-0 text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={submitting || !selectedOwner}>
          {submitting ? "Salvando…" : "Cadastrar"}
        </Button>
      </form>
    </section>
  );
}
