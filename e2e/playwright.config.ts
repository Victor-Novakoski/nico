import { defineConfig, devices } from "@playwright/test";

// Tudo configurável por ambiente, para rodar igual local e na CI.
const apiPort = process.env.E2E_API_PORT ?? "8000";
const webPort = process.env.E2E_WEB_PORT ?? "4173";
const python = process.env.E2E_PYTHON ?? "python";
const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl || !process.env.E2E_PASSWORD) {
  throw new Error("Defina DATABASE_URL (banco só de teste) e E2E_PASSWORD.");
}

export default defineConfig({
  testDir: "./tests",
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Pixel 7"] } }],
  webServer: [
    {
      // Zera o banco, migra, cria o usuário e sobe a API.
      command: `${python} prepare_db.py && ${python} -m uvicorn nico.app:app --port ${apiPort}`,
      url: `http://localhost:${apiPort}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        DATABASE_URL: databaseUrl,
        // Chave descartável, só deste processo de teste.
        NICO_SECRET_KEY:
          process.env.NICO_SECRET_KEY ?? "chave-descartavel-do-e2e",
        E2E_PASSWORD: process.env.E2E_PASSWORD,
      },
    },
    {
      cwd: "../web",
      command: `npm run build && npx vite preview --port ${webPort} --strictPort`,
      url: `http://localhost:${webPort}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { E2E_API_PORT: apiPort },
    },
  ],
});
