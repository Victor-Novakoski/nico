# Backend (Python)

Núcleo de cálculo do Nico. `src/nico/billing.py` é lógica pura (só stdlib); `app.py` é o app FastAPI (sem banco ainda, decisão 001) e `config.py` lê variáveis de ambiente.

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
- O fixture de teste faz `drop schema public cascade`: use só o Postgres descartável, nunca um banco real.

## Ver também

- `docs/decisoes/002-ia-propoe-codigo-decide.md`
- `docs/decisoes/004-fatura-com-datas-gravadas.md`
- `docs/decisoes/007-modo-sem-ia-e-ordem-de-construcao.md`
- `docs/decisoes/008-regras-do-calculo-de-fatura.md`
