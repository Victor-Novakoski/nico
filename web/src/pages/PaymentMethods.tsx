import { useEffect, useState, type FormEvent } from "react";
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
    <section className="methods">
      <h1>Meios de pagamento</h1>
      {loading ? (
        <p>Carregando…</p>
      ) : methods.length === 0 ? (
        <p>Nenhum meio de pagamento cadastrado ainda.</p>
      ) : (
        <ul>
          {methods.map((m) => (
            <li key={m.id}>
              <strong>{m.name}</strong>
              <p className="meta">
                {KIND_LABELS[m.kind]}
                {m.kind === "credito" &&
                  ` · fecha dia ${m.closing_day}, vence dia ${m.due_day}`}
                {` · de ${personName(m.owner_id)}`}
              </p>
              {m.aliases.length > 0 && (
                <p className="meta">Apelidos: {m.aliases.join(", ")}</p>
              )}
              <form className="alias-form" onSubmit={(e) => handleAlias(e, m)}>
                <label htmlFor={`alias-${m.id}`}>
                  Novo apelido de {m.name}
                </label>
                <input
                  id={`alias-${m.id}`}
                  value={aliasDrafts[m.id] ?? ""}
                  onChange={(e) =>
                    setAliasDrafts((d) => ({ ...d, [m.id]: e.target.value }))
                  }
                />
                {aliasError?.id === m.id && (
                  <p role="alert" className="error">
                    {aliasError.message}
                  </p>
                )}
                <button type="submit" className="secondary">
                  Adicionar apelido
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}

      <h2>Novo meio de pagamento</h2>
      <form onSubmit={handleCreate}>
        <label htmlFor="pm-name">Nome</label>
        <input
          id="pm-name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label htmlFor="pm-owner">Dono</label>
        <select
          id="pm-owner"
          value={selectedOwner}
          onChange={(e) => setOwnerId(e.target.value)}
        >
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <label htmlFor="pm-kind">Tipo</label>
        <select
          id="pm-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value as Kind)}
        >
          {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
            <option key={k} value={k}>
              {KIND_LABELS[k]}
            </option>
          ))}
        </select>
        {kind === "credito" && (
          <>
            <label htmlFor="pm-closing">Dia de fechamento (1 a 31)</label>
            <input
              id="pm-closing"
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
              required
              value={closingDay}
              onChange={(e) => setClosingDay(e.target.value)}
            />
            <label htmlFor="pm-due">Dia de vencimento (1 a 31)</label>
            <input
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
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting || !selectedOwner}>
          {submitting ? "Salvando…" : "Cadastrar"}
        </button>
      </form>
    </section>
  );
}
