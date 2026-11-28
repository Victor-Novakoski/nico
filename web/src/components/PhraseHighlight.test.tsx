import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { PhraseHighlight } from "./PhraseHighlight";

const phrase = "120 no mercado no cartao X em 3x";

function colored(container: HTMLElement) {
  return [...container.querySelectorAll("p [data-field]")].map((el) => [
    el.getAttribute("data-field"),
    el.textContent,
  ]);
}

describe("PhraseHighlight", () => {
  it("colore cada trecho no lugar certo", () => {
    const { container } = render(
      <PhraseHighlight
        phrase={phrase}
        spans={[
          { field: "amount_cents", start: 0, end: 3 },
          { field: "description", start: 7, end: 14 },
          { field: "installments", start: 30, end: 32 },
        ]}
      />,
    );
    expect(colored(container)).toEqual([
      ["amount_cents", "120"],
      ["description", "mercado"],
      ["installments", "3x"],
    ]);
    expect(container.querySelector("p")?.textContent).toBe(phrase);
    expect(
      (container.querySelector('[data-field="amount_cents"]') as HTMLElement)
        .style.color,
    ).toBe("var(--valor)");
  });

  it("ignora span invalido, sobreposto ou de campo desconhecido", () => {
    const { container } = render(
      <PhraseHighlight
        phrase={phrase}
        spans={[
          { field: "amount_cents", start: 0, end: 3 },
          { field: "description", start: 2, end: 10 },
          { field: "method_id", start: 5, end: 5 },
          { field: "method_id", start: 20, end: 99 },
          { field: "method_id", start: -1, end: 4 },
          { field: "outro", start: 15, end: 18 },
        ]}
      />,
    );
    expect(colored(container)).toEqual([["amount_cents", "120"]]);
    expect(container.querySelector("p")?.textContent).toBe(phrase);
  });

  it("mostra a frase normal sem spans e traz a legenda", () => {
    const { container, getByText } = render(
      <PhraseHighlight phrase={phrase} />,
    );
    expect(colored(container)).toEqual([]);
    expect(container.querySelector("p")?.textContent).toBe(phrase);
    for (const label of ["Valor", "O quê", "Meio", "Parcelas"]) {
      expect(getByText(label)).toBeTruthy();
    }
  });
});
