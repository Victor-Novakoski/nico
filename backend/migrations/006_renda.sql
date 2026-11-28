-- Renda fixa e entradas avulsas (decisão 012). amount_cents nulo em recurring_income =
-- valor varia, informado a cada mês. Quem vê a renda de quem é decidido por
-- group_member.show_income (decisão 013), não aqui.

create table recurring_income (
    id uuid primary key default gen_random_uuid(),
    person_id uuid not null references person (id) on delete restrict,
    name text not null check (length(btrim(name)) > 0),
    day integer not null check (day between 1 and 31),
    amount_cents bigint check (amount_cents > 0),
    active boolean not null default true,
    created_at timestamptz not null default now()
);
create index recurring_income_person_id_idx on recurring_income (person_id);

create table income (
    id uuid primary key, -- gerado pelo cliente (idempotência do lançamento)
    person_id uuid not null references person (id) on delete restrict,
    description text not null,
    amount_cents bigint not null check (amount_cents > 0),
    received_on date not null,
    status text not null default 'pendente' check (status in ('pendente', 'conferido')),
    recurring_income_id uuid references recurring_income (id) on delete restrict,
    year integer,
    month integer check (month between 1 and 12),
    created_at timestamptz not null default now(),
    check (recurring_income_id is null or (year is not null and month is not null)),
    unique (recurring_income_id, year, month)
);
create index income_person_id_idx on income (person_id);
