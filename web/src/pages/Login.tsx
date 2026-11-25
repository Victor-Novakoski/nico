import { useState, type FormEvent } from "react";
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
    <main className="login">
      <h1>Nico</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="username">Usuário</label>
        <input
          id="username"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <label htmlFor="password">Senha</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
