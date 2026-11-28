-- Contas fixas (decisão 012) e os meses já pagos. group_id nulo = conta pessoal (decisão 013).
-- amount_cents nulo = valor varia, informado a cada mês. A regra "partes só de membros
-- do grupo" é garantida na API, não aqui.

create table recurring_bill (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(btrim(name)) > 0),
    due_day integer not null check (due_day between 1 and 31),
    amount_cents bigint check (amount_cents >= 0),
    payment_method_id uuid not null references payment_method (id) on delete restrict,
    group_id uuid references expense_group (id) on delete restrict,
    created_by_person_id uuid not null references person (id) on delete restrict,
    installments_total integer check (installments_total >= 1),
    start_year integer,
    start_month integer check (start_month between 1 and 12),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    check (installments_total is null or (start_year is not null and start_month is not null))
);
create index recurring_bill_group_id_idx on recurring_bill (group_id);

create table recurring_bill_share (
    bill_id uuid not null references recurring_bill (id) on delete cascade,
    person_id uuid not null references person (id) on delete restrict,
    weight integer not null check (weight > 0),
    primary key (bill_id, person_id)
);

create table bill_payment (
    id uuid primary key default gen_random_uuid(),
    bill_id uuid not null references recurring_bill (id) on delete cascade,
    year integer not null,
    month integer not null check (month between 1 and 12),
    purchase_id uuid not null unique references purchase (id) on delete cascade,
    amount_cents bigint not null check (amount_cents >= 0),
    unique (bill_id, year, month)
);
