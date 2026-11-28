import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, login } from "../api";

type Props = { onLoggedIn: (username: string) => void };

export function Login({ onLoggedIn }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const user = await login(username, password);
      onLoggedIn(user.username);
    } catch (err) {
      // Só mensagens da API (em português); falha de rede vira a genérica.
      setError(
        err instanceof ApiError
          ? err.message
          : "Sem conexão com o servidor. Tente de novo.",
      );
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-[400px] px-4 py-8">
      <h1 className="mb-4 font-display text-3xl font-semibold">Nico</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <label htmlFor="username" className="font-semibold">
          Usuário
        </label>
        <Input
          id="username"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <label htmlFor="password" className="font-semibold">
          Senha
        </label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="m-0 text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={submitting}>
          {submitting ? "Entrando…" : "Entrar"}
        </Button>
      </form>
    </main>
  );
}
