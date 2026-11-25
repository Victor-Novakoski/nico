import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("mostra o nome Nico na tela inicial", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Nico" })).toBeInTheDocument();
  });
});
