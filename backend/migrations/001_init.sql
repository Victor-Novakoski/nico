-- Schema inicial (decisoes 004, 008, 009 e 010). Dinheiro em centavos (bigint).

create table person (
    id uuid primary key default gen_random_uuid(),
    name text not null check (btrim(name) <> '')
);

create table payment_method (
    id uuid primary key default gen_random_uuid(),
    owner_person_id uuid not null references person (id) on delete cascade,
    name text not null check (btrim(name) <> ''),
    kind text not null check (kind in ('credito', 'debito', 'pix', 'dinheiro')),
    closing_day smallint check (closing_day between 1 and 31),
    due_day smallint check (due_day between 1 and 31),
    -- Só crédito tem os dois dias; os outros tipos têm os dois nulos (decisão 010).
    constraint payment_method_days_only_credit check (
        (kind = 'credito' and closing_day is not null and due_day is not null)
        or (kind <> 'credito' and closing_day is null and due_day is null)
    ),
    -- Alvo da chave estrangeira composta que limita invoice a crédito.
    constraint payment_method_id_kind_key unique (id, kind)
);

create table payment_method_alias (
    id uuid primary key default gen_random_uuid(),
    payment_method_id uuid not null references payment_method (id) on delete cascade,
    alias text not null check (btrim(alias) <> '')
);
-- O apelido resolve um meio só: único na casa toda, sem diferenciar maiúsculas.
create unique index payment_method_alias_alias_key on payment_method_alias (lower(alias));

create table invoice (
    id uuid primary key default gen_random_uuid(),
    payment_method_id uuid not null,
    kind text not null default 'credito' check (kind = 'credito'),
    year smallint not null,
    month smallint not null check (month between 1 and 12),
    closing_date date not null,
    due_date date not null,
    -- Fatura só existe para meio de crédito.
    foreign key (payment_method_id, kind) references payment_method (id, kind) on delete cascade,
    unique (payment_method_id, year, month)
);

create table purchase (
    id uuid primary key, -- gerado pelo cliente (idempotência do lançamento)
    description text not null,
    total_cents bigint not null check (total_cents >= 0),
    purchase_date date not null,
    installments integer not null default 1 check (installments >= 1),
    status text not null default 'pendente' check (status in ('pendente', 'conferido')),
    ai_provider text,
    payment_method_id uuid not null references payment_method (id) on delete restrict,
    created_by_person_id uuid not null references person (id) on delete restrict,
    created_at timestamptz not null default now()
);

create table installment (
    id uuid primary key default gen_random_uuid(),
    purchase_id uuid not null references purchase (id) on delete cascade,
    invoice_id uuid not null references invoice (id) on delete restrict,
    number integer not null check (number >= 1),
    amount_cents bigint not null check (amount_cents >= 0),
    unique (purchase_id, number)
);

create table purchase_share (
    purchase_id uuid not null references purchase (id) on delete cascade,
    person_id uuid not null references person (id) on delete restrict,
    weight integer not null check (weight > 0),
    primary key (purchase_id, person_id)
);

create table app_user (
    id uuid primary key default gen_random_uuid(),
    person_id uuid not null references person (id) on delete cascade,
    username text not null unique,
    password_hash text not null,
    ai_enabled boolean not null default false,
    default_method_id uuid references payment_method (id) on delete set null
);
