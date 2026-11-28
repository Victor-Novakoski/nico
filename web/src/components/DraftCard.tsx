import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  ApiError,
  type DraftSources,
  type PaymentMethod,
  type Person,
  type PurchaseStatus,
} from "../api";

export type DraftValues = {
  description: string;
  amount: string; // em reais, como a pessoa digita ("120,50")
  methodId: string;
  date: string; // AAAA-MM-DD
  installments: string;
  ownerId: string;
};

export type SaveInput = {
  description: string;
  totalCents: number;
  methodId: string;
  date: string;
  installments: number;
  ownerId: string;
};

type Props = {
  initial: DraftValues;
  sources?: DraftSources;
  methods: PaymentMethod[];
  people: Person[];
  onSave: (input: SaveInput, status: PurchaseStatus) => Promise<void>;
};

const HINT = "Assumido pelo app, confira.";

export function parseAmountCents(text: string): number | null {
  const raw = text.trim();
  // Sem vírgula, um ponto seguido de 1 ou 2 dígitos no fim é decimal ("12.50",
  // teclado do Android); fora isso, ponto é separador de milhar ("1.234,56").
  const clean =
    !raw.includes(",") && /^\d+\.\d{1,2}$/.test(raw)
      ? raw
      : raw.replace(/\./g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const [reais, cents = ""] = clean.split(".");
  return Number(reais) * 100 + Number(cents.padEnd(2, "0"));
}

export function centsToInput(cents: number): string {
  return (cents / 100).toFixed(2).replace(".", ",");
}

export function DraftCard({
  initial,
  sources,
  methods,
  people,
  onSave,
}: Props) {
  const [values, setValues] = useState<DraftValues>(initial);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<PurchaseStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const method = methods.find((m) => m.id === values.methodId);
  const isCash = method !== undefined && method.kind !== "credito";

  function set<K extends keyof DraftValues>(key: K, value: DraftValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function hint(field: string) {
    return sources?.[field] === "padrao" ? (
      <small className="-mt-2 text-aviso">{HINT}</small>
    ) : null;
  }

  async function save(status: PurchaseStatus) {
    const totalCents = parseAmountCents(values.amount);
    const installments = Number(values.installments);
    if (totalCents === null || totalCents <= 0) {
      setError("Informe um valor maior que zero.");
      return;
    }
    if (!values.description.trim()) {
      setError("Informe a descrição.");
      return;
    }
    if (!values.methodId) {
      setError("Escolha o meio de pagamento.");
      return;
    }
    if (!Number.isInteger(installments) || installments < 1) {
      setError("Parcelas deve ser 1 ou mais.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await onSave(
        {
          description: values.description.trim(),
          totalCents,
          methodId: values.methodId,
          date: values.date,
          installments: isCash ? 1 : installments,
          ownerId: values.ownerId,
        },
        status,
      );
      setSaved(status);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Sem conexão com o servidor. Tente de novo.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (saved) {
    return (
      <li className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 text-card-foreground">
        <p>
          Salvo como {saved}: {values.description} (R${" "}
          <span className="font-display text-valor">{values.amount}</span>)
        </p>
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 text-card-foreground">
      <label className="flex flex-col gap-2 font-semibold">
        Valor (R$)
        <Input
          inputMode="decimal"
          className="font-display text-valor"
          value={values.amount}
          onChange={(e) => set("amount", e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-2 font-semibold">
        Descrição
        <Input
          value={values.description}
          onChange={(e) => set("description", e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-2 font-semibold">
        Meio de pagamento
        <Select
          value={values.methodId}
          onChange={(e) => set("methodId", e.target.value)}
        >
          <option value="">Escolha…</option>
          {methods.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </Select>
      </label>
      {hint("method_id")}
      <label className="flex flex-col gap-2 font-semibold">
        Data
        <Input
          type="date"
          value={values.date}
          onChange={(e) => set("date", e.target.value)}
        />
      </label>
      {hint("purchase_date")}
      {!isCash && (
        <label className="flex flex-col gap-2 font-semibold">
          Parcelas
          <Input
            type="number"
            min={1}
            value={values.installments}
            onChange={(e) => set("installments", e.target.value)}
          />
        </label>
      )}
      <label className="flex flex-col gap-2 font-semibold">
        De quem é
        <Select
          value={values.ownerId}
          onChange={(e) => set("ownerId", e.target.value)}
        >
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
      </label>
      {hint("person_id")}
      {error && (
        <p role="alert" className="m-0 text-destructive">
          {error}
        </p>
      )}
      <Button
        type="button"
        size="lg"
        disabled={saving}
        onClick={() => save("pendente")}
      >
        Salvar como pendente
      </Button>
      <Button
        type="button"
        variant="outline"
        size="lg"
        disabled={saving}
        onClick={() => save("conferido")}
      >
        Conferido
      </Button>
    </li>
  );
}
