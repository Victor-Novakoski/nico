import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DraftCard, type DraftValues } from "./DraftCard";

const PEOPLE = [
  { id: "p1", name: "Ana" },
  { id: "p2", name: "Beto" },
];

const METHODS = [
  {
    id: "m1",
    name: "Nubank",
    owner_id: "p1",
    kind: "credito" as const,
    closing_day: 5,
    due_day: 12,
    aliases: [],
  },
  {
    id: "m2",
    name: "Pix",
    owner_id: "p1",
    kind: "pix" as const,
    closing_day: null,
    due_day: null,
    aliases: [],
  },
];

const INITIAL: DraftValues = {
  description: "mercado",
  amount: "120,00",
  methodId: "m2",
  date: "2026-11-26",
  installments: "1",
  ownerId: "p1",
};

function renderCard(sources: Record<string, "frase" | "padrao">) {
  return render(
    <DraftCard
      initial={INITIAL}
      sources={sources}
      methods={METHODS}
      people={PEOPLE}
      onSave={vi.fn(() => Promise.resolve())}
    />,
  );
}

describe("DraftCard", () => {
  it("meio vindo do padrão mostra o aviso e foca a escolha ao tocar", () => {
    renderCard({ method_id: "padrao" });
    const aviso = screen.getByRole("button", {
      name: "seu principal, você não disse",
    });
    fireEvent.click(aviso);
    expect(document.activeElement).toBe(
      screen.getByLabelText("Meio de pagamento"),
    );
  });

  it("meio vindo da frase não mostra aviso", () => {
    renderCard({ method_id: "frase" });
    expect(
      screen.queryByText("seu principal, você não disse"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Assumido pelo app, confira."),
    ).not.toBeInTheDocument();
  });

  it("pessoa vinda do padrão mantém o aviso genérico", () => {
    renderCard({ person_id: "padrao" });
    expect(screen.getByText("Assumido pelo app, confira.")).toBeInTheDocument();
    expect(
      screen.queryByText("seu principal, você não disse"),
    ).not.toBeInTheDocument();
  });
});
