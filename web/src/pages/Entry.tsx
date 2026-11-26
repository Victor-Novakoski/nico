import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  createPurchase,
  listPaymentMethods,
  listPeople,
  parseDrafts,
  type PaymentMethod,
  type Person,
} from "../api";
import {
  DraftCard,
  centsToInput,
  type DraftValues,
  type SaveInput,
} from "../components/DraftCard";
import type { DraftSources, PurchaseStatus } from "../api";

type Props = { personId: string | null };

type Card = { key: string; values: DraftValues; sources?: DraftSources };

function today(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

export function Entry({ personId }: Props) {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cards, setCards] = useState<Card[] | null>(null);
  const [manual, setManual] = useState(false);
  const [round, setRound] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([listPaymentMethods(), listPeople()])
      .then(([ms, ps]) => {
        if (!active) return;
        setMethods(Array.isArray(ms) ? ms : []);
        setPeople(Array.isArray(ps) ? ps : []);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const defaultOwner = personId ?? "";

  async function handleParse(e: FormEvent) {
    e.preventDefault();
    const phrase = text.trim();
    if (!phrase) return;
    setError(null);
    setParsing(true);
    try {
      const result = await parseDrafts(phrase);
      const empty =
        !result.drafts ||
        result.drafts.length === 0 ||
        result.fallback === "form";
      setRound((r) => r + 1);
      if (empty) {
        setManual(true);
        setCards([
          {
            key: "manual",
            values: {
              description: phrase,
              amount: "",
              methodId: "",
              date: today(),
              installments: "1",
              ownerId: defaultOwner,
            },
          },
        ]);
      } else {
        setManual(false);
        setCards(
          result.drafts.map((d, i) => ({
            key: `draft-${i}`,
            sources: d.sources,
            values: {
              description: d.description,
              amount: centsToInput(d.amount_cents),
              methodId: d.method_id ?? "",
              date: d.purchase_date,
              installments: String(d.installments),
              // "De quem é" começa com a pessoa logada (decisão 009).
              ownerId: defaultOwner || d.person_id,
            },
          })),
        );
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Sem conexão com o servidor. Tente de novo.",
      );
    } finally {
      setParsing(false);
    }
  }

  async function save(input: SaveInput, status: PurchaseStatus) {
    await createPurchase({
      id: crypto.randomUUID(),
      payment_method_id: input.methodId,
      description: input.description,
      total_cents: input.totalCents,
      purchase_date: input.date,
      installments: input.installments,
      status,
      ...(input.ownerId
        ? { shares: [{ person_id: input.ownerId, weight: 1 }] }
        : {}),
    });
  }

  return (
    <main className="entry">
      <h1>Lançar gastos</h1>
      <form onSubmit={handleParse}>
        <label htmlFor="entry-text">Conte o gasto do jeito que vier</label>
        <textarea
          id="entry-text"
          rows={5}
          placeholder="Ex.: 120 no mercado no cartão X em 3x"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" disabled={parsing || !text.trim()}>
          {parsing ? "Lendo…" : "Montar lançamentos"}
        </button>
      </form>
      {cards && (
        <section aria-label="Lançamentos para conferir">
          {manual && (
            <p>Não entendi a frase. Preencha os campos para lançar na mão.</p>
          )}
          <ul className="drafts">
            {cards.map((c) => (
              <DraftCard
                key={`${round}-${c.key}`}
                initial={c.values}
                sources={c.sources}
                methods={methods}
                people={people}
                onSave={save}
              />
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
