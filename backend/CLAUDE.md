# Backend (Python)

Núcleo de cálculo do Nico. `src/nico/billing.py` é lógica pura (só stdlib); `app.py` é o app FastAPI; `db.py` tem o pool (criado no `lifespan` se `DATABASE_URL` existir; sem ela o app sobe e `get_conn` responde 503) e a dependência `get_conn` e `config.py` lê variáveis de ambiente.

## Comandos

```
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/uvicorn nico.app:app --reload   # roda local; teste: curl localhost:8000/api/health
```

## Banco de teste

Os testes de banco usam um Postgres descartável, lido de `NICO_TEST_DATABASE_URL`. Sem a variável, esses testes são pulados (o resto roda normal).

```
docker compose up -d          # na raiz; Postgres 17 na porta 5433, volume nico_pgdata
export NICO_TEST_DATABASE_URL=postgresql://nico@localhost:5433/nico   # só de teste local
backend/.venv/bin/pytest backend -q
docker compose down           # sem -v, para manter o volume
```

Na CI, o job do backend sobe o mesmo Postgres como `services` e define a variável.

## Migrações

SQL puro em `backend/migrations/NNN_nome.sql`, aplicado em ordem por `python -m nico.migrate` (lê `DATABASE_URL`; cada arquivo numa transação, registrado em `schema_migrations`; rodar de novo não faz nada). Sem ORM.

```
cd backend && DATABASE_URL=postgresql://nico@localhost:5433/nico .venv/bin/python -m nico.migrate
```

## Usuários

Não há tela de cadastro. Crie à mão (pede a senha duas vezes, mínimo 8 caracteres; nunca por argumento). A pessoa é criada se ainda não existir. A senha é guardada com scrypt (`nico.auth`, parâmetros dentro do hash).

```
cd backend && DATABASE_URL=postgresql://nico@localhost:5433/nico .venv/bin/python -m nico.create_user <username> <nome da pessoa>
```

Login: `POST /api/login` grava o cookie `nico_session` (HttpOnly, Secure, SameSite=Lax, 30 dias), um token assinado com HMAC-SHA256 por `NICO_SECRET_KEY` (sem padrão; gere como no `.env.example`). `current_user` confere cookie e usuário no banco; rotas novas entram com `app.include_router(x.router, dependencies=PROTECTED)` (`app.py`) e um teste garante 401 sem cookie em toda rota `/api` fora `/api/health` e `/api/login`. O `person_id` do usuário logado é o autor dos lançamentos, nunca o corpo da requisição. O limite de 5 senhas erradas em 15 minutos por username fica em memória, por instância. Em teste de rota use `TestClient(app, base_url="https://testserver")` (cookie Secure) e o fixture `logged_client`.

## IA (decisão 006)

`ai/schema.py` (o que a IA devolve e a conferência), `ai/cascade.py` (ordem e quando passar adiante), `ai/prompt.py` (contexto, prompt e schema iguais para todo provedor), `ai/http.py` (`call` traduz 429/5xx/tempo esgotado em `ProviderUnavailable` e 401/403/4xx em `ProviderConfigError`), `ai/registry.py` (nome em `AI_PROVIDERS` → `from_env()` do módulo, import tardio). Provedor novo: módulo `ai/<nome>.py` com uma classe e `from_env()`; testes com `httpx.MockTransport`, sem rede.

## Regras

- Dinheiro sempre em centavos `int`, nunca `float`. Data e parcela são calculadas aqui, nunca pelo modelo de IA (decisão 002).
- A competência da fatura é o mês do vencimento. A fatura guarda as próprias datas de fechamento e vencimento (decisão 004).
- Dia maior que o mês vira o último dia do mês. O mês do vencimento sai dos dias configurados (`due_day > closing_day` → mesmo mês; senão, mês seguinte), nunca das datas ajustadas: cada mês de fechamento tem uma competência só (decisão 008).
- Testes sem rede; nomes de pessoas e valores inventados.

## Armadilhas conhecidas

- Suposições a confirmar com faturas reais (decisão 004): compra no dia do fechamento entra na fatura seguinte; o centavo que sobra vai para a primeira parcela. Ao confirmar, ajuste o código, os testes e a decisão.
- Sobras da divisão por pessoa vão na ordem alfabética das chaves, não na de inserção.
- Comparar as datas já ajustadas para decidir o mês do vencimento repete competência (fecha 28 e vence 31: fevereiro e março viravam março). O teste `test_consecutive_invoices_never_repeat_the_competence` pega isso; não o afrouxe.
- Com `due_day > closing_day`, num mês curto fechamento e vencimento podem cair no mesmo dia (fecha 30 e vence 31 em fevereiro: os dois em 28/02).

- Migração já aplicada não se edita: crie a próxima (`002_...sql`). O arquivo é registrado pelo nome.
- `invoice` só aceita meio de crédito por chave estrangeira composta `(payment_method_id, kind)`; `purchase`/`installment` não impõem isso no banco (quem grava parcelas só chama o cálculo para crédito).
- Fixture `db_url` (`tests/conftest.py`): recria o schema, migra e devolve a URL; use nos testes de banco. Pula sem a variável.
- O fixture de teste faz `drop schema public cascade`: use só o Postgres descartável, nunca um banco real.

## Ver também

- `docs/decisoes/002-ia-propoe-codigo-decide.md`
- `docs/decisoes/004-fatura-com-datas-gravadas.md`
- `docs/decisoes/007-modo-sem-ia-e-ordem-de-construcao.md`
- `docs/decisoes/008-regras-do-calculo-de-fatura.md`
